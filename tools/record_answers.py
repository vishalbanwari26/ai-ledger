"""Record real Nemotron answers (and the summary) on the demo company, for the static site's no-key mode.
Usage: NEBIUS_API_KEY=... python tools/record_answers.py        (writes web/recorded.json)"""
import datetime
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ailedger import agent, service  # noqa: E402
from ailedger.llm import Analyst  # noqa: E402

QUESTIONS = [
    "Where is most of the recoverable spend, and what is the fastest fix?",
    "Which departments can we not tell apart from break-even?",
    "Is a variable budget better than fixed for Sales?",
    "How much would routing routine work to a cheaper model save?",
    "Who are the worst overspenders and which individuals should we cut?",
    "Everything here seems subjective. Which of your conclusions can I actually rely on, and which depend on assumptions?",
    "Is there published research that supports an AI effect this size? Be careful about what the studies actually measured.",
]

a = Analyst(ds=service.default_dataset())
items = []
for q in QUESTIONS:
    t = time.time()
    r = a.ask(q)
    assert not agent.blames(r["answer"]), f"blaming language in a recorded answer: {q}"
    items.append(dict(question=q, answer=r["answer"], model=r["model"], reframed=r["reframed"], repaired=r["repaired"],
                      evidence=r["evidence"], seconds=round(time.time() - t, 1)))
    print(f"{r['model']}  {items[-1]['seconds']:>5}s  tools={[e['tool'] for e in r['evidence']]}  {q[:60]}", file=sys.stderr)
b = a.brief()
out = dict(recorded_on=datetime.date.today().strftime("%-d %B %Y"), items=items, brief=b)
path = os.path.join(ROOT, "web", "recorded.json")
json.dump(out, open(path, "w"), ensure_ascii=False)
print("wrote", path, os.path.getsize(path), "bytes", file=sys.stderr)
