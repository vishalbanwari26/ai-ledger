from __future__ import annotations

import json
import os
import secrets
import time
from collections import OrderedDict, deque
from dataclasses import replace
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import analysis as an
from . import data
from . import bench
from . import evidence as ev
from . import rules
from . import sources
from .llm import Analyst

STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_SESSIONS = int(os.environ.get("LEDGER_MAX_SESSIONS", "200"))
LLM_PER_HOUR = int(os.environ.get("LEDGER_LLM_PER_HOUR", "120"))  # global cap: a public demo spends real credits
MAX_UPLOAD = 5_000_000
app = FastAPI(title="AI Ledger")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Each visitor gets their own dataset and assumptions, keyed by a cookie, so one person's CSV upload
# or slider change never alters what another visitor sees. Oldest sessions are evicted past the cap.
sessions: OrderedDict[str, Analyst] = OrderedDict()
_default_ds = data.generate()
_llm_calls: deque[float] = deque()


def get_state(request: Request, response: Response) -> Analyst:
    sid = request.cookies.get("sid")
    if sid not in sessions:
        sid = secrets.token_urlsafe(16)
        sessions[sid] = Analyst(ds=_default_ds)
        while len(sessions) > MAX_SESSIONS:
            sessions.popitem(last=False)
    sessions.move_to_end(sid)
    response.set_cookie("sid", sid, httponly=True, samesite="lax", max_age=86400)
    return sessions[sid]


class Ask(BaseModel):
    question: str


class Params(BaseModel):
    realization: float = 0.5
    elasticity: float = 0.5
    cheap_price_per_m: float = 0.6
    ppu_multiplier: float = 1.6


def _report(st: Analyst) -> dict:
    a = st.assumptions
    return dict(summary=an.summary(st.ds, a), policies=an.compare_policies(st.ds, a),
                budgets=an.budget_recommendations(st.ds, a), waste=an.waste(st.ds, a), plan=an.plan_savings(st.ds, a), output_index=an.output_index(st.ds, a),
                actions=an.actions(st.ds, a), routing=an.routing(st.ds, a), trend=an.trend(st.ds, a.drift_alert, a.drift_min_dollars),
                validation=an.validate(st.ds, a), policy_assumptions=an.POLICY_ASSUMPTIONS, ppu_breakeven=an.pay_per_use_breakeven(st.ds, a),
                value=an.value_info(st.ds, a),
                unit_names={d: an.unit_label(st.ds, a, d) for d in sorted({r["department"] for r in st.ds.rows})}, rows=len(st.ds.rows))


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/report")
def report(request: Request, response: Response):
    return _report(get_state(request, response))


@app.get("/api/sources")
def get_sources(request: Request, response: Response):
    return sources.registry(get_state(request, response).assumptions)


@app.get("/api/evidence")
def evidence(request: Request, response: Response):
    st = get_state(request, response)
    return bench.bundle(st.ds, st.assumptions)


@app.get("/api/perception")
def perception(request: Request, response: Response, pct: float):
    st = get_state(request, response)
    if not (-100 <= pct <= 500):
        raise HTTPException(422, "percentage out of range")
    return bench.perception(st.ds, st.assumptions, pct)


@app.get("/api/robustness")
def robustness(request: Request, response: Response):
    st = get_state(request, response)
    return an.robustness(st.ds, st.assumptions)


class ValueBody(BaseModel):
    defs: dict = {}


@app.get("/api/value")
def get_value(request: Request, response: Response):
    st = get_state(request, response)
    return an.value_info(st.ds, st.assumptions)


@app.post("/api/value")
def set_value(body: ValueBody, request: Request, response: Response):
    """Set how this session values AI output. An empty object goes back to hours x hourly rate from the data."""
    st = get_state(request, response)
    depts = sorted({r["department"] for r in st.ds.rows})
    try:
        clean = an.validate_value_defs(body.defs, depts, an.metrics_by_dept(st.ds))
    except ValueError as e:
        raise HTTPException(422, str(e))
    st.assumptions = replace(st.assumptions, value_json=json.dumps(clean, sort_keys=True) if clean else "")
    return _report(st)


class RulesBody(BaseModel):
    values: dict = {}
    routine: dict | None = None
    reset: bool = False


def _depts(st: Analyst) -> list[str]:
    return sorted({r["department"] for r in st.ds.rows})


