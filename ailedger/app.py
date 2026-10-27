from __future__ import annotations

import os
import secrets
import time
from collections import OrderedDict, deque
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import service
from .llm import Analyst
from .service import MAX_UPLOAD, ServiceError  # noqa: F401  (MAX_UPLOAD is also read by the tests)

STATIC = Path(__file__).resolve().parent.parent / "static"
MAX_SESSIONS = int(os.environ.get("LEDGER_MAX_SESSIONS", "200"))
LLM_PER_HOUR = int(os.environ.get("LEDGER_LLM_PER_HOUR", "120"))  # global cap: a public demo spends real credits
app = FastAPI(title="AI Ledger")
app.mount("/static", StaticFiles(directory=STATIC), name="static")

# Each visitor gets their own dataset and assumptions, keyed by a cookie, so one person's CSV upload
# or slider change never alters what another visitor sees. Oldest sessions are evicted past the cap.
sessions: OrderedDict[str, Analyst] = OrderedDict()
_default_ds = service.default_dataset()
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


def _run(fn, *args, **kw):
    """Call a service function; its refusals become the matching HTTP errors."""
    try:
        return fn(*args, **kw)
    except ServiceError as e:
        raise HTTPException(e.status, e.message)


class Ask(BaseModel):
    question: str


class Params(BaseModel):
    realization: float = 0.5
    elasticity: float = 0.5
    cheap_price_per_m: float = 0.6
    ppu_multiplier: float = 1.6


class ValueBody(BaseModel):
    defs: dict = {}


class RulesBody(BaseModel):
    values: dict = {}
    routine: dict | None = None
    reset: bool = False


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/report")
def report(request: Request, response: Response):
    return service.report(get_state(request, response))


@app.get("/api/sources")
def get_sources(request: Request, response: Response):
    return service.get_sources(get_state(request, response))


@app.get("/api/evidence")
def evidence(request: Request, response: Response):
    return service.evidence(get_state(request, response))


@app.get("/api/perception")
def perception(request: Request, response: Response, pct: float):
    return _run(service.perception, get_state(request, response), pct)


@app.get("/api/robustness")
def robustness(request: Request, response: Response):
    return service.robustness(get_state(request, response))


@app.get("/api/value")
def get_value(request: Request, response: Response):
    return service.get_value(get_state(request, response))


@app.post("/api/value")
def set_value(body: ValueBody, request: Request, response: Response):
    return _run(service.set_value, get_state(request, response), body.defs)


@app.get("/api/rules")
def get_rules(request: Request, response: Response):
    return service.get_rules(get_state(request, response))


@app.post("/api/rules")
def set_rules(body: RulesBody, request: Request, response: Response):
    return _run(service.set_rules, get_state(request, response), body.values, body.routine, body.reset)


@app.get("/api/explain")
def explain(request: Request, response: Response, department: str = ""):
    return service.explain(get_state(request, response), department)


@app.post("/api/assumptions")
def set_assumptions(p: Params, request: Request, response: Response):
    return _run(service.set_assumptions, get_state(request, response), p.realization, p.elasticity,
                p.cheap_price_per_m, p.ppu_multiplier)


@app.post("/api/upload")
async def upload(request: Request, response: Response, file: UploadFile = File(...)):
    st = get_state(request, response)
    raw = await file.read(MAX_UPLOAD + 1)
    if len(raw) > MAX_UPLOAD:
        raise HTTPException(413, "CSV larger than 5 MB")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise HTTPException(422, str(e))
    return _run(service.upload, st, text)


@app.post("/api/reset")
def reset(request: Request, response: Response):
    return service.reset(get_state(request, response))


@app.get("/api/actions.csv")
def actions_csv(request: Request, response: Response, ids: str = ""):
    return PlainTextResponse(service.actions_csv(get_state(request, response), ids), media_type="text/csv",
                             headers={"Content-Disposition": "attachment; filename=ai-ledger-actions.csv"})


@app.get("/api/sample.csv")
def sample():
    return PlainTextResponse(service.sample_csv(), media_type="text/csv",
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
