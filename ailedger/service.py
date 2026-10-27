"""What each request does, as plain functions.

The FastAPI app (app.py) and the in-browser engine (webapi.py, running under Pyodide) both call these, so the two can never
disagree. A "state" is anything with `.ds` (the dataset) and `.assumptions` (the settings); the caller owns it.
Nothing here imports FastAPI or the OpenAI client.
"""
from __future__ import annotations

import csv
import io
from dataclasses import replace

from . import analysis as an
from . import bench, data, rules, sources

MAX_UPLOAD = 5_000_000  # bytes of CSV


class ServiceError(Exception):
    """A request the tool refuses, with the HTTP status it maps to and a plain message."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


_DEFAULT: data.Dataset | None = None


def default_dataset() -> data.Dataset:
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = data.generate()
    return _DEFAULT


def departments(st) -> list[str]:
    return sorted({r["department"] for r in st.ds.rows})


def report(st) -> dict:
    a = st.assumptions
    return dict(summary=an.summary(st.ds, a), policies=an.compare_policies(st.ds, a),
                budgets=an.budget_recommendations(st.ds, a), waste=an.waste(st.ds, a), plan=an.plan_savings(st.ds, a),
                output_index=an.output_index(st.ds, a), actions=an.actions(st.ds, a), routing=an.routing(st.ds, a),
                trend=an.trend(st.ds, a.drift_alert, a.drift_min_dollars), validation=an.validate(st.ds, a),
                policy_assumptions=an.POLICY_ASSUMPTIONS, ppu_breakeven=an.pay_per_use_breakeven(st.ds, a),
                value=an.value_info(st.ds, a),
                unit_names={d: an.unit_label(st.ds, a, d) for d in departments(st)}, rows=len(st.ds.rows))


def get_sources(st) -> dict:
    return sources.registry(st.assumptions)


def evidence(st) -> dict:
    return bench.bundle(st.ds, st.assumptions)


def perception(st, pct: float) -> dict:
    if not (-100 <= pct <= 500):
        raise ServiceError(422, "percentage out of range")
    return bench.perception(st.ds, st.assumptions, pct)


def robustness(st) -> dict:
    return an.robustness(st.ds, st.assumptions)


def get_value(st) -> dict:
    return an.value_info(st.ds, st.assumptions)


def set_value(st, defs: dict) -> dict:
    """Set how this session values AI output. An empty object goes back to hours x hourly rate from the data."""
    import json
    try:
        clean = an.validate_value_defs(defs, departments(st), an.metrics_by_dept(st.ds))
    except ValueError as e:
        raise ServiceError(422, str(e))
    st.assumptions = replace(st.assumptions, value_json=json.dumps(clean, sort_keys=True) if clean else "")
    return report(st)


def get_rules(st) -> dict:
    return rules.info(st.assumptions, departments(st))


def set_rules(st, values: dict, routine: dict | None, reset: bool) -> dict:
    """Change the tool's judgement calls. Bad values are refused; risky ones come back as warnings."""
    d0 = an.Assumptions()
    if reset:
        st.assumptions = replace(st.assumptions, **{r["field"]: getattr(d0, r["field"]) for r in rules.RULES}, routine_json="")
        return report(st) | dict(rule_warnings=[])
    months = len({r["month"] for r in st.ds.rows})
    try:
        changes, warnings = rules.validate(values, routine, st.assumptions, departments(st), months)
    except ValueError as e:
        raise ServiceError(422, str(e))
    st.assumptions = replace(st.assumptions, **changes)
    return report(st) | dict(rule_warnings=warnings)


def explain(st, department: str = "") -> dict:
    return dict(department=an.explain(st.ds, st.assumptions, department or None),
                policies=an.explain_policies(st.ds, st.assumptions))


def set_assumptions(st, realization: float, elasticity: float, cheap_price_per_m: float, ppu_multiplier: float) -> dict:
    if not (0.05 <= realization <= 1 and 0.1 <= elasticity <= 1 and 0.0 <= cheap_price_per_m <= 5.0
            and 0.5 <= ppu_multiplier <= 6.0):
        raise ServiceError(422, "assumption out of range")
    st.assumptions = replace(st.assumptions, realization=realization, elasticity=elasticity,
                             cheap_price_per_m=cheap_price_per_m, ppu_multiplier=ppu_multiplier)  # keeps your value definition
    return report(st)


def upload(st, text: str) -> dict:
    if len(text.encode("utf-8")) > MAX_UPLOAD:
        raise ServiceError(413, "CSV larger than 5 MB")
    try:
        st.ds = data.load_csv(text)
        st.assumptions = replace(st.assumptions, value_json="", routine_json="")  # keyed to the old departments: would mislead
    except (ValueError, KeyError) as e:
        raise ServiceError(422, str(e))
    return report(st)


def reset(st) -> dict:
    st.ds = default_dataset()
    st.assumptions = an.Assumptions()
    return report(st)


def actions_csv(st, ids: str = "") -> str:
    """The approved actions as CSV. `ids` is a comma list of action ids the user ticked."""
    want = {int(x) for x in ids.split(",") if x.strip().isdigit()}
    rows = [r for r in an.actions(st.ds, st.assumptions) if not want or r["id"] in want]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["action", "department", "level", "people", "monthly_saving", "reason"])
    for r in rows:
        w.writerow([r["kind"], r["department"], r["level"], r["people"], r["monthly_saving"], r["reason"]])
    return buf.getvalue()


def sample_csv() -> str:
    return default_dataset().to_csv()


def is_default(st) -> bool:
    """True while the session still has the demo company and the default settings (recorded answers apply)."""
    return st.ds is default_dataset() and st.assumptions == an.Assumptions()
