import asyncio, json
from pathlib import Path
from telethon import TelegramClient

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")

async def main():
    tg = json.loads(CFG.read_text(encoding="utf-8-sig"))["telegram"]
    client = TelegramClient(str(Path(tg["session"]).with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone"))
    dialogs = await client.get_dialogs()
    print(f"total_dialogs={len(dialogs)}")
    for d in dialogs:
        e = d.entity
        phone = getattr(e, "phone", None) or ""
        uname = getattr(e, "username", None) or ""
        print(f"id={d.id} name={d.name!r} phone={phone} user={uname} kind={type(e).__name__}")
    await client.disconnect()

asyncio.run(main())
