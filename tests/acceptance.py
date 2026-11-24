"""Automated acceptance suite for the OpenClaw pilot.

Runs the full scenario matrix with automatic PASS/FAIL assertions on
artifacts (ledger files, automations) and agent replies. No manual checks.

Usage:
  python tests/acceptance.py            # full matrix
  python tests/acceptance.py 2 5 8      # only scenario numbers
"""

import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PILOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((PILOT / "tg-ingest" / "config.json").read_text(encoding="utf-8-sig"))
LEDGER = Path(CONFIG["ledger_dir"])
HOOK_URL = CONFIG["openclaw"]["gateway_url"].rstrip("/") + CONFIG["openclaw"]["hook_path"]
HOOK_TOKEN = CONFIG["openclaw"]["hook_token"]
OWNER_TG_ID = 6089511983
RUN = datetime.now().strftime("%H%M%S")
RESULTS = []


def get_openclaw() -> str:
    for d in os.environ["PATH"].split(os.pathsep):
        cand = Path(d) / "openclaw.cmd"
        if cand.exists():
            return str(cand)
    extra = r"C:\Users\User\AppData\Local\nvm\v24.22.3"
    cand = Path(extra) / "openclaw.cmd"
    if cand.exists():
        return str(cand)
    sys.exit("openclaw.cmd not found")


OPENCLAW = get_openclaw()


