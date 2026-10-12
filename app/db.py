import os
import time
from contextvars import ContextVar

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


def load_env():
    from pathlib import Path
    path = Path(__file__).resolve().parents[1] / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ.setdefault(key, value)


load_env()
SCHEMA = 'timur_kuzin'
engine = create_engine(os.environ.get('DATABASE_URL', 'postgresql+psycopg://localhost:55432/timur_kuzin'), pool_pre_ping=True)
Session = sessionmaker(engine)
sql_metrics = ContextVar('sql_metrics', default=None)


@event.listens_for(engine, 'before_cursor_execute')
def before_query(conn, cursor, statement, parameters, context, executemany):
    context._started = time.perf_counter()


@event.listens_for(engine, 'after_cursor_execute')
def after_query(conn, cursor, statement, parameters, context, executemany):
    metrics = sql_metrics.get()
    if metrics is not None:
        metrics['queries'] += 1
        metrics['sql_ms'] += (time.perf_counter() - context._started) * 1000


class Base(DeclarativeBase):
    pass


def get_db():
    with Session() as db:
        yield db
