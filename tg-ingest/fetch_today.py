"""Fetch today's messages from a chat matched by phone number or name."""
import asyncio, sys, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from telethon import TelegramClient

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")
PHONE = "998938499656"
MSK = timezone(timedelta(hours=3))
DAY_START = datetime(2026, 11, 22, 0, 0, tzinfo=MSK)

async def main():
    tg = json.loads(CFG.read_text(encoding="utf-8-sig"))["telegram"]
    client = TelegramClient(str(Path(tg["session"]).with_suffix("")), int(tg["api_id"]), tg["api_hash"])
    await client.start(phone=tg.get("phone"))
    dialogs = await client.get_dialogs()
    matched = []
    for d in dialogs:
        e = d.entity
        if not getattr(e, "bot", False):
            phone = getattr(e, "phone", None) or ""
            name = ((getattr(e, "first_name", "") or "") + " " + (getattr(e, "last_name", "") or "") + " " + (d.name or "")).lower()
            if PHONE in phone or "akk" in name:
                matched.append(d)
    if not matched:
        print("NO_MATCH: dialogs=" + json.dumps([d.name for d in dialogs[:40]], ensure_ascii=False))
        return
    for d in matched:
        e = d.entity
        print(f"MATCH: name={d.name!r} id={d.id} phone={getattr(e,'phone',None)} username={getattr(e,'username',None)}")
        n = 0
        async for m in client.iter_messages(d.id, limit=100):
            if m.date < DAY_START:
                break
            if m.out:
                continue
            n += 1
            t = m.date.astimezone(MSK).strftime("%H:%M")
            who = (m.sender.first_name or "") if m.sender else "?"
            text = (m.text or "").replace("\n", " / ")[:300]
            kind = "media:" + type(m.media).__name__ if m.media else ""
            print(f"  [{t}] {who}: {text} {kind}".rstrip())
        print(f"  total_incoming_today={n}")
    await client.disconnect()

asyncio.run(main())