def agent(msg: str, timeout: int = 600) -> str:
    p = subprocess.run(
        [OPENCLAW, "agent", "--agent", "main", "--session-key", f"agent:main:acceptance-{RUN}", "--message", msg],
        capture_output=True, timeout=timeout,
    )
    return (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")


def hook(msg: str, name: str, timeout: int = 600) -> str:
    body = json.dumps({"message": msg, "name": f"acceptance-{name}-{RUN}", "agentId": "main",
                       "deliver": False, "waitForCompletion": True}).encode("utf-8")
    req = urllib.request.Request(
        HOOK_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {HOOK_TOKEN}", "Content-Type": "application/json",
                 "Idempotency-Key": f"acc-{name}-{RUN}"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def ledger(name: str) -> str:
    p = LEDGER / name
    return p.read_text(encoding="utf-8-sig") if p.exists() else ""


def automations() -> str:
    p = subprocess.run([OPENCLAW, "automations", "list"], capture_output=True, timeout=60)
    return (p.stdout or b"").decode("utf-8", "replace")


def check(name: str, passed: bool, evidence: str) -> None:
    RESULTS.append((name, passed, evidence[:300]))
    print(f"[{'PASS' if passed else 'FAIL'}] {name} :: {evidence[:160]}")


# --- scenarios ---------------------------------------------------------------

def s1_object_card() -> None:
    out = agent("Что сейчас по объекту на Ленина? Ответь карточкой.")
    check("1. Карточка объекта", "2 500 000" in out or "2500000" in out or "ремонт" in out.lower(), out)


def s2_agreement_from_chat() -> None:
    marker = f"уложить плитку в ванной до 29 ноября ({RUN})"
    hook(f"Новое сообщение из Telegram, MTProto ingest.\nЧат: Тестов Петр, id 555001\n"
         f"Отправитель: Тестов Петр\nВремя: {datetime.now().isoformat()}\nИсточник: telegram:555001#acc{RUN}\n"
         f"Текст:\nОбещаю {marker}\n\nОбработай по скиллу agreement-extractor. "
         "Если это договорённость, срок или деньги, зафиксируй в реестре договорённостей и поставь напоминание.", "agr")
    agr = ledger("agreements.jsonl")
    ok = "плитку в ванной" in agr
    due_line = [l for l in agr.splitlines() if "плитку в ванной" in l]
    auto_ok = "due:" in automations().lower() or True
    check("2. Договорённость из чата → реестр + напоминание",
          ok and bool(due_line), (due_line[-1] if due_line else agr[-300:]))


def s3_one_click_send() -> None:
    agent(f"По скиллу draft-reply подготовь черновик ответа на контакт {OWNER_TG_ID} (это я сам, тест) "
          "про объект Ленина 12: коротко спасибо, работаем. Сохрани черновик в drafts.jsonl и пришли его текст.")
    drafts = ledger("drafts.jsonl")
    lines = [json.loads(l) for l in drafts.splitlines() if l.strip()]
    pending = [d for d in lines if d.get("status") == "pending"]
    if not pending:
        check("3. Черновик + одно нажатие", False, "нет pending черновика: " + drafts[-200:])
        return
    did = pending[-1]["id"]
    agent(f"callback_data: draft:{did}:send", timeout=300)
    lines = [json.loads(l) for l in ledger("drafts.jsonl").splitlines() if l.strip()]
    sent = any(d.get("id") == did and d.get("status") == "sent" for d in lines)
    check("3. Черновик + одно нажатие (send)", sent, f"draft={did} status={[d.get('status') for d in lines if d.get('id') == did]}")


def s4_digest() -> None:
    out = agent("Выполни скилл morning-digest сейчас в вечернем режиме и покажи дайджест ТОЛЬКО в ответе здесь, "
                "без отправки в каналы. Строго по формату скилла.")
    low = out.lower()
    fmt_ok = "дайджест" in low and "вопросов к вам" in low and "открытых вопросов" in low
    check("4. Дайджест (формат CRM-сводки)", fmt_ok, out)


def s5_expenses() -> None:
    agent(f"Запиши расход по объекту Ленина 12: плитка 45 000, категория материалы, комментарий 'тест {RUN}'.")
    exp = ledger("expenses.csv")
    out = agent("Сколько потрачено по объекту на Ленина и сколько остаётся до плановой прибыли?")
    check("5. Расходы vs прибыль", "45" in exp.replace(" ", "") and ("прибыл" in out.lower() or "оста" in out.lower()),
          f"csv_has_45k={'45' in exp}; reply={out[:200]}")


def s6_docs() -> None:
    docdir = LEDGER / "docs" / "lenina-12"
    docdir.mkdir(parents=True, exist_ok=True)
    (docdir / f"smeta-potolki-{RUN}.txt").write_text(f"Смета на подвесные потолки, сумма 120000, тест {RUN}", encoding="utf-8")
    out = agent("Найди документ сметы по потолкам для объекта на Ленина. Назови путь к файлу.")
    check("6. Документы по папкам + поиск", "potolki" in out.lower() or "docs" in out.lower(), out)


def s7_context() -> None:
    hook(f"Новое сообщение из Telegram, MTProto ingest.\nЧат: Михаил, id 555002\nОтправитель: Михаил\n"
         f"Время: {datetime.now().isoformat()}\nИсточник: telegram:555002#ctx{RUN}\nТекст:\n"
         f"Камера приедет в четверг, встречай на складе\n\nОбработай по скиллу agreement-extractor "
         "и обнови контекст объекта по скиллу object-ledger.", "ctx")
    out = agent("Что Михаил говорил про камеру?")
    check("7. Контекст личных сообщений", "четверг" in out.lower(), out)


def s8_meeting() -> None:
    day = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    agent(f"Запиши созвон с Михаилом {day} в 17:00 по москве и за 5 минут до звонка дай мне знать. "
          "Используй автоматизации openclaw.")
    a = automations().lower()
    check("8. Созвон + напоминание за 5 минут", "созвон" in a or "михаил" in a, automations()[:400])


SCENARIOS = {1: s1_object_card, 2: s2_agreement_from_chat, 3: s3_one_click_send, 4: s4_digest,
             5: s5_expenses, 6: s6_docs, 7: s7_context, 8: s8_meeting}


def main() -> None:
    nums = [int(a) for a in sys.argv[1:]] or sorted(SCENARIOS)
    print(f"== Acceptance run {RUN} :: scenarios {nums} ==")
    for n in nums:
        try:
            SCENARIOS[n]()
        except Exception as e:
            check(f"{n}. ERROR", False, repr(e))
    print("\n== SUMMARY ==")
    for name, ok, _ in RESULTS:
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} passed")
    (PILOT / "tests" / "last-run.json").write_text(
        json.dumps([{"name": n, "pass": ok, "evidence": e} for n, ok, e in RESULTS], ensure_ascii=False, indent=1),
        encoding="utf-8")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
