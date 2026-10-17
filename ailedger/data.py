"""Synthetic company generator and CSV loader.

Every row is one employee-month. The schema is what a real company could export by joining its AI
vendor billing (cost, tokens, sessions) with its own work systems (outcome units) and HR data
(role, level, loaded hourly rate). There is deliberately no "baseline" column: the analysis
estimates the AI effect from the data itself, using people who did not adopt as the control group.

The generator also keeps hidden ground-truth labels (who is really a power user, who uses a lot without gaining output).
They never reach the analysis; they exist so tests can measure how well the analysis recovers them.
"""
from __future__ import annotations

import csv
import io
import random
import re
from dataclasses import dataclass, field

COLUMNS = [
    "employee_id", "department", "role", "level", "month", "seat_cost", "token_cost",
    "tokens", "sessions", "outcome_units", "hours_per_unit", "hourly_rate",
]
OPTIONAL = {"level": "mid"}

# department -> (role, outcome unit name, hours per unit, hourly rate for a mid-level, units/month for a mid-level)
ROLES = {
    "Engineering": ("Software Engineer", "PRs merged", 3.0, 85, 14),
    "Support": ("Support Agent", "tickets closed", 0.5, 38, 140),
    "Sales": ("Account Executive", "qualified opps", 4.0, 70, 9),
    "Marketing": ("Content Marketer", "assets shipped", 3.5, 55, 12),
    "Finance": ("Financial Analyst", "reports delivered", 5.0, 62, 8),
    "Legal": ("Legal Counsel", "contracts reviewed", 2.5, 120, 20),
}
UNIT_NAMES = {dept: v[1] for dept, v in ROLES.items()}

HEADCOUNT = {"Engineering": 640, "Support": 440, "Sales": 360, "Marketing": 200, "Finance": 180, "Legal": 80}
SEAT_COSTS = {"Engineering": 60.0, "Support": 40.0, "Sales": 40.0, "Marketing": 40.0, "Finance": 40.0, "Legal": 40.0}
# Token-use multiplier: engineers run agentic coding sessions, support runs agent-assisted replies.
TOKEN_MULT = {"Engineering": 8.0, "Support": 2.5, "Sales": 1.0, "Marketing": 1.5, "Finance": 1.0, "Legal": 1.2}

# Interns work on smaller, lower-stakes tasks: less output, lower rate, fewer tokens.
# lift: how much of the archetype's gain this level realizes. Calibrated to the published findings (docs/evidence.md):
# Brynjolfsson et al. found novices gained 34% while experienced workers saw minimal impact, and Cui et al. found less
# experienced developers gained more. With a 24% power-user lift at mid level, an intern's 1.45x gives about 35%
# (the novice figure) and a senior's 0.70x gives about 17% (smaller, not minimal).
LEVELS = {  # share of headcount, token mult, output mult, hourly-rate mult, lift mult
    "intern": dict(share=0.08, tok=0.45, units=0.55, rate=0.45, lift=1.45),
    "junior": dict(share=0.25, tok=0.8, units=0.8, rate=0.7, lift=1.30),
    "mid": dict(share=0.40, tok=1.0, units=1.0, rate=1.0, lift=1.00),
    "senior": dict(share=0.27, tok=1.15, units=1.1, rate=1.4, lift=0.70),
}

