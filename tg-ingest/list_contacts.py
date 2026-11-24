import asyncio, json, shutil
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.contacts import GetContactsRequest

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")

def session_path(tg):
    src = Path(tg["session"])
    dst = Path(str(src.with_suffix("")) + "-ro-copy")
    try:
        shutil.copyfile(src, dst.with_suffix(".session"))
        return str(dst)
    except Exception:
        return str(src.with_suffix(""))

async def main():
    tg = json.loads(CFG.read_text(encoding="utf-8-sig"))["telegram"]
    client = TelegramClient(session_path(tg), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone"))
    res = await client(GetContactsRequest(hash=0))
    users = sorted(res.users, key=lambda u: ((u.first_name or "") + (u.last_name or "")).lower())
    lines = []
    for u in users:
        name = ((u.first_name or "") + " " + (u.last_name or "")).strip() or "-"
        phone = "+" + u.phone if u.phone else "-"
        uname = "@" + u.username if u.username else "-"
        lines.append(f"{name} | {phone} | {uname}")
    out = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/contacts.txt")
    out.write_text(f"contacts_total={len(users)}\n" + "\n".join(lines), encoding="utf-8")
    print(f"total={len(users)} saved={out}")
    await client.disconnect()

asyncio.run(main())
