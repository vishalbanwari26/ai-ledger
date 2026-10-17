"""Synthetic company generator and CSV loader.

Every row is one employee-month. The schema is what a real company could export
by joining its AI vendor billing (cost, tokens) with its own work systems
(outcome units) and HR data (role, department, loaded hourly rate).
"""
from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass

COLUMNS = [
    "employee_id", "department", "role", "month", "seat_cost", "token_cost",
    "tokens", "sessions", "outcome_units", "baseline_units", "hours_per_unit",
    "hourly_rate",
]

# department -> (role, outcome unit name, hours per unit, hourly rate, baseline units/month)
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

# Monthly seat price per person (coding assistant + chat suite for engineers, chat suite for the rest).
SEAT_COSTS = {"Engineering": 60.0, "Support": 40.0, "Sales": 40.0, "Marketing": 40.0, "Finance": 40.0, "Legal": 40.0}
# Token-use multiplier: engineers run agentic coding sessions, support runs agent-assisted replies.
TOKEN_MULT = {"Engineering": 8.0, "Support": 2.5, "Sales": 1.0, "Marketing": 1.5, "Finance": 1.0, "Legal": 1.2}

# Behaviour archetypes. lift = real productivity gain on outcomes; usage = relative token use.
ARCHETYPES = {
    "power": dict(lift=0.22, usage=1.0, sessions=(60, 120)),
    "steady": dict(lift=0.10, usage=0.35, sessions=(20, 50)),
    "tourist": dict(lift=0.02, usage=0.08, sessions=(2, 10)),
    "shelfware": dict(lift=0.0, usage=0.0, sessions=(0, 1)),
    "wasteful": dict(lift=0.0, usage=1.6, sessions=(80, 200)),
}
# Archetype mix differs by department so the story is not uniform.
MIX = {
    "Engineering": {"power": 0.35, "steady": 0.35, "tourist": 0.12, "shelfware": 0.10, "wasteful": 0.08},
    "Support": {"power": 0.30, "steady": 0.40, "tourist": 0.15, "shelfware": 0.10, "wasteful": 0.05},
    "Sales": {"power": 0.10, "steady": 0.25, "tourist": 0.25, "shelfware": 0.25, "wasteful": 0.15},
    "Marketing": {"power": 0.20, "steady": 0.30, "tourist": 0.15, "shelfware": 0.10, "wasteful": 0.25},
    "Finance": {"power": 0.08, "steady": 0.22, "tourist": 0.25, "shelfware": 0.40, "wasteful": 0.05},
    "Legal": {"power": 0.20, "steady": 0.30, "tourist": 0.20, "shelfware": 0.20, "wasteful": 0.10},
}
TOKEN_PRICE_PER_M = 5.0  # blended $/1M tokens across fast and frontier models, after caching
MONTHS = ["2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


@dataclass
class Dataset:
    rows: list[dict]

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
    return "steady"


def generate(seed: int = 7) -> Dataset:
    rng = random.Random(seed)
    rows: list[dict] = []
    n = 0
    for dept, count in HEADCOUNT.items():
        role, _unit, hpu, rate, base = ROLES[dept]
        for _ in range(count):
            n += 1
            eid = f"E{n:04d}"
            arch = ARCHETYPES[_pick(rng, MIX[dept])]
            personal_base = base * rng.uniform(0.7, 1.3)
            for i, month in enumerate(MONTHS):
                # adoption ramps over the first months
                ramp = min(1.0, 0.4 + 0.2 * i)
                lo, hi = arch["sessions"]
                sessions = int(rng.uniform(lo, hi) * ramp) if hi > 1 else 0
                tokens = int(arch["usage"] * TOKEN_MULT[dept] * ramp * rng.uniform(2.0e6, 6.0e6)) if sessions else 0
                lift = arch["lift"] * ramp
                units = personal_base * (1 + lift) * rng.uniform(0.93, 1.07)
                rows.append(dict(
                    employee_id=eid, department=dept, role=role, month=month,
                    seat_cost=SEAT_COSTS[dept], token_cost=round(tokens / 1e6 * TOKEN_PRICE_PER_M, 2),
                    tokens=tokens, sessions=sessions, outcome_units=round(units, 1),
                    baseline_units=round(personal_base, 1), hours_per_unit=hpu, hourly_rate=rate,
                ))
    return Dataset(rows)


def load_csv(text: str) -> Dataset:
    reader = csv.DictReader(io.StringIO(text))
    missing = set(COLUMNS) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"CSV is missing columns: {sorted(missing)}")
    rows = []
    for r in reader:
        rows.append(dict(
            employee_id=r["employee_id"], department=r["department"], role=r["role"], month=r["month"],
            seat_cost=float(r["seat_cost"]), token_cost=float(r["token_cost"]),
            tokens=int(float(r["tokens"])), sessions=int(float(r["sessions"])),
            outcome_units=float(r["outcome_units"]), baseline_units=float(r["baseline_units"]),
            hours_per_unit=float(r["hours_per_unit"]), hourly_rate=float(r["hourly_rate"]),
        ))
    if not rows:
        raise ValueError("CSV has no rows")
    return Dataset(rows)
