import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession
from starlette.middleware.sessions import SessionMiddleware

from .db import get_db, sql_metrics
from .models import Category, Comment, Ticket, User
from .rules import can_transition, reaction_minutes, sla_breached
from .security import verify_password

app = FastAPI(title='timur_kuzin — служба поддержки', version='1.0.0')
app.add_middleware(SessionMiddleware, secret_key=os.environ['SESSION_SECRET'], same_site='strict', max_age=28800)
templates = Jinja2Templates(directory=str(Path(__file__).parent / 'templates'))


@app.middleware('http')
async def measure(request: Request, call_next):
    started = time.perf_counter()
    metrics = {'queries': 0, 'sql_ms': 0.0}
    token = sql_metrics.set(metrics)
    try:
        origin = request.headers.get('origin')
        if request.method not in {'GET', 'HEAD', 'OPTIONS'} and origin and origin.rstrip('/') != str(request.base_url).rstrip('/'):
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail': 'Недопустимый источник запроса'}, status_code=403)
        response = await call_next(request)
        response.headers['X-SQL-Ms'] = f"{metrics['sql_ms']:.3f}"
        response.headers['X-SQL-Queries'] = str(metrics['queries'])
        response.headers['X-App-Ms'] = f'{(time.perf_counter() - started) * 1000:.3f}'
        response.headers['Cache-Control'] = 'no-store'
        return response
    finally:
        sql_metrics.reset(token)


def current_user(request: Request, db: DbSession = Depends(get_db)):
    user_id = request.session.get('user_id')
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, 'Требуется вход')
    return user


def require_staff(user=Depends(current_user)):
    if not user.is_staff:
        raise HTTPException(403, 'Требуется роль сотрудника')
    return user


def accessible_ticket(db, ticket_id, user, lock=False):
    query = select(Ticket).where(Ticket.id == ticket_id)
    if lock:
        query = query.with_for_update()
    ticket = db.scalar(query)
    if ticket is None:
        raise HTTPException(404, 'Заявка не найдена')
    if not user.is_staff and ticket.user_id != user.id:
        raise HTTPException(403, 'Чужая заявка')
    return ticket


def ticket_dict(t):
    return {key: getattr(t, key) for key in ('id', 'user_id', 'category_id', 'title', 'body', 'status', 'created_at')}


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class NewTicket(BaseModel):
    title: str = Field(min_length=1, max_length=200, pattern=r'\S')
    body: str = Field(min_length=1, max_length=5000, pattern=r'\S')
    category_id: int = Field(gt=0)


class NewComment(BaseModel):
    body: str = Field(min_length=1, max_length=5000, pattern=r'\S')


class StatusChange(BaseModel):
    status: Literal['new', 'in_progress', 'closed']


@app.post('/api/login')
def login(data: Credentials, request: Request, db: DbSession = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == data.username))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, 'Неверное имя или пароль')
    request.session.clear()
    request.session['user_id'] = user.id
    return {'id': user.id, 'username': user.username, 'is_staff': user.is_staff}


@app.post('/api/logout')
def logout(request: Request, user=Depends(current_user)):
    request.session.clear()
    return {'ok': True}


@app.get('/api/me')
def me(user=Depends(current_user)):
    return {'id': user.id, 'username': user.username, 'is_staff': user.is_staff}


@app.get('/api/categories')
def categories(db: DbSession = Depends(get_db), user=Depends(current_user)):
    return [{'id': c.id, 'name': c.name, 'sla_minutes': c.sla_minutes} for c in db.scalars(select(Category).order_by(Category.id))]


@app.get('/api/tickets')
def list_tickets(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
                 status: Literal['new', 'in_progress', 'closed'] | None = None,
                 category_id: int | None = Query(None, gt=0), db: DbSession = Depends(get_db), user=Depends(current_user)):
    filters = []
    if not user.is_staff:
        filters.append(Ticket.user_id == user.id)
    if status:
        filters.append(Ticket.status == status)
    if category_id:
        filters.append(Ticket.category_id == category_id)
    total = db.scalar(select(func.count()).select_from(Ticket).where(*filters))
    rows = db.scalars(select(Ticket).where(*filters).order_by(Ticket.created_at.desc(), Ticket.id.desc()).offset((page - 1) * size).limit(size))
    return {'items': [ticket_dict(t) for t in rows], 'total': total, 'page': page, 'size': size}


