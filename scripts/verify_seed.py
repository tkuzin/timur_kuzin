import json
from pathlib import Path
from sqlalchemy import text
from app.db import engine, SCHEMA
from scripts.seed import seed


def fingerprint():
    with engine.connect() as conn:
        return {t: conn.scalar(text(f"SELECT md5(string_agg(to_jsonb(x)::text, '' ORDER BY id)) FROM {SCHEMA}.{t} x")) for t in ('users', 'categories', 'tickets', 'comments')}


if __name__ == '__main__':
    results = {}
    for size in ('small', 'work'):
        a = seed(size); fa = fingerprint()
        b = seed(size); fb = fingerprint()
        assert a == b and fa == fb
        results[size] = {'equal': True, 'counts': a['counts'], 'input_sha256': a['sha256_input_rows'], 'database_md5_first': fa, 'database_md5_second': fb}
    Path('artifacts/reproducibility.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    with engine.connect() as conn:
        indexes = [dict(row._mapping) for row in conn.execute(text('SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname=:schema'), {'schema': SCHEMA})]
    Path('artifacts/indexes.json').write_text(json.dumps(indexes, indent=2), encoding='utf-8')
    print('Both datasets are byte-equivalent as PostgreSQL JSON rows across two seed runs.')
