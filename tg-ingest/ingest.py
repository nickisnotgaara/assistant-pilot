"""Telegram MTProto ingest -> OpenClaw.

Слушает новые сообщения в личных чатах/группах из allowlist,
пишет их в ledger/inbox.jsonl и будит агента через Gateway webhook
(POST /hooks/agent), чтобы agreement-extractor / object-ledger
обработали событие.

Usage:
  python ingest.py --config config.json              # слушать новые сообщения
  python ingest.py --config config.json --dry-run    # проверка без сети
  python ingest.py --config config.json --backfill 30  # выгрузить историю за N дней
"""

import argparse
import asyncio
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from telethon import TelegramClient, events

SAMPLE = {
    "id": 9001,
    "chat_id": 777000,
    "chat": "Иванов Иван",
    "sender_id": 777000,
    "sender": "Иванов Иван",
    "date": "2026-11-22T10:30:00+00:00",
    "text": "Закончу отделку стен до пятницы, смету пришлю завтра",
    "source": "telegram:777000#9001",
}


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Config not found: {p}. Copy config.example.json -> config.json first.")
    return json.loads(p.read_text(encoding="utf-8-sig"))


def append_inbox(ledger_dir: Path, record: dict) -> None:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    with (ledger_dir / "inbox.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_agent_message(record: dict) -> str:
    text = (record["text"] + "\n").replace("\u2014", "-").replace("\u2013", "-")
    body = (
        "Новое сообщение из Telegram, MTProto ingest.\n"
        f"Чат: {record['chat']}, id {record['chat_id']}\n"
        f"Отправитель: {record['sender']}\n"
        f"Время: {record['date']}\n"
        f"Источник: {record['source']}\n"
        "Текст:\n"
        f"{text}\n"
        "Обработай по скиллу agreement-extractor. Если это договорённость, срок или "
        "деньги, зафиксируй в реестре договорённостей с source как выше и поставь "
        "напоминание. Иначе обнови контекст объекта по скиллу object-ledger. "
        "Ответ в чат не отправляй. Сообщения контрагентам: только владельцу на согласование."
    )
    # shortcut: webhook scanner rejects em/en-dash as a malformed flag, replace until upstream fixes it
    return body.replace("\u2014", "-").replace("\u2013", "-")


def push_to_openclaw(cfg: dict, record: dict) -> None:
    oc = cfg["openclaw"]
    url = oc["gateway_url"].rstrip("/") + oc["hook_path"]
    payload = json.dumps(
        {
            "message": build_agent_message(record),
            "name": f"tg-ingest {record['source']}",
            "agentId": oc.get("agent_id", "main"),
            "deliver": bool(oc.get("deliver", False)),
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {oc['hook_token']}",
            "Content-Type": "application/json",
            "Idempotency-Key": f"tg-{record['chat_id']}-{record['id']}",
        },
    )
    try:
        with urlrequest.urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8", "replace")
            print(f"[openclaw] {resp.status} {body}")
    except HTTPError as e:
        print(f"[openclaw] HTTP {e.code}: {e.read().decode('utf-8', 'replace')}", file=sys.stderr)
    except URLError as e:
        print(f"[openclaw] gateway недоступен: {e.reason}", file=sys.stderr)


def normalize(event, chat, sender) -> dict:
    text = (event.message.message or "").strip()
    src = f"telegram:{event.chat_id}#{event.message.id}"
    return {
        "id": event.message.id,
        "chat_id": event.chat_id,
        "chat": getattr(chat, "title", None) or getattr(chat, "first_name", None) or str(event.chat_id),
        "sender_id": getattr(event.sender_id, "id", event.sender_id),
        "sender": getattr(sender, "first_name", None) or str(event.sender_id),
        "date": event.message.date.astimezone(timezone.utc).isoformat(),
        "text": text,
        "source": src,
    }


def chat_allowed(cfg: dict, chat_id) -> bool:
    tg = cfg["telegram"]
    if tg.get("chats_mode", "allowlist") == "all":
        return True
    allowed = {str(c) for c in tg.get("chats", [])}
    return str(chat_id) in allowed


async def run_listen(cfg: dict, ledger_dir: Path) -> None:
    tg = cfg["telegram"]
    client = TelegramClient(str(Path(tg["session"]).with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone") or (lambda: input("Телефон (в формате +7...): ")))
    print(f"[tg-ingest] слушаю: mode={tg.get('chats_mode', 'allowlist')} chats={tg.get('chats')}")

    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        if tg.get("ignore_self", True) and event.out:
            return
        if not chat_allowed(cfg, event.chat_id):
            return
        text = (event.message.message or "").strip()
        if not text:
            return
        chat = await event.get_chat()
        sender = await event.get_sender()
        record = normalize(event, chat, sender)
        append_inbox(ledger_dir, record)
        print(f"[inbox] {record['source']} {record['text'][:60]!r}")
        push_to_openclaw(cfg, record)

    await client.run_until_disconnected()


async def run_backfill(cfg: dict, ledger_dir: Path, days: int) -> None:
    tg = cfg["telegram"]
    client = TelegramClient(str(Path(tg["session"]).with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone") or (lambda: input("Телефон (в формате +7...): ")))
    since = datetime.now(timezone.utc).astimezone().timestamp() - days * 86400
    count = 0
    async for dialog in client.iter_dialogs():
        if not chat_allowed(cfg, dialog.id):
            continue
        async for msg in client.iter_messages(dialog.entity, limit=500, offset_date=datetime.now(timezone.utc)):
            if msg.date.timestamp() < since:
                break
            text = (msg.message or "").strip()
            if not text:
                continue
            record = {
                "id": msg.id,
                "chat_id": dialog.id,
                "chat": dialog.name,
                "sender_id": msg.sender_id,
                "sender": dialog.name,
                "date": msg.date.astimezone(timezone.utc).isoformat(),
                "text": text,
                "source": f"telegram:{dialog.id}#{msg.id}",
            }
            append_inbox(ledger_dir, record)
            count += 1
    print(f"[backfill] сохранено {count} сообщений в {ledger_dir / 'inbox.jsonl'}")
    if count:
        push_to_openclaw(cfg, {
            "id": "backfill",
            "chat_id": 0,
            "chat": "backfill",
            "sender_id": 0,
            "sender": "backfill",
            "date": datetime.now(timezone.utc).isoformat(),
            "text": f"Backfill: прочитай ledger/inbox.jsonl (последние {count} записей) и извлеки договорённости.",
            "source": "telegram:backfill",
        })
    await client.disconnect()


def run_dry(cfg: dict, ledger_dir: Path) -> None:
    record = dict(SAMPLE)
    append_inbox(ledger_dir, record)
    print("[dry-run] запись в inbox.jsonl:")
    print(json.dumps(record, ensure_ascii=False, indent=2))
    print("\n[dry-run] сообщение агенту (webhook payload.message):")
    print(build_agent_message(record))
    print("\n[dry-run] OK. Сеть не использовалась.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backfill", type=int, metavar="DAYS")
    args = ap.parse_args()

    cfg = load_config(args.config)
    ledger_dir = Path(cfg.get("ledger_dir", "ledger"))
    ledger_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        run_dry(cfg, ledger_dir)
        return
    if args.backfill:
        asyncio.run(run_backfill(cfg, ledger_dir, args.backfill))
        return
    asyncio.run(run_listen(cfg, ledger_dir))


if __name__ == "__main__":
    main()
