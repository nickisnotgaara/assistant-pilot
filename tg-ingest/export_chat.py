import asyncio, json, shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from telethon import TelegramClient

CFG = Path(r"C:/Users/User/Desktop/openclaw-pilot/tg-ingest/config.json")
MSK = timezone(timedelta(hours=3))
SEARCH = ["bestbroctopus", "алёнка", "аленка", "al", "998935172313"]

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

    target = None
    dialogs = await client.get_dialogs()
    for d in dialogs:
        name = (d.name or "").lower()
        phone = getattr(d.entity, "phone", None) or ""
        uname = getattr(d.entity, "username", None) or ""
        hay = name + " " + phone + " " + uname.lower()
        if "bestbroctopus" in hay or "998935172313" in phone:
            target = d
            break
    if target is None:
        print("NOT_FOUND")
        await client.disconnect()
        return

    print("found:", target.name, target.id)
    lines = []
    total = 0
    async for m in client.iter_messages(target.id, reverse=True):
        total += 1
        t = m.date.astimezone(MSK).strftime("%Y-%m-%d %H:%M")
        arrow = "->" if m.out else "<-"
        who = "я" if m.out else ((m.sender.first_name or "?") if m.sender else "?")
        text = (m.text or "").replace(chr(10), " / ")
        if not text:
            kind = type(m.media).__name__ if m.media else "empty"
            text = "[" + kind + "]"
        lines.append(f"{t} | {arrow} | {who} | {text}")

    out = Path(r"C:/Users/User/.openclaw/workspace/alenka-history.txt")
    header = f"Переписка с {target.name} (id {target.id}) | сообщений: {total}\n"
    out.write_text(header + chr(10).join(lines), encoding="utf-8")
    print("messages:", total, "saved:", out)
    await client.disconnect()

asyncio.run(main())
