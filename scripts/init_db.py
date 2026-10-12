from sqlalchemy import create_engine, text
from app.db import Base, SCHEMA, engine
from app import models  # register metadata


def main():
    admin = create_engine(engine.url.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as conn:
        if not conn.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': SCHEMA}):
            conn.execute(text(f'CREATE DATABASE {SCHEMA}'))
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {SCHEMA}'))
    Base.metadata.create_all(engine)
    print(f'Database and schema ready: {SCHEMA}')


if __name__ == '__main__':
    main()
