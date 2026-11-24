# Пилот: ИИ-ассистент по объектам (OpenClaw)

Персональный агент, который читает переписки клиента (WhatsApp, Telegram, почта),
фиксирует договорённости, следит за сроками, ведёт расходы по объектам и
синхронизирует всё с amoCRM / календарём.

## Что уже собрано

| Компонент | Где | Что делает |
| --- | --- | --- |
| `skills/object-ledger` | скилл | Реестр объектов, ответы «что сейчас по объекту на Ленина?» |
| `skills/agreement-extractor` | скилл | Договорённости из переписок → реестр + напоминание + задача |
| `skills/deadline-monitor` | скилл | Контроль сроков контрагентов, готовые тексты напоминаний |
| `skills/morning-digest` | скилл | Утренняя сводка: срочное, ответы, зависшее, деньги |
| `skills/expense-ledger` | скилл | Расходы по объектам vs смета и плановая прибыль |
| `skills/amocrm-sync` | скилл | Задачи/сделки/примечания/воронки amoCRM (REST API) |
| `skills/mail-triage` | скилл | Спам-фильтр почты, договорённости из писем, «ждут ответа» |
| `skills/calendar-sync` | скилл | Google/Yandex Календарь: дедлайны → события, расписание в дайджест |
| `tg-ingest/` | сервис | MTProto userbot: чтение личных чатов Telegram → OpenClaw |
| `ledger/` | данные | objects.json / agreements.jsonl / expenses.csv / inbox.jsonl |
| `openclaw.pilot.json` | конфиг | Каналы, webhooks, таймзона, политика доступа |
| `scripts/install-pilot.ps1` | скрипт | Установка скиллов и автоматизаций |

Автоматизации (регистрируются скриптом):
- `morning-digest` — каждый день в 08:00
- `deadline-check` — 09:00 и 17:00 (проверка сроков)

## Установка (Windows)

1. **Node.js 24.x** (или 26.x) — через nvm: `nvm install 24` / `nvm use 24`.
2. **OpenClaw**:
   ```powershell
   npm install -g openclaw@latest --allow-scripts=openclaw
   openclaw onboard --install-daemon   # мастер: модель, workspace, Gateway
   ```
3. **Пилот**:
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\install-pilot.ps1
   ```
4. **WhatsApp** (главный канал — видит входящие переписки):
   ```powershell
   openclaw plugins install "@openclaw/whatsapp"
   openclaw channels login --channel whatsapp   # QR → Linked Devices на телефоне
   ```
   ⚠️ Используй **отдельный номер/телефон** под агента: Baileys — неофициальный
   клиент WhatsApp, есть риск ограничений аккаунта.
5. **Telegram** — два контура:
   - **Бот** (диалог с агентом + рабочие группы):
     ```powershell
     openclaw channels add --channel telegram     # токен от @BotFather
     ```
   - **Личные чаты клиента** — через MTProto userbot (`tg-ingest/`), см. раздел ниже.
6. **Telegram MTProto (tg-ingest)** — чтение личных переписок:
   1. `https://my.telegram.org` → API development tools → получи `api_id`, `api_hash`.
   2. Настрой webhook в конфиге OpenClaw (`hooks` из `openclaw.pilot.json`), заменив
      токен на случайный: `openclaw config validate && openclaw gateway restart`.
   3. В `tg-ingest\`:
      ```powershell
      pip install -r requirements.txt
      copy config.example.json config.json   # заполни api_id/api_hash/chats/hook_token
      python login.py --config config.json   # вход: код из Telegram (создаст .session)
      python ingest.py --config config.json --dry-run   # самопроверка без сети
      python ingest.py --config config.json             # слушает новые сообщения
      ```
   4. `--backfill 30` — разово выгрузить историю за 30 дней (для «памяти»).
   ⚠️ Аккаунт клиента под MTProto — серая зона ToS Telegram; используй
   умеренный объём запросов, не сканируй всю историю постоянно.
7. **amoCRM** — переменные окружения (в систему или `.env` окружения Gateway):
   ```powershell
   [Environment]::SetEnvironmentVariable("AMOCRM_SUBDOMAIN", "mycompany", "User")
   [Environment]::SetEnvironmentVariable("AMOCRM_ACCESS_TOKEN", "...", "User")
   ```
8. **Календарь** — переменные `GOOGLE_ACCESS_TOKEN` / `YANDEX_CALDAV_*`
   (см. `skills/calendar-sync/SKILL.md`).
9. **Почта** — `openclaw configure` (IMAP/Gmail), либо `docs/automation/imap.md`.
10. Проверка: `openclaw gateway status`, `openclaw dashboard`, `openclaw skills list`
    (должны быть видны все 8 скиллов пилота).

## Как проверить пилот (сценарии приёмки)

1. В WhatsApp (с номера из `allowFrom`): «Что сейчас по объекту на Ленина?»
   → карточка объекта из ledger.
2. Переслать сообщение подрядчика «Закончу отделку до пятницы»
   → «Зафиксировано: …, напоминание поставлено» + запись в `ledger/agreements.jsonl`.
3. «Сколько потрачено по Ленина и сколько до прибыли?» → цифры из expenses.csv.
4. Утром в 08:00 приходит дайджест.
5. «Напомни Сидорову про смету» → готовый текст сообщения (отправка — по кнопке/да).
6. «Разбери почту» → сводка спам/деловые/ждут ответа.
7. **MTProto**: в личный чат TG (из allowlist) приходит «Закончу до пятницы»
   → запись в `ledger/inbox.jsonl` + агент фиксирует договорённость
   (agreements.jsonl + задача amoCRM + событие календаря).
8. **Календарь**: «что в календаре на сегодня?» → события; договорённость с `due`
   появляется в календаре.

## Ограничения пилота (честно)

- **Telegram**: личные чаты читает `tg-ingest` (MTProto). Серая зона ToS —
  риск ограничений аккаунта; бот остаётся каналом ответов и управления.
- **MAX**: программного доступа к личным чатам нет — импорт/пересылка вручную.
- **Отправка сообщений контрагентам** — только через согласование владельцем
  (draft + «одно нажатие»). Автоответы выключены осознанно.
- amoCRM: нужен действующий токен; маппинг воронок согласуется при старте.

## Roadmap (фаза 2+)

1. **Яндекс Телемост** — записи → Яндекс.Диск API + ASR (Whisper/SpeechKit) →
   договорённости из звонков.
2. **MAX** — мониторинг статуса API; пока ручной импорт.
3. **Сингуларити** — интеграция после получения API-доступа.
4. Статусы прочтения/ответов в tg-ingest (кто кому ответил) — точнее «ждут ответа».

## Где живут данные

- Состояние OpenClaw: `~/.openclaw/` (config, память, сессии)
- Реестры пилота: `<workspace>/ledger/` (JSON/CSV, бэкапить!)
- Скиллы: `<workspace>/skills/`

## Безопасность и право

- Согласие владельца на обработку переписок и передачу текстов модели — обязательно.
- Согласие контрагентов на обработку переписок/записей звонков — 152-ФЗ.
- Ключи (amoCRM, почта) — только в секретах/окружении, не в git.
- Входящие сообщения — недоверенный ввод; исполнение команд только по политике
  OpenClaw (см. docs.openclaw.ai → Security).
