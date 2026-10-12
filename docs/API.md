# Контракт программного интерфейса

Версия 1.0.0. JSON, UTF-8. Времена — ISO 8601 с часовым поясом UTC. Авторизация — подписанная cookie `session`, выдаваемая при входе, срок действия 8 часов. Cookie HttpOnly, SameSite=Strict; стенд работает на localhost по HTTP. Клиент получает только свои заявки; сотрудник получает все. Создание заявки всегда выполняется от имени текущего пользователя.

Объект Ticket: `id: int`, `user_id: int`, `category_id: int`, `title: str`, `body: str`, `status: new|in_progress|closed`, `created_at: datetime`. Ошибки имеют поле `detail`: строка для прикладных ошибок или массив описаний для ошибок валидации FastAPI.

| Метод и путь | Параметры | Успешный ответ | Ошибки |
|---|---|---|---|
| POST /api/login | JSON username (1–80 символов), password (1–200) | 200: id, username, is_staff; cookie session | 401 неверная пара, 422 параметры |
| POST /api/logout | Нет | 200: {ok: true}; удаление сессии | 401 |
| GET /api/me | Нет | 200: id, username, is_staff | 401 |
| GET /api/categories | Нет | 200: массив {id, name, sla_minutes} по id | 401 |
| GET /api/tickets | Query page≥1 (1), size 1–100 (20), status (необязательный), category_id>0 (необязательный) | 200: {items: Ticket[], total, page, size}; сортировка created_at DESC, id DESC | 401, 422; неизвестная категория даёт пустой список |
| POST /api/tickets | JSON title (1–200), body (1–5000), category_id>0; текст содержит непробельный символ | 201: Ticket со статусом new | 401, 404 категория, 422 |
| GET /api/tickets/{id} | Целый id | 200: Ticket + owner, category {id,name,sla_minutes}, reaction_minutes: number|null, sla_breached: bool, comments: [{id,body,author,is_staff,created_at}] | 401, 403 чужая заявка, 404, 422 |
| PATCH /api/tickets/{id}/status | Целый id; JSON status | 200: Ticket | 401, 403 не сотрудник, 404, 409 переход запрещён, 422 |
| POST /api/tickets/{id}/comments | Целый id; JSON body (1–5000), непробельный | 201: {id,ticket_id,body,created_at} | 401, 403 чужая заявка, 404, 409 заявка закрыта, 422 |
| GET /api/summary | Только сотрудник | 200: {as_of,total,open,breached,categories:[{category_id,name,sla_minutes,total,open,breached,breached_share}]} | 401, 403 |

Для всех изменяющих запросов Origin, если передан браузером, должен совпадать с адресом сервиса; иначе 403. Пользовательские идентификаторы для API чтения и изменения — целые; несуществующие, включая неположительные, дают 404, если доступ к операции разрешён.

Разрешённые переходы: `new → in_progress → closed`. Повторная установка того же статуса, пропуск этапа и повторное открытие дают 409. Изменение статуса и добавление комментария блокируют строку заявки на время транзакции: нельзя добавить комментарий одновременно с уже завершившимся закрытием.

Первый ответ — минимальное время комментария сотрудника. Комментарии клиента не останавливают отсчёт. До ответа reaction_minutes = null; нарушение проверяется относительно текущего времени. Ответ ровно в срок нарушением не является. Для каждой категории breached_share = breached / total (0 для пустой категории), знаменатель включает открытые и закрытые заявки. Сводка не ограничивается текущей страницей.

HTML-страницы `/login`, `/`, `/tickets/{id}`, `/summary` являются оболочкой интерфейса и получают данные через перечисленные API. В измерения включены все 10 операций API; для списка дополнительно измерен фильтр status=new&category_id=1. `/docs` и `/openapi.json` — служебная документация, не пользовательские операции.