@app.get("/api/rules")
def get_rules(request: Request, response: Response):
    st = get_state(request, response)
    return rules.info(st.assumptions, _depts(st))


@app.post("/api/rules")
def set_rules(body: RulesBody, request: Request, response: Response):
    """Change the tool's judgement calls for this session. Bad values are refused; risky ones come back as warnings."""
    st = get_state(request, response)
    d0 = an.Assumptions()
    if body.reset:
        st.assumptions = replace(st.assumptions, **{r["field"]: getattr(d0, r["field"]) for r in rules.RULES}, routine_json="")
        return _report(st) | dict(rule_warnings=[])
    months = len({r["month"] for r in st.ds.rows})
    try:
        changes, warnings = rules.validate(body.values, body.routine, st.assumptions, _depts(st), months)
    except ValueError as e:
        raise HTTPException(422, str(e))
    st.assumptions = replace(st.assumptions, **changes)
    return _report(st) | dict(rule_warnings=warnings)


@app.get("/api/explain")
def explain(request: Request, response: Response, department: str = ""):
    st = get_state(request, response)
    return dict(department=an.explain(st.ds, st.assumptions, department or None),
                policies=an.explain_policies(st.ds, st.assumptions))


@app.post("/api/assumptions")
def set_assumptions(p: Params, request: Request, response: Response):
    st = get_state(request, response)
    if not (0.05 <= p.realization <= 1 and 0.1 <= p.elasticity <= 1 and 0.0 <= p.cheap_price_per_m <= 5.0
            and 0.5 <= p.ppu_multiplier <= 6.0):
        raise HTTPException(422, "assumption out of range")
    st.assumptions = replace(st.assumptions, realization=p.realization, elasticity=p.elasticity,
                             cheap_price_per_m=p.cheap_price_per_m, ppu_multiplier=p.ppu_multiplier)  # keeps your value definition
    return _report(st)


@app.post("/api/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...)):
    st = get_state(request, response)
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "CSV larger than 5 MB")
    try:
        st.ds = data.load_csv(raw.decode("utf-8-sig"))
        st.assumptions = replace(st.assumptions, value_json="", routine_json="")  # keyed to the old departments: would mislead
    except (ValueError, KeyError, UnicodeDecodeError) as e:
        raise HTTPException(422, str(e))
    return _report(st)


@app.post("/api/reset")
def reset(request: Request, response: Response):
    st = get_state(request, response)
    st.ds = _default_ds
    st.assumptions = an.Assumptions()
    return _report(st)


@app.get("/api/actions.csv")
def actions_csv(request: Request, response: Response, ids: str = ""):
    """Download the approved actions. `ids` is a comma list of action ids the user ticked."""
    st = get_state(request, response)
    want = {int(x) for x in ids.split(",") if x.strip().isdigit()}
    rows = [r for r in an.actions(st.ds, st.assumptions) if not want or r["id"] in want]
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["action", "department", "level", "people", "monthly_saving", "reason"])
    for r in rows:
        w.writerow([r["kind"], r["department"], r["level"], r["people"], r["monthly_saving"], r["reason"]])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ai-ledger-actions.csv"})


@app.get("/api/sample.csv")
def sample():
    return PlainTextResponse(_default_ds.to_csv(), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ai-ledger-sample.csv"})


def _llm(fn, *args):
    now = time.time()
    while _llm_calls and now - _llm_calls[0] > 3600:
        _llm_calls.popleft()
    if len(_llm_calls) >= LLM_PER_HOUR:
        raise HTTPException(429, "The demo's hourly model budget is used up. Try again later or run it locally.")
    _llm_calls.append(now)
    try:
        return fn(*args)
    except RuntimeError as e:  # missing key / no model
        raise HTTPException(503, str(e))
    except Exception as e:  # upstream API errors
        raise HTTPException(502, f"{type(e).__name__}: {e}")


@app.post("/api/ask")
def ask(body: Ask, request: Request, response: Response):
    st = get_state(request, response)
    q = body.question.strip()
    if not q:
        raise HTTPException(422, "empty question")
    if len(q) > 500:
        raise HTTPException(422, "question longer than 500 characters")
    return _llm(st.ask, q)


@app.get("/api/brief")
def brief(request: Request, response: Response):
    return _llm(get_state(request, response).brief)