# lift = real productivity gain on outcomes for a mid-level person; usage = relative token use.
# Calibrated to published adopter effects on output of 12% to 26% (Dell'Acqua 12.2, Brynjolfsson 14, Microsoft rollout 24,
# Cui 26.1): power users sit at the top of that range, steady users near its lower end, light users well below.
ARCHETYPES = {
    "power": dict(lift=0.24, usage=1.0, sessions=(60, 120)),
    "steady": dict(lift=0.14, usage=0.35, sessions=(20, 50)),
    "light": dict(lift=0.03, usage=0.08, sessions=(2, 10)),
    "unused": dict(lift=0.0, usage=0.0, sessions=(0, 1)),
    "heavy_no_gain": dict(lift=0.0, usage=1.6, sessions=(80, 200)),
}
MIX = {
    "Engineering": {"power": 0.35, "steady": 0.35, "light": 0.12, "unused": 0.10, "heavy_no_gain": 0.08},
    "Support": {"power": 0.30, "steady": 0.40, "light": 0.15, "unused": 0.10, "heavy_no_gain": 0.05},
    "Sales": {"power": 0.10, "steady": 0.25, "light": 0.25, "unused": 0.25, "heavy_no_gain": 0.15},
    "Marketing": {"power": 0.20, "steady": 0.30, "light": 0.15, "unused": 0.10, "heavy_no_gain": 0.25},
    "Finance": {"power": 0.08, "steady": 0.22, "light": 0.25, "unused": 0.40, "heavy_no_gain": 0.05},
    "Legal": {"power": 0.20, "steady": 0.30, "light": 0.20, "unused": 0.20, "heavy_no_gain": 0.10},
}
# Other things a team might count as output, to show the data can carry more than one metric. Demo data only.
# (metric, how many per main unit, how much of the AI lift it picks up). Each has its own noise and a different AI sensitivity.
EXTRA_METRICS = {
    "Engineering": [("reviews", 0.8, 0.5), ("commits", 3.2, 1.2)],
    "Support": [("chats", 1.4, 0.8), ("surveys_returned", 0.3, 0.5)],
    "Sales": [("calls", 6.0, 0.6), ("emails", 14.0, 0.9)],
    "Marketing": [("drafts", 1.8, 0.7), ("campaign_tasks", 2.5, 0.5)],
    "Finance": [("reconciliations", 3.0, 0.6), ("forecast_updates", 1.2, 0.5)],
    "Legal": [("clauses_checked", 8.0, 0.7), ("matters_opened", 0.6, 0.4)],
}
TEXT_OK = re.compile(r"^[\w &/().,+'\-:%#]{0,60}$")  # letters, digits, spaces and light punctuation; no markup characters
TOKEN_PRICE_PER_M = 5.0  # blended $/1M tokens across fast and frontier models, after caching
MONTHS = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
COMPANY_TREND = 0.025  # everyone's output rises 2.5% a month (busy season). A before/after check would credit this to AI.


@dataclass
class Dataset:
    rows: list[dict]
    truth: dict[str, dict] = field(default_factory=dict)  # employee_id -> hidden labels (generator only)

    def extra_keys(self) -> list[str]:
        seen: list[str] = []
        for r in self.rows:
            for k in r.get("extras", {}):
                if k not in seen:
                    seen.append(k)
        return seen

    def to_csv(self) -> str:
        extras = self.extra_keys()
        has_unit = any(r.get("unit_name") for r in self.rows)
        header = COLUMNS + (["unit_name"] if has_unit else []) + [f"outcome_{k}" for k in extras]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(header)
        for r in self.rows:
            row = [r[c] for c in COLUMNS] + ([r.get("unit_name", "")] if has_unit else []) + [r.get("extras", {}).get(k, "") for k in extras]
            w.writerow(row)
        return buf.getvalue()


def _pick(rng: random.Random, mix: dict[str, float]) -> str:
    x, acc = rng.random(), 0.0
    for k, p in mix.items():
        acc += p
        if x <= acc:
            return k
    return list(mix)[-1]


