---
name: amocrm-sync
description: "amoCRM REST API: создать задачу/сделку, добавить примечание, перенести по воронке. Ключи из переменных окружения."
---

# Синхронизация с amoCRM

Фиксация договорённостей и продвижения сделок в amoCRM через REST API v2.

## Когда использовать

- Зафиксировать договорённость как задачу в amoCRM (по объекту/сделке)
- Обновить стадию сделки (перенос в другой статус/воронку)
- Добавить примечание к сделке (суть договорённости, ссылка на источник)
- Ответ на вопрос «что в amoCRM по объекту X?»

## Доступ (env)

| Переменная | Что это |
| --- | --- |
| `AMOCRM_SUBDOMAIN` | Поддомен: `mycompany` для `mycompany.amocrm.ru` |
| `AMOCRM_ACCESS_TOKEN` | Bearer-токен (OAuth access token или long-lived API key) |

Проверь наличие перед вызовами (`echo $env:AMOCRM_SUBDOMAIN`). Если нет — скажи владельцу, где взять (amoCRM → Разработчики → API), и не продолжай.

## Типовые вызовы (exec + curl)

Все запросы: `https://$env:AMOCRM_SUBDOMAIN.amocrm.ru/api/v4/...`, заголовок `Authorization: Bearer $env:AMOCRM_ACCESS_TOKEN`, `Content-Type: application/json`.

**Создать задачу по договорённости:**
```bash
curl -s -X POST "https://$AMOCRM_SUBDOMAIN.amocrm.ru/api/v4/tasks" \
  -H "Authorization: Bearer $AMOCRM_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '[{"text":"<who>: <what> (до <due>)","complete_till":"<unixtime due 12:00>","entity_type":"lead","entity_id":<lead_id>}]'
```

**Найти сделку по объекту** (name содержит адрес):
```bash
curl -s "https://$AMOCRM_SUBDOMAIN.amocrm.ru/api/v4/leads?with=contacts&query=<адрес или имя объекта>" \
  -H "Authorization: Bearer $AMOCRM_ACCESS_TOKEN"
```

**Примечание к сделке:**
```bash
curl -s -X POST "https://$AMOCRM_SUBDOMAIN.amocrm.ru/api/v4/leads/<id>/notes" \
  -H "Authorization: Bearer $AMOCRM_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '[{"note_type":"common","params":{"text":"<текст договорённости, источник: канал#сообщение>"}}]'
```

**Перенос в другой статус воронки:**
```bash
curl -s -X PATCH "https://$AMOCRM_SUBDOMAIN.amocrm.ru/api/v4/leads/<id>" \
  -H "Authorization: Bearer $AMOCRM_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '[{"pipeline_id":<id воронки>,"status_id":<id статуса>}]'
```

**Список воронок и статусов** (для маппинга): `GET /api/v4/leads/pipelines`.

## Маппинг «авто-перенос по воронке»

Веди соответствие в `ledger/objects.json` → поле `"amo": {"lead_id": 123, "pipeline": "Ремонт", "stage": "Черновик"}`. Правила маршрутизации (согласуй с владельцем при старте, значения — пример):

| Событие | Действие в amoCRM |
| --- | --- |
| Договорённость зафиксирована | Задача со сроком `due` |
| Сделка «на согласовании» → «в работе» | PATCH status_id |
| Просрочена договорённость | Задача «ПРОСРОЧЕНО: ...» + примечание |
| Объект завершён | Перенос в статус «Успешно» |

## Правила

- Никогда не удаляй сущности в amoCRM — только создавай/обновляй.
- Все изменения идемпотентны: перед созданием задачи проверь существующие (`GET /api/v4/tasks?filter[entity_id]=<id>`).
- Ошибки API показывай как есть (HTTP-код + текст ответа), без замалчивания.
- Токен в логи и ответы не выводи.
