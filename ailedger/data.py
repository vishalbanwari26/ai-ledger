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
LEVELS = {  # share of headcount, token mult, output mult, hourly-rate mult
    "intern": dict(share=0.08, tok=0.45, units=0.55, rate=0.45),
    "junior": dict(share=0.25, tok=0.8, units=0.8, rate=0.7),
    "mid": dict(share=0.40, tok=1.0, units=1.0, rate=1.0),
    "senior": dict(share=0.27, tok=1.15, units=1.1, rate=1.4),
}

# lift = real productivity gain on outcomes; usage = relative token use.
ARCHETYPES = {
    "power": dict(lift=0.22, usage=1.0, sessions=(60, 120)),
    "steady": dict(lift=0.10, usage=0.35, sessions=(20, 50)),
    "light": dict(lift=0.02, usage=0.08, sessions=(2, 10)),
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
TOKEN_PRICE_PER_M = 5.0  # blended $/1M tokens across fast and frontier models, after caching
MONTHS = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]
COMPANY_TREND = 0.025  # everyone's output rises 2.5% a month (busy season). A before/after check would credit this to AI.


@dataclass
class Dataset:
    rows: list[dict]
    truth: dict[str, dict] = field(default_factory=dict)  # employee_id -> hidden labels (generator only)

    def to_csv(self) -> str:
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=COLUMNS)
        w.writeheader()
        for r in self.rows:
            w.writerow({c: r[c] for c in COLUMNS})
        return buf.getvalue()


def _pick(rng: random.Random, mix: dict[str, float]) -> str:
    x, acc = rng.random(), 0.0
    for k, p in mix.items():
        acc += p
        if x <= acc:
            return k
    return list(mix)[-1]


def generate(seed: int = 7, messy: bool = True, noise: float = 0.07, trend: float = COMPANY_TREND,
             adopter_drift: float = 0.0, scale: float = 1.0) -> Dataset:
    """messy=True adds the cases that break naive analysis: part-timers, people on leave, new hires.

    Knobs for stress tests: noise (monthly output noise, +/- fraction), trend (company-wide monthly growth),
    adopter_drift (extra monthly growth that people who use AI would have had anyway: self-selection),
    scale (headcount multiplier).
    """
    rng = random.Random(seed)
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
                lift = arch["lift"] * ramp
                growth = (1 + trend) ** i * ((1 + adopter_drift) ** i if arch_name != "unused" else 1.0)
                units = personal_base * growth * (1 + lift) * rng.uniform(1 - noise, 1 + noise)
                if i >= 2:
                    win_lifts.append(lift)
                if part_time:
                    units *= 0.5
                    sessions //= 2
                    tokens //= 2
                if leave_month == i:
                    units *= 0.2
                    sessions = 0
                    tokens = 0
                rows.append(dict(
                    employee_id=eid, department=dept, role=role, level=level, month=month,
                    seat_cost=SEAT_COSTS[dept], token_cost=round(tokens / 1e6 * TOKEN_PRICE_PER_M, 2),
                    tokens=tokens, sessions=sessions, outcome_units=round(units, 2),
                    hours_per_unit=hpu, hourly_rate=round(rate * lv["rate"], 2),
                ))
            truth[eid]["lift_window"] = sum(win_lifts) / len(win_lifts) if win_lifts else 0.0
    return Dataset(rows, truth)


def load_csv(text: str) -> Dataset:
    reader = csv.DictReader(io.StringIO(text))
    missing = set(COLUMNS) - set(OPTIONAL) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV is missing columns: {sorted(missing)}")
    rows = []
    for r in reader:
        rows.append(dict(
            employee_id=r["employee_id"], department=r["department"], role=r["role"],
            level=(r.get("level") or OPTIONAL["level"]).strip().lower(), month=r["month"],
            seat_cost=float(r["seat_cost"]), token_cost=float(r["token_cost"]),
            tokens=int(float(r["tokens"])), sessions=int(float(r["sessions"])),
            outcome_units=float(r["outcome_units"]),
            hours_per_unit=float(r["hours_per_unit"]), hourly_rate=float(r["hourly_rate"]),
        ))
    if not rows:
        raise ValueError("CSV has no rows")
    if len({r["month"] for r in rows}) < 4:
        raise ValueError("Need at least 4 months: 2 before rollout as a baseline and 2 or more after")
    return Dataset(rows)
