"""Login to Telegram MTProto and save the session file.

Usage:
  python login.py --config config.json
  (вводишь код из Telegram; при включённом 2FA — пароль)

api_id / api_hash берутся на https://my.telegram.org -> API development tools.
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
        sys.exit(f"Config not found: {p}. Copy config.example.json -> config.json first.")
    return json.loads(p.read_text(encoding="utf-8-sig"))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    args = ap.parse_args()

    cfg = load_config(args.config)
    tg = cfg["telegram"]
    if not tg.get("api_id") or tg.get("api_hash", "").startswith("ваш"):
        sys.exit("Заполни telegram.api_id и telegram.api_hash в config.json (my.telegram.org).")

    session = Path(tg["session"])
    client = TelegramClient(str(session.with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    phone = tg.get("phone") or (lambda: input("Телефон (в формате +7...): "))
    await client.start(phone=phone)
    me = await client.get_me()
    print(f"OK: сессия сохранена в {session}")
    print(f"Аккаунт: {me.first_name} (@{me.username}) id={me.id}")
    print("Теперь запусти: python ingest.py --config config.json --dry-run")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
