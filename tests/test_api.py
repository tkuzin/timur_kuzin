import pytest


@pytest.mark.parametrize('method,path,payload', [
    ('GET', '/api/me', None), ('GET', '/api/categories', None), ('GET', '/api/tickets', None),
    ('GET', '/api/tickets/900001', None), ('GET', '/api/summary', None),
    ('POST', '/api/logout', None), ('POST', '/api/tickets', {'title': 'A', 'body': 'B', 'category_id': 900001}),
    ('PATCH', '/api/tickets/900001/status', {'status': 'in_progress'}),
    ('POST', '/api/tickets/900001/comments', {'body': 'Ответ'})])
def test_operations_require_authorization(client, method, path, payload):
    assert client.request(method, path, json=payload).status_code == 401


def test_wrong_password_and_logout(client):
    assert client.post('/api/login', json={'username': 'test_staff', 'password': 'wrong'}).status_code == 401
    assert client.post('/api/login', json={'username': 'test_staff', 'password': 'test-password'}).status_code == 200
    assert client.get('/api/me').json()['is_staff'] is True
    assert client.post('/api/logout').json() == {'ok': True}
    assert client.get('/api/me').status_code == 401


def test_list_filter_pagination_and_fields(staff):
    response = staff.get('/api/tickets?size=1&category_id=900001&status=new')
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1 and len(data['items']) == 1
    assert {'id', 'title', 'body', 'status', 'created_at', 'user_id', 'category_id'} == set(data['items'][0])
    assert staff.get('/api/tickets?size=1&page=2&category_id=900001').json()['items'] == []
    assert staff.get('/api/tickets?page=0').status_code == 422
    assert staff.get('/api/tickets?status=invalid').status_code == 422
    assert staff.get('/api/tickets?size=101').status_code == 422


def test_create_and_missing_category(staff):
    data = {'title': 'Нужна помощь', 'body': 'Не работает приложение', 'category_id': 900001}
    r = staff.post('/api/tickets', json=data)
    assert r.status_code == 201 and r.json()['status'] == 'new'
    assert staff.get('/api/tickets/' + str(r.json()['id'])).json()['title'] == data['title']
    assert staff.post('/api/tickets', json={**data, 'category_id': 99999999}).status_code == 404
    assert staff.post('/api/tickets', json={**data, 'title': ' '}).status_code == 422


def test_detail_missing_and_first_staff_reply(staff):
    assert staff.get('/api/tickets/99999999').status_code == 404
    before = staff.get('/api/tickets/900001').json()
    assert before['reaction_minutes'] is None
    reply = staff.post('/api/tickets/900001/comments', json={'body': 'Начали проверку'})
    assert reply.status_code == 201
    detail = staff.get('/api/tickets/900001').json()
    first = detail['reaction_minutes']
    assert first is not None and first >= 0
    assert detail['comments'][0]['is_staff'] is True
    staff.post('/api/tickets/900001/comments', json={'body': 'Повторный ответ'})
    assert staff.get('/api/tickets/900001').json()['reaction_minutes'] == first


def test_status_workflow_and_closed_comments(staff):
    path = '/api/tickets/900001/status'
    assert staff.patch(path, json={'status': 'closed'}).status_code == 409
    assert staff.patch(path, json={'status': 'in_progress'}).status_code == 200
    assert staff.patch(path, json={'status': 'closed'}).json()['status'] == 'closed'
    assert staff.post('/api/tickets/900001/comments', json={'body': 'Слишком поздно'}).status_code == 409
    assert staff.patch(path, json={'status': 'unknown'}).status_code == 422


def test_client_permissions_and_client_comment_is_not_staff_reply(client):
    client.post('/api/login', json={'username': 'test_client', 'password': 'test-password'})
    assert client.get('/api/summary').status_code == 403
    assert client.patch('/api/tickets/900001/status', json={'status': 'in_progress'}).status_code == 403
    assert client.post('/api/tickets/900001/comments', json={'body': 'Уточнение клиента'}).status_code == 201
    assert client.get('/api/tickets/900001').json()['reaction_minutes'] is None
    assert all(t['user_id'] == 900002 for t in client.get('/api/tickets').json()['items'])


def test_categories_summary_counts_and_metrics(staff):
    cats = staff.get('/api/categories').json()
    assert any(c['id'] == 900001 and c['sla_minutes'] == 60 for c in cats)
    r = staff.get('/api/summary')
    data = r.json()
    own = next(c for c in data['categories'] if c['category_id'] == 900001)
    assert own['total'] == own['open'] == 1 and own['breached'] == 0
    assert data['total'] == sum(c['total'] for c in data['categories'])
    assert data['open'] == sum(c['open'] for c in data['categories'])
    assert data['breached'] == sum(c['breached'] for c in data['categories'])
    assert int(r.headers['X-SQL-Queries']) > 0
    assert float(r.headers['X-SQL-Ms']) >= 0
    assert r.headers['Cache-Control'] == 'no-store'


def test_rejects_cross_origin_mutation(staff):
    assert staff.post('/api/logout', headers={'Origin': 'https://unrelated.example'}).status_code == 403
