"""The tool's judgement calls, as settings you can change.

Each rule has a label, a type, limits, and a link to its entry in the source registry. Changing one never fails silently:
out-of-range values are refused with a message, and risky-but-allowed values return a plain warning that says what the
stress tests found. The minimum group size can be raised but never lowered below 10, so no figure can point at one person.
"""
from __future__ import annotations

import dataclasses
import json

from . import analysis as an

PRIVACY_FLOOR = 10

# type: number | int | pct (stored as a fraction, shown as a percent) | money | bool
RULES: list[dict] = [
    dict(field="idle_sessions", group="Finding waste", label="A seat counts as unused below this many sessions a month",
         type="number", min=0, max=50, step=1, ref="idle_sessions"),
    dict(field="high_spend_mult", group="Finding waste", label="A seat is high spend above this multiple of its peers' median spend",
         type="number", min=1.1, max=10, step=0.1, ref="high_spend"),
    dict(field="peer_percentile", group="Finding waste", label="Token caps follow this percentile of ROI-positive peers' spend",
         type="pct", min=0.5, max=0.99, step=0.01, ref="peer_percentile"),
    dict(field="min_cohort", group="Finding waste", label="Smallest peer group compared on its own (people)",
         type="int", min=3, max=50, step=1, ref="min_cohort"),
    dict(field="pre_months", group="Measuring the effect", label="Baseline months (before rollout)",
         type="int", min=1, max=6, step=1, ref="windows"),
    dict(field="window_months", group="Measuring the effect", label="Measured months (the latest months)",
         type="int", min=1, max=12, step=1, ref="windows"),
    dict(field="adjust_pretrend", group="Measuring the effect", label="Remove a growth gap adopters already had before rollout",
         type="bool", ref="pretrend"),
    dict(field="seat_savings_realized", group="Money", label="Share of a reclaimed seat's cost actually saved",
         type="pct", min=0.0, max=1.0, step=0.05, ref="seat_savings_realized"),
    dict(field="ppu_friction", group="Money", label="Value lost because people ration metered use (pay per use)",
         type="pct", min=0.0, max=0.9, step=0.01, ref="ppu_friction"),
    dict(field="quality_penalty", group="Money", label="Value lost on tokens moved to the cheaper model",
         type="pct", min=0.0, max=0.5, step=0.01, ref="quality_penalty"),
    dict(field="fixed_cap", group="Money", label="Token cap in the fixed-budget policy ($ per person a month)",
         type="money", min=0, max=100000, step=5, ref="fixed_cap"),
    dict(field="drift_alert", group="Alerts", label="Raise a drift alert when a department's monthly spend jumps by",
         type="pct", min=0.02, max=5.0, step=0.01, ref="drift"),
    dict(field="drift_min_dollars", group="Alerts", label="... and the jump is at least ($)",
         type="money", min=0, max=10_000_000, step=50, ref="drift"),
    dict(field="min_group", group="Privacy", label=f"Smallest group ever shown (people). Can be raised; never below {PRIVACY_FLOOR}",
         type="int", min=PRIVACY_FLOOR, max=200, step=1, ref="min_group"),
]
BY_FIELD = {r["field"]: r for r in RULES}


def info(a: an.Assumptions, departments: list[str]) -> dict:
    d0 = an.Assumptions()
    rules = [dict(r, current=getattr(a, r["field"]), default=getattr(d0, r["field"])) for r in RULES]
    shares, base = an.routine_shares(a), an.ROUTINE_SHARE
    routine = [dict(department=d, current=shares.get(d, 0.5), default=base.get(d, 0.5)) for d in departments]
    return dict(rules=rules, routine=routine, privacy_floor=PRIVACY_FLOOR,
                customized=any(r["current"] != r["default"] for r in rules) or bool(a.routine_json))


def _num(field: str, v: object) -> float:
    try:
        x = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValueError(f"{BY_FIELD[field]['label']}: enter a number.")
    if x != x:
        raise ValueError(f"{BY_FIELD[field]['label']}: enter a number.")
    return x


def validate(values: dict, routine: dict | None, a: an.Assumptions, departments: list[str], months: int) -> tuple[dict, list[str]]:
    """Return (changes to apply, warnings). Raises ValueError with a plain message for anything out of range."""
    out: dict = {}
    for field, v in values.items():
        if field not in BY_FIELD:
            raise ValueError(f"Unknown rule: {field}")
        r = BY_FIELD[field]
        if r["type"] == "bool":
            if not isinstance(v, bool):
                raise ValueError(f"{r['label']}: must be on or off.")
            out[field] = v
            continue
        x = _num(field, v)
        if not (r["min"] <= x <= r["max"]):
            low = f"{r['min'] * 100:g}%" if r["type"] == "pct" else f"{r['min']:g}"
            high = f"{r['max'] * 100:g}%" if r["type"] == "pct" else f"{r['max']:g}"
            raise ValueError(f"{r['label']}: must be between {low} and {high}.")
        out[field] = int(round(x)) if r["type"] == "int" else x
    if routine is not None:
        if not isinstance(routine, dict):
            raise ValueError("Routine shares must be an object keyed by department.")
        clean = {}
        for d, v in routine.items():
            if d not in departments:
                raise ValueError(f"Unknown department in routine shares: {d}")
            try:
                x = float(v)
            except (TypeError, ValueError):
                raise ValueError(f"Routine share for {d} must be a number.")
            if not (0.0 <= x <= 1.0):
                raise ValueError(f"Routine share for {d} must be between 0% and 100%.")
            clean[d] = x
        out["routine_json"] = json.dumps(clean, sort_keys=True) if clean else ""
    merged = dataclasses.replace(a, **out)
    if merged.pre_months + merged.window_months > months:
        raise ValueError(f"Baseline ({merged.pre_months}) plus measured ({merged.window_months}) months is more than the {months} months in the data.")
    warnings: list[str] = []
    if merged.window_months < 3:
        warnings.append("A measured window under 3 months overstated the effect by about 2.9 points in the stress tests: one month of leave can decide the result.")
    if merged.pre_months < 2:
        warnings.append("With one baseline month the pre-rollout check cannot run, so a self-selection bias would go undetected.")
    if not merged.adjust_pretrend:
        warnings.append("Without the pre-rollout adjustment, adopters who were already growing faster will be credited to AI.")
    if merged.high_spend_mult < 1.3:
        warnings.append("A high-spend multiple this low will flag many ordinary seats. Treat the list as a place to start a conversation.")
    if merged.idle_sessions > 10:
        warnings.append("Above about 10 sessions a month, genuinely light users are treated as unused and lose their seats in the plan.")
    if merged.peer_percentile < 0.6:
        warnings.append("A low peer percentile sets tight caps: productive heavy users will sit above them.")
    return out, warnings