@app.post('/api/tickets', status_code=201)
def create_ticket(data: NewTicket, db: DbSession = Depends(get_db), user=Depends(current_user)):
    if db.get(Category, data.category_id) is None:
        raise HTTPException(404, 'Категория не найдена')
    ticket = Ticket(**data.model_dump(), user_id=user.id, status='new', created_at=datetime.now(timezone.utc))
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket_dict(ticket)


@app.get('/api/tickets/{ticket_id}')
def ticket_detail(ticket_id: int, db: DbSession = Depends(get_db), user=Depends(current_user)):
    ticket = accessible_ticket(db, ticket_id, user)
    category = db.get(Category, ticket.category_id)
    owner = db.get(User, ticket.user_id)
    comments = db.execute(select(Comment, User).join(User, User.id == Comment.user_id).where(Comment.ticket_id == ticket_id).order_by(Comment.created_at, Comment.id)).all()
    first_reply = next((c.created_at for c, author in comments if author.is_staff), None)
    return {**ticket_dict(ticket), 'owner': owner.username,
            'category': {'id': category.id, 'name': category.name, 'sla_minutes': category.sla_minutes},
            'reaction_minutes': reaction_minutes(ticket.created_at, first_reply),
            'sla_breached': sla_breached(ticket.created_at, first_reply, category.sla_minutes, datetime.now(timezone.utc)),
            'comments': [{'id': c.id, 'body': c.body, 'author': a.username, 'is_staff': a.is_staff, 'created_at': c.created_at} for c, a in comments]}


@app.patch('/api/tickets/{ticket_id}/status')
def change_status(ticket_id: int, data: StatusChange, db: DbSession = Depends(get_db), user=Depends(require_staff)):
    ticket = accessible_ticket(db, ticket_id, user, lock=True)
    if not can_transition(ticket.status, data.status):
        raise HTTPException(409, 'Разрешены переходы новая → в работе → закрыта')
    ticket.status = data.status
    db.commit()
    db.refresh(ticket)
    return ticket_dict(ticket)


@app.post('/api/tickets/{ticket_id}/comments', status_code=201)
def add_comment(ticket_id: int, data: NewComment, db: DbSession = Depends(get_db), user=Depends(current_user)):
    ticket = accessible_ticket(db, ticket_id, user, lock=True)
    if ticket.status == 'closed':
        raise HTTPException(409, 'Переписка закрытой заявки завершена')
    comment = Comment(ticket_id=ticket_id, user_id=user.id, body=data.body, created_at=datetime.now(timezone.utc))
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {'id': comment.id, 'ticket_id': ticket_id, 'body': comment.body, 'created_at': comment.created_at}


@app.get('/api/summary')
def summary(db: DbSession = Depends(get_db), user=Depends(require_staff)):
    now = datetime.now(timezone.utc)
    cats = list(db.scalars(select(Category).order_by(Category.id)))
    tickets = list(db.scalars(select(Ticket)))
    first_replies = dict(db.execute(select(Comment.ticket_id, func.min(Comment.created_at)).join(User, User.id == Comment.user_id).where(User.is_staff.is_(True)).group_by(Comment.ticket_id)).all())
    result = {c.id: {'category_id': c.id, 'name': c.name, 'sla_minutes': c.sla_minutes, 'total': 0, 'open': 0, 'breached': 0} for c in cats}
    for ticket in tickets:
        row = result[ticket.category_id]
        row['total'] += 1
        if ticket.status != 'closed':
            row['open'] += 1
        row['breached'] += int(sla_breached(ticket.created_at, first_replies.get(ticket.id), row['sla_minutes'], now))
    for row in result.values():
        row['breached_share'] = row['breached'] / row['total'] if row['total'] else 0
    return {'as_of': now, 'total': len(tickets), 'open': sum(r['open'] for r in result.values()),
            'breached': sum(r['breached'] for r in result.values()), 'categories': list(result.values())}


@app.get('/', response_class=HTMLResponse, include_in_schema=False)
@app.get('/tickets/{ticket_id}', response_class=HTMLResponse, include_in_schema=False)
@app.get('/summary', response_class=HTMLResponse, include_in_schema=False)
def page(request: Request, ticket_id: int | None = None):
    if not request.session.get('user_id'):
        return RedirectResponse('/login', status_code=303)
    return templates.TemplateResponse(request=request, name='index.html', context={'ticket_id': ticket_id})


@app.get('/login', response_class=HTMLResponse, include_in_schema=False)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name='login.html', context={})
