import asyncio, json, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from telethon import TelegramClient

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")
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
    dialogs = await client.get_dialogs()
    for d in dialogs:
        if not d.is_user or d.date < DAY_START:
            continue
        msgs = []
        async for m in client.iter_messages(d.id, limit=50):
            if m.date < DAY_START:
                break
            if not m.out:
                msgs.append(m)
        if not msgs:
            continue
        e = d.entity
        phone = getattr(e, "phone", None) or "-"
        uname = getattr(e, "username", None) or "-"
        print(f"CHAT: {d.name!r} id={d.id} phone={phone} user={uname} today_in={len(msgs)}")
        for m in reversed(msgs):
            t = m.date.astimezone(MSK).strftime("%H:%M")
            text = (m.text or "").replace("\n", " / ")[:250]
            kind = " media:" + type(m.media).__name__ if m.media else ""
            print(f"  [{t}] {text}{kind}")
    await client.disconnect()

asyncio.run(main())