def generate(seed: int = 7, messy: bool = True, noise: float = 0.07, trend: float = COMPANY_TREND,
             adopter_drift: float = 0.0, scale: float = 1.0, level_lift: bool = True, extras: bool = True) -> Dataset:
    """messy=True adds the cases that break naive analysis: part-timers, people on leave, new hires.

    Knobs for stress tests: noise (monthly output noise, +/- fraction), trend (company-wide monthly growth),
    adopter_drift (extra monthly growth that people who use AI would have had anyway: self-selection),
    scale (headcount multiplier), level_lift (False gives every level the same lift, a flat case for tests).
    """
    rng = random.Random(seed)
    rng_x = random.Random(seed + 1)  # extra metrics draw from their own stream, so the main numbers never change
    rows: list[dict] = []
    truth: dict[str, dict] = {}
    n = 0
    level_names = list(LEVELS)
    level_p = [LEVELS[k]["share"] for k in level_names]
    for dept, count in HEADCOUNT.items():
        role, _unit, hpu, rate, base = ROLES[dept]
        for _ in range(max(1, round(count * scale))):
            n += 1
            eid = f"E{n:04d}"
            arch_name = _pick(rng, MIX[dept])
            arch = ARCHETYPES[arch_name]
            level = rng.choices(level_names, level_p)[0]
            lv = LEVELS[level]
            personal_base = base * lv["units"] * rng.uniform(0.8, 1.2)
            adopt_at = rng.choice([2, 3])  # staggered rollout: months 0-1 are clean for everyone
            part_time = messy and rng.random() < 0.08
            new_hire = messy and rng.random() < 0.05
            leave_month = rng.choice([3, 4]) if messy and rng.random() < 0.05 else None
            truth[eid] = dict(archetype=arch_name, level=level, department=dept,
                              new_hire=new_hire, part_time=part_time, leave=leave_month is not None,
                              lift_window=0.0, base_units=personal_base)
            win_lifts: list[float] = []
            for i, month in enumerate(MONTHS):
                if new_hire and i < 3:
                    continue  # joined in month 3: no pre-period
                active = arch_name != "unused" and i >= adopt_at
                ramp = min(1.0, 0.5 + 0.25 * (i - adopt_at)) if active else 0.0
                lo, hi = arch["sessions"]
                sessions = int(rng.uniform(lo, hi) * ramp) if active and hi > 1 else 0
                tokens = int(arch["usage"] * TOKEN_MULT[dept] * lv["tok"] * ramp * rng.uniform(2.0e6, 6.0e6)) if sessions else 0
                lift = arch["lift"] * (lv["lift"] if level_lift else 1.0) * ramp
                growth = (1 + trend) ** i * ((1 + adopter_drift) ** i if arch_name != "unused" else 1.0)
                units = personal_base * growth * (1 + lift) * rng.uniform(1 - noise, 1 + noise)
                if i >= 2:
                    win_lifts.append(lift)
                mod = 1.0
                if part_time:
                    mod *= 0.5
                    sessions //= 2
                    tokens //= 2
                if leave_month == i:
                    mod *= 0.2
                    sessions = 0
                    tokens = 0
                units_main = units
                units *= mod
                row = dict(
                    employee_id=eid, department=dept, role=role, level=level, month=month,
                    seat_cost=SEAT_COSTS[dept], token_cost=round(tokens / 1e6 * TOKEN_PRICE_PER_M, 2),
                    tokens=tokens, sessions=sessions, outcome_units=round(units, 2),
                    hours_per_unit=hpu, hourly_rate=round(rate * lv["rate"], 2), unit_name=UNIT_NAMES[dept])
                if extras:
                    core = units_main / (1 + lift)
                    row["extras"] = {k: round(core * f * (1 + lift * share) * mod * rng_x.uniform(0.9, 1.1), 2)
                                     for k, f, share in EXTRA_METRICS[dept]}
                rows.append(row)
            truth[eid]["lift_window"] = sum(win_lifts) / len(win_lifts) if win_lifts else 0.0
    return Dataset(rows, truth)


def _safe(value: str, field: str) -> str:
    v = (value or "").strip()
    if not TEXT_OK.match(v):
        raise ValueError(f"{field} may contain letters, digits, spaces and . , ( ) & / + - : % # ' only, up to 60 characters. Got: {v[:40]!r}")
    return v


def load_csv(text: str) -> Dataset:
    reader = csv.DictReader(io.StringIO(text))
    names = reader.fieldnames or []
    missing = set(COLUMNS) - set(OPTIONAL) - set(names)
    if missing:
        raise ValueError(f"CSV is missing columns: {sorted(missing)}")
    extra_cols = [c for c in names if c.startswith("outcome_") and c != "outcome_units"]
    for c in extra_cols:
        if not re.fullmatch(r"outcome_[A-Za-z0-9_]{1,40}", c):
            raise ValueError(f"Extra outcome column names may use letters, digits and underscores only: {c[:40]!r}")
    rows = []
    for r in reader:
        row = dict(
            employee_id=_safe(r["employee_id"], "employee_id"), department=_safe(r["department"], "department"),
            role=_safe(r["role"], "role"), level=_safe(r.get("level") or OPTIONAL["level"], "level").lower(),
            month=_safe(r["month"], "month"),
            seat_cost=float(r["seat_cost"]), token_cost=float(r["token_cost"]),
            tokens=int(float(r["tokens"])), sessions=int(float(r["sessions"])),
            outcome_units=float(r["outcome_units"]),
            hours_per_unit=float(r["hours_per_unit"]), hourly_rate=float(r["hourly_rate"]),
            unit_name=_safe(r.get("unit_name") or "", "unit_name"))
        ex = {c[len("outcome_"):]: float(r[c]) for c in extra_cols if (r.get(c) or "").strip() != ""}
        if ex:
            row["extras"] = ex
        rows.append(row)
    if not rows:
        raise ValueError("CSV has no rows")
    if len({r["month"] for r in rows}) < 4:
        raise ValueError("Need at least 4 months: 2 before rollout as a baseline and 2 or more after")
    return Dataset(rows)
