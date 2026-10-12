from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.db import engine, get_db
from app.main import app
from app.models import Category, Ticket, User
from app.security import hash_password


@pytest.fixture
def client():
    # Real PostgreSQL and the real HTTP handlers; all test writes roll back.
    with engine.connect() as conn:
        transaction = conn.begin()
        with Session(bind=conn, join_transaction_mode='create_savepoint') as db:
            hashed = hash_password('test-password', 'test-fixed-salt')
            db.add_all([User(id=900001, username='test_staff', password_hash=hashed, is_staff=True), User(id=900002, username='test_client', password_hash=hashed, is_staff=False), Category(id=900001, name='Тестовая категория', sla_minutes=60)])
            db.flush()
            db.add(Ticket(id=900001, user_id=900002, category_id=900001, title='Тест', body='Описание', status='new', created_at=datetime.now(timezone.utc)))
            db.commit()
        def override():
            with Session(bind=conn, join_transaction_mode='create_savepoint') as db:
                yield db
        app.dependency_overrides[get_db] = override
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()
            transaction.rollback()


@pytest.fixture
def staff(client):
    assert client.post('/api/login', json={'username': 'test_staff', 'password': 'test-password'}).status_code == 200
    return client
