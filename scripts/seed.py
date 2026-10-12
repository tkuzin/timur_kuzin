import argparse
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import insert, text
from app.db import SCHEMA, engine
from app.models import Category, Comment, Ticket, User
from app.security import hash_password

NAMES = ['Учётные записи', 'Сеть и интернет', 'Рабочие места', 'Программное обеспечение', 'Почта', 'Доступ к ресурсам', 'Печать', 'Телефония', 'Видеосвязь', 'Прочее']


def seed(size):
    users, cats, tickets = (50, 5, 300) if size == 'small' else (3000, 10, 50000)
    password = hash_password(os.environ.get('DEMO_PASSWORD', 'timur-demo-2026'), salt='timur_kuzin_dataset_v1')
    base = datetime(2026, 9, 1, tzinfo=timezone.utc)
    digest = hashlib.sha256()
    with engine.begin() as conn:
        conn.execute(text(f'TRUNCATE {SCHEMA}.comments, {SCHEMA}.tickets, {SCHEMA}.categories, {SCHEMA}.users RESTART IDENTITY'))
        def batch(model, data):
            for offset in range(0, len(data), 2000):
                part = data[offset:offset + 2000]
                conn.execute(insert(model), part)
                digest.update(json.dumps(part, default=str, sort_keys=True, ensure_ascii=False).encode())
        batch(User, [{'id': i, 'username': 'operator' if i == 1 else ('client' if i == 2 else f'user_{i:04d}'), 'password_hash': password, 'is_staff': i % 10 == 1} for i in range(1, users + 1)])
        batch(Category, [{'id': i, 'name': NAMES[i - 1], 'sla_minutes': [30, 60, 120, 240, 480][(i - 1) % 5]} for i in range(1, cats + 1)])
        ticket_rows, comment_rows = [], []
        for i in range(1, tickets + 1):
            owner = 2 + (i * 7 % (users - 2))
            if owner % 10 == 1:
                owner += 1
            category = (i - 1) % cats + 1
            sla = [30, 60, 120, 240, 480][(category - 1) % 5]
            created = base + timedelta(seconds=(i * 137) % (20 * 86400))
            ticket_rows.append({'id': i, 'user_id': owner, 'category_id': category, 'title': f'{NAMES[category-1]}: обращение {i}', 'body': f'Учебная заявка № {i}. Требуется проверить доступность сервиса и помочь восстановить работу. Описание содержит сведения о воспроизводимой проблеме рабочего места.', 'status': ['new', 'in_progress', 'closed'][i % 3], 'created_at': created})
            reply_at = created + timedelta(minutes=sla * (2 if i % 4 == 0 else 0.5))
            for j in range(3):
                staff = j == 1 and i % 5 != 0
                comment_rows.append({'id': (i - 1) * 3 + j + 1, 'ticket_id': i, 'user_id': 1 if staff else owner, 'body': 'Проверяем обращение, уточняем обстоятельства.' if staff else f'Дополнение {j+1}: описание симптомов и условий возникновения проблемы.', 'created_at': reply_at if staff else created + timedelta(minutes=j + 1)})
        batch(Ticket, ticket_rows)
        batch(Comment, comment_rows)
        for table in ('users', 'categories', 'tickets', 'comments'):
            conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{SCHEMA}.{table}', 'id'), (SELECT max(id) FROM {SCHEMA}.{table}))"))
        counts = {table: conn.scalar(text(f'SELECT count(*) FROM {SCHEMA}.{table}')) for table in ('users', 'categories', 'tickets', 'comments')}
    with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as conn:
        conn.execute(text(f'ANALYZE {SCHEMA}.users, {SCHEMA}.categories, {SCHEMA}.tickets, {SCHEMA}.comments'))
    result = {'size': size, 'counts': counts, 'sha256_input_rows': digest.hexdigest(), 'seed_version': 1}
    Path('artifacts').mkdir(exist_ok=True)
    Path(f'artifacts/seed_{size}.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Reset ONLY the timur_kuzin project schema and seed deterministic data.')
    parser.add_argument('size', choices=['small', 'work'])
    args = parser.parse_args()
    seed(args.size)
