---
name: calendar-sync
description: "Календарь (Google Calendar / Яндекс.Календарь): создать событие из договорённости, список событий на день для дайджеста, напоминания."
---

# Синхронизация с календарём

Превращает договорённости в события календаря и подтягивает расписание в дайджест.

## Когда использовать

- Зафиксирована договорённость со сроком → создать событие-напоминание
- Вопросы: «что у меня в календаре на сегодня/неделю?», «поставь встречу»
- Утренний дайджест (раздел «Календарь на сегодня»)

## Google Calendar (env)

| Переменная | Что это |
| --- | --- |
| `GOOGLE_ACCESS_TOKEN` | OAuth-токен с scope `https://www.googleapis.com/auth/calendar.events` |
| `GOOGLE_CALENDAR_ID` | `primary` по умолчанию |

**Создать событие:**
```bash
curl -s -X POST "https://www.googleapis.com/calendar/v3/calendars/$GOOGLE_CALENDAR_ID/events" \
  -H "Authorization: Bearer $GOOGLE_ACCESS_TOKEN" -H "Content-Type: application/json" \
  -d '{
    "summary": "<who>: <what>",
    "description": "Договорённость <agreement-id>, источник: <source>",
    "start": {"date": "YYYY-MM-DD"},
    "end": {"date": "YYYY-MM-DD+1"},
    "reminders": {"useDefault": false, "overrides": [{"method": "popup", "minutes": 60}]}
  }'
```
Для встреч со временем: `"start": {"dateTime": "2026-11-27T15:00:00+03:00"}`.

**Список событий на день:**
```bash
curl -s "https://www.googleapis.com/calendar/v3/calendars/$GOOGLE_CALENDAR_ID/events?timeMin=<ISO 00:00>&timeMax=<ISO 24:00>&singleEvents=true&orderBy=startTime" \
  -H "Authorization: Bearer $GOOGLE_ACCESS_TOKEN"
```

## Яндекс.Календарь (CalDAV, env)

| Переменная | Что это |
| --- | --- |
| `YANDEX_CALDAV_URL` | `https://caldav.yandex.ru/calendars/<логин>/` |
| `YANDEX_CALDAV_USER` | логин Яндекса |
| `YANDEX_CALDAV_PASSWORD` | пароль приложения (id.yandex.ru → пароли приложений) |

Событие — PUT .ics-файла:
```bash
curl -s -X PUT "$YANDEX_CALDAV_URL/<uid>.ics" \
  -u "$YANDEX_CALDAV_USER:$YANDEX_CALDAV_PASSWORD" -H "Content-Type: text/calendar" \
  --data-binary $'BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:<uid>\r\nDTSTART;VALUE=DATE:20261127\r\nSUMMARY:<who>: <what>\r\nDESCRIPTION:Договорённость <agreement-id>\r\nBEGIN:VALARM\r\nTRIGGER:-PT60M\r\nACTION:DISPLAY\r\nEND:VALARM\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n'
```

Список на день: `PROPFIND`/`REPORT` по тому же URL (или GET календаря); для пилота достаточно Google-варианта.

## Правила

- Событие из договорённости = дедлайн (`due`) в 09:00 + напоминание за час. Если `due` пуст — событие не создавай, ограничься напоминанием агента.
- В `description` всегда указывай `agreement-id` и `source` — обратная связь с `ledger/agreements.jsonl`.
- После создания события обнови договорённость: `"calendar": "<event-id>"`.
- Не изменяй чужие события без команды владельца.
- Токены в вывод не показывай; при ошибке API — HTTP-код и текст ответа как есть.
