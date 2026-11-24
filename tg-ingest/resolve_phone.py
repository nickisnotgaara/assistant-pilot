import asyncio, json, shutil, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from telethon import TelegramClient
from telethon.tl.functions.messages import CheckChatInviteRequest
from telethon.tl.functions.contacts import GetContactsRequest, ImportContactsRequest, DeleteContactsRequest
from telethon.tl.types import InputPhoneContact

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")
PHONE = "998938499656"
MSK = timezone(timedelta(hours=3))
DAY_START = datetime(2026, 11, 22, 0, 0, tzinfo=MSK)

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

    # 1) Is it an invite link?
    try:
        inv = await client(CheckChatInviteRequest(PHONE))
        print("INVITE:", type(inv).__name__, getattr(inv, "title", None) or getattr(getattr(inv, "chat", None), "title", None))
    except Exception as e:
        print("not an invite link:", type(e).__name__, str(e)[:120])

    # 2) Was the phone already a contact?
    before = await client(GetContactsRequest(hash=0))
    pre_ids = {u.id for u in before.users}

    # 3) Resolve phone via contact import
    res = await client(ImportContactsRequest([InputPhoneContact(client_id=0, phone="+" + PHONE, first_name="tmp-resolve", last_name="")]))
    users = res.users
    if not users:
        print("PHONE_NOT_FOUND: user with this phone is not on Telegram or hidden")
        return
    u = users[0]
    print(f"RESOLVED: id={u.id} name={(u.first_name or '') + ' ' + (u.last_name or '')!r} user={u.username} mutual_contact={u.mutual_contact}")

    # 4) Read today's incoming messages
    n = 0
    async for m in client.iter_messages(u.id, limit=100):
        if m.date < DAY_START:
            break
        if m.out:
            continue
        n += 1
        t = m.date.astimezone(MSK).strftime("%H:%M")
        text = (m.text or "").replace("\n", " / ")[:300]
        kind = " media:" + type(m.media).__name__ if m.media else ""
        print(f"  [{t}] {text}{kind}")
    print(f"total_incoming_today={n}")

    # 5) Clean up: remove contact if we added it
    if u.id not in pre_ids:
        await client(DeleteContactsRequest(id=[u]))
        print("cleanup: temp contact removed")
    await client.disconnect()

asyncio.run(main())
