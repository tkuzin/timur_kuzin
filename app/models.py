from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, SCHEMA


class User(Base):
    __tablename__ = 'users'
    __table_args__ = {'schema': SCHEMA}
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(240))
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)


class Category(Base):
    __tablename__ = 'categories'
    __table_args__ = (CheckConstraint('sla_minutes > 0'), {'schema': SCHEMA})
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    sla_minutes: Mapped[int] = mapped_column(Integer)


class Ticket(Base):
    __tablename__ = 'tickets'
    __table_args__ = (CheckConstraint("status IN ('new', 'in_progress', 'closed')"), {'schema': SCHEMA})
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey(f'{SCHEMA}.users.id'))
    category_id: Mapped[int] = mapped_column(ForeignKey(f'{SCHEMA}.categories.id'))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='new')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Comment(Base):
    __tablename__ = 'comments'
    __table_args__ = {'schema': SCHEMA}
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey(f'{SCHEMA}.tickets.id'))
    user_id: Mapped[int] = mapped_column(ForeignKey(f'{SCHEMA}.users.id'))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
