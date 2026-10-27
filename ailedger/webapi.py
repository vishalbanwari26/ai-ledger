"""The engine as it runs in the browser (Pyodide). No server, no FastAPI, no OpenAI client.

`handle` answers the same routes as the server, in-process, for one visitor's session. The page's JavaScript makes the
HTTP call to Token Factory (with the visitor's own key) and uses the helpers below around it, so the prompt, tools,
guardrails and model choice are the same Python code the server uses.
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from . import agent
from . import analysis as an
from . import service
from .service import ServiceError

STATE = SimpleNamespace(ds=service.default_dataset(), assumptions=an.Assumptions())


def _q(query: dict, key: str, default: str = "") -> str:
    return query.get(key, [default])[0]


def _route(method: str, path: str, query: dict, body: dict):
    st = STATE
    if method == "GET":
        if path == "/api/report":
            return service.report(st)
        if path == "/api/sources":
            return service.get_sources(st)
        if path == "/api/evidence":
            return service.evidence(st)
        if path == "/api/robustness":
            return service.robustness(st)
        if path == "/api/value":
            return service.get_value(st)
        if path == "/api/rules":
            return service.get_rules(st)
        if path == "/api/explain":
            return service.explain(st, _q(query, "department"))
        if path == "/api/perception":
            try:
                return service.perception(st, float(_q(query, "pct", "nan")))
            except ValueError:
                raise ServiceError(422, "enter a number")
        if path == "/api/sample.csv":
            return {"__text__": service.sample_csv()}
        if path == "/api/actions.csv":
            return {"__text__": service.actions_csv(st, _q(query, "ids"))}
    if method == "POST":
        if path == "/api/assumptions":
            return service.set_assumptions(st, float(body.get("realization", 0.5)), float(body.get("elasticity", 0.5)),
                                           float(body.get("cheap_price_per_m", 0.6)), float(body.get("ppu_multiplier", 1.6)))
        if path == "/api/value":
            return service.set_value(st, body.get("defs", {}))
        if path == "/api/rules":
            return service.set_rules(st, body.get("values", {}), body.get("routine"), bool(body.get("reset", False)))
        if path == "/api/upload":
            return service.upload(st, str(body.get("text", "")))
        if path == "/api/reset":
            return service.reset(st)
    return None


def handle(method: str, url: str, body_json: str = "") -> str:
    """Answer one request. Returns JSON: {"status": 200, "json": ...} or {"status": 200, "text": ...} for CSV."""
    parsed = urlparse(url)
    try:
        body = json.loads(body_json) if body_json else {}
        out = _route(method.upper(), parsed.path, parse_qs(parsed.query), body)
    except ServiceError as e:
        return json.dumps({"status": e.status, "json": {"detail": e.message}})
    except Exception as e:  # a bug must not freeze the page
        return json.dumps({"status": 500, "json": {"detail": f"{type(e).__name__}: {e}"}})
    if out is None:
        return json.dumps({"status": 404, "json": {"detail": f"no route {method} {parsed.path}"}})
    if isinstance(out, dict) and "__text__" in out:
        return json.dumps({"status": 200, "text": out["__text__"]})
    return json.dumps({"status": 200, "json": out})


# ---- helpers for the browser-side analyst loop ---------------------------------------------------------------------

def is_default() -> bool:
    """True while the visitor still has the demo company and default settings (recorded answers apply)."""
    return service.is_default(STATE)


def ask_setup(question: str) -> str:
    targeted = agent.asks_about_individuals(question)
    return json.dumps(dict(targeted=targeted, question=agent.reframe(question) if targeted else question,
                           system=agent.SYSTEM, tools=agent.TOOLS, prefix=agent.INDIVIDUALS_PREFIX))


def run_tool_json(name: str, args_json: str) -> str:
    return json.dumps(agent.run_tool(STATE.ds, STATE.assumptions, name, json.loads(args_json or "{}")))


def blames(text: str) -> bool:
    return agent.blames(text)


def strip_think(text: str) -> str:
    return agent.strip_think(text)


def repair_messages(answer: str) -> str:
    return json.dumps([{"role": "system", "content": agent.SYSTEM}, {"role": "user", "content": agent.REPAIR_PROMPT + answer}])


def safe_summary() -> str:
    return agent.safe_summary(STATE.ds, STATE.assumptions)


def brief_messages_json() -> str:
    return json.dumps(agent.brief_messages(STATE.ds, STATE.assumptions))


def pick_models_json(ids_json: str) -> str:
    return json.dumps(agent.pick_models(json.loads(ids_json)))
