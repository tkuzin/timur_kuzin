import argparse
import csv
import json
import math
import os
import platform
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import text
from app.db import SCHEMA, engine


def run(size, base_url, repeats=30, warmup=5):
    credentials = {'username': 'operator', 'password': os.environ.get('DEMO_PASSWORD', 'timur-demo-2026')}
    samples, results = [], []
    with httpx.Client(base_url=base_url, timeout=120, trust_env=False) as client:
        def login():
            client.post('/api/login', json=credentials).raise_for_status()
        def new_ticket():
            r = client.post('/api/tickets', json={'title': 'Проверка измерений', 'body': 'Заявка серии измерений', 'category_id': 1})
            r.raise_for_status()
            return r.json()['id']
        login()
        def measure(name, method, path, payload=None, prepare=None, status=200):
            rows = []
            for i in range(warmup + repeats):
                dynamic = prepare() if prepare else None
                url = path(dynamic) if callable(path) else path
                start = time.perf_counter()
                response = client.request(method, url, json=payload)
                elapsed = (time.perf_counter() - start) * 1000
                if response.status_code != status:
                    raise RuntimeError(f'{name}: {response.status_code} {response.text}')
                row = {'scenario': name, 'iteration': i - warmup + 1, 'http_ms': elapsed,
                       'sql_ms': float(response.headers['X-SQL-Ms']), 'handler_ms': float(response.headers['X-App-Ms']),
                       'queries': int(response.headers['X-SQL-Queries']), 'status': response.status_code}
                if i >= warmup:
                    rows.append(row)
                    samples.append(row)
            times = sorted(r['http_ms'] for r in rows)
            p50 = statistics.median(times)
            sql = statistics.median(r['sql_ms'] for r in rows)
            results.append({'scenario': name, 'p50': p50, 'p95': times[math.ceil(repeats * 0.95)-1], 'max': max(times),
                            'sql_p50': sql, 'residual': p50-sql, 'queries': statistics.median(r['queries'] for r in rows)})
            print(f'{name}: p50={p50:.2f} ms, p95={results[-1]["p95"]:.2f}, SQL={sql:.2f}, queries={results[-1]["queries"]}', flush=True)
        # All reads precede the write series; both volumes start from the seed.
        measure('login', 'POST', '/api/login', credentials)
        measure('logout', 'POST', '/api/logout', prepare=login)
        login()
        measure('me', 'GET', '/api/me')
        measure('categories', 'GET', '/api/categories')
        measure('list', 'GET', '/api/tickets?page=1&size=20')
        measure('list_filtered', 'GET', '/api/tickets?page=1&size=20&status=new&category_id=1')
        measure('detail', 'GET', '/api/tickets/1')
        measure('summary', 'GET', '/api/summary')
        measure('create', 'POST', '/api/tickets', {'title': 'Измерение создания', 'body': 'Контрольная запись', 'category_id': 1}, status=201)
        measure('status', 'PATCH', lambda key: f'/api/tickets/{key}/status', {'status': 'in_progress'}, prepare=new_ticket)
        comment_target = new_ticket()
        measure('comment', 'POST', f'/api/tickets/{comment_target}/comments', {'body': 'Контрольный ответ'}, status=201)
    with engine.connect() as conn:
        counts = {t: conn.scalar(text(f'SELECT count(*) FROM {SCHEMA}.{t}')) for t in ('users', 'categories', 'tickets', 'comments')}
    out = Path('artifacts'); out.mkdir(exist_ok=True)
    report = {'size': size, 'recorded_at_utc': datetime.now(timezone.utc).isoformat(), 'repeats': repeats, 'warmup': warmup,
              'account': 'operator', 'base_url': base_url, 'python': platform.python_version(), 'platform': platform.platform(),
              'counts_after': counts, 'results': results}
    (out/f'benchmark_{size}.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    with (out/f'samples_{size}.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(samples[0])); writer.writeheader(); writer.writerows(samples)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('size', choices=['small', 'work'])
    parser.add_argument('--url', default='http://127.0.0.1:8080')
    args = parser.parse_args()
    run(args.size, args.url)
