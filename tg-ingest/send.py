"""Send a Telegram message to a chat via the saved MTProto session.

One-click send target: the agent runs this after the owner approves a draft.

Usage:
  python send.py --config config.json --chat "@username" --text "message"
  python send.py --config config.json --chat 777000 --text "message" --dry-run
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from telethon import TelegramClient


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        sys.exit(f"Config not found: {p}")
    return json.loads(p.read_text(encoding="utf-8-sig"))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--chat", required=True, help="@username or numeric chat id")
    ap.add_argument("--text", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(f"[dry-run] to={args.chat} text={args.text!r}")
        return

    tg = load_config(args.config)["telegram"]
    client = TelegramClient(str(Path(tg["session"]).with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone") or (lambda: input("Телефон (в формате +7...): ")))
    entity = int(args.chat) if str(args.chat).lstrip("-").isdigit() else args.chat
    msg = await client.send_message(entity, args.text)
    print(f"sent: chat={args.chat} message_id={msg.id}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
