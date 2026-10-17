"""ROI maths, employee segmentation and budget-policy simulation.

All numbers here are computed in plain Python so every figure the LLM quotes
can be traced back to rows. Assumptions are explicit parameters, not hidden.
"""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass, field

from .data import Dataset


@dataclass
class Assumptions:
    window_months: int = 3       # steady-state window; early months are adoption ramp
    realization: float = 0.5     # share of extra output that is real, bankable value
    elasticity: float = 0.5      # value kept = (cap/usage)^elasticity when spend is capped
    idle_sessions: float = 3.0   # avg sessions/month below this = idle seat


@dataclass
class Employee:
    employee_id: str
    department: str
    role: str
    cost: float = 0.0            # avg monthly seat + token cost
    token_cost: float = 0.0      # avg monthly token spend
    peak_token_cost: float = 0.0 # highest single-month token spend in the window
    seat_cost: float = 0.0
    sessions: float = 0.0
    uplift_units: float = 0.0    # avg monthly units above personal baseline
    value: float = 0.0           # avg monthly dollar value after realization haircut
    segment: str = ""

    @property
    def roi(self) -> float:
        return (self.value - self.cost) / self.cost if self.cost else 0.0


def employees(ds: Dataset, a: Assumptions) -> list[Employee]:
    months = sorted({r["month"] for r in ds.rows})[-a.window_months:]
    by_emp: dict[str, list[dict]] = {}
    for r in ds.rows:
        if r["month"] in months:
            by_emp.setdefault(r["employee_id"], []).append(r)
    out = []
    for eid, rs in by_emp.items():
        n = len(rs)
        e = Employee(eid, rs[0]["department"], rs[0]["role"])
        e.seat_cost = sum(r["seat_cost"] for r in rs) / n
        e.token_cost = sum(r["token_cost"] for r in rs) / n
        e.peak_token_cost = max(r["token_cost"] for r in rs)
        e.cost = e.seat_cost + e.token_cost
        e.sessions = sum(r["sessions"] for r in rs) / n
        e.uplift_units = sum(r["outcome_units"] - r["baseline_units"] for r in rs) / n
        e.value = a.realization * sum(
            (r["outcome_units"] - r["baseline_units"]) * r["hours_per_unit"] * r["hourly_rate"] for r in rs
        ) / n
        out.append(e)
    med_token = st.median([e.token_cost for e in out]) or 1.0
    for e in out:
        if e.sessions < a.idle_sessions:
            e.segment = "idle"
        elif e.roi >= 1.0:
            e.segment = "high-return"
        elif e.roi >= 0.0:
            e.segment = "break-even"
        elif e.token_cost > 1.5 * med_token:
            e.segment = "overspender"
        else:
            e.segment = "low-return"
    return out


def _roll(es: list[Employee]) -> dict:
    cost = sum(e.cost for e in es)
    value = sum(e.value for e in es)
    return dict(
        headcount=len(es),
        monthly_cost=round(cost, 2),
        monthly_value=round(value, 2),
        net=round(value - cost, 2),
        roi=round((value - cost) / cost, 3) if cost else 0.0,
        cost_per_head=round(cost / len(es), 2) if es else 0.0,
        idle=sum(1 for e in es if e.segment == "idle"),
        idle_waste=round(sum(e.seat_cost for e in es if e.segment == "idle"), 2),
        overspenders=sum(1 for e in es if e.segment == "overspender"),
    )


def summary(ds: Dataset, a: Assumptions) -> dict:
    es = employees(ds, a)
    depts: dict[str, list[Employee]] = {}
    for e in es:
        depts.setdefault(e.department, []).append(e)
    segs: dict[str, int] = {}
    for e in es:
        segs[e.segment] = segs.get(e.segment, 0) + 1
    return dict(
        assumptions=a.__dict__,
        company=_roll(es),
        departments={d: _roll(v) | {"role": v[0].role} for d, v in sorted(depts.items())},
        segments=segs,
    )


def waste(ds: Dataset, a: Assumptions) -> dict:
    """Recoverable monthly spend: idle seats, plus overspend above what ROI-positive peers spend."""
    es = employees(ds, a)
    caps = _role_caps(es, 0.75)
    per: dict[str, dict] = {}
    for e in es:
        d = per.setdefault(e.department, dict(idle_seats=0, idle_cost=0.0, over_people=0, over_cost=0.0))
        if e.segment == "idle":
            d["idle_seats"] += 1
            d["idle_cost"] += e.seat_cost
        elif e.segment == "overspender":
            d["over_people"] += 1
            d["over_cost"] += max(0.0, e.token_cost - caps.get(e.department, 0.0))
    for d in per.values():
        d["idle_cost"], d["over_cost"] = round(d["idle_cost"], 2), round(d["over_cost"], 2)
        d["total"] = round(d["idle_cost"] + d["over_cost"], 2)
    idle = round(sum(d["idle_cost"] for d in per.values()), 2)
    over = round(sum(d["over_cost"] for d in per.values()), 2)
    return dict(idle_seats=sum(d["idle_seats"] for d in per.values()), idle_monthly=idle,
                over_people=sum(d["over_people"] for d in per.values()), over_monthly=over,
                total_monthly=round(idle + over, 2), total_annual=round((idle + over) * 12, 2),
                by_department=dict(sorted(per.items(), key=lambda kv: -kv[1]["total"])))


def employees_in(ds: Dataset, a: Assumptions, department: str | None = None,
                 segment: str | None = None, limit: int = 10, worst: bool = True) -> list[dict]:
    es = [e for e in employees(ds, a)
          if (department is None or e.department.lower() == department.lower())
          and (segment is None or e.segment == segment)]
    es.sort(key=lambda e: e.roi, reverse=not worst)
    return [dict(employee_id=e.employee_id, department=e.department, segment=e.segment,
                 monthly_cost=round(e.cost, 2), monthly_value=round(e.value, 2),
                 roi=round(e.roi, 2), sessions=round(e.sessions, 1)) for e in es[:limit]]


# ---------------------------------------------------------------- policies

@dataclass
class Policy:
    name: str
    description: str
    seat_fee: float | None = None        # flat $/seat/month; None = each person's actual seat cost
    reclaim_idle: bool = False           # idle employees lose the seat
    cap_mode: str = "none"               # none | flat | role
    flat_cap: float = 0.0                # monthly token $ cap per employee
    cap_pctile: float = 0.75             # for role mode: percentile of ROI-positive spend
    pooled: bool = False                 # unused allowance pooled within a department
    price_multiplier: float = 1.0        # list-price premium when buying tokens without a seat plan
    extra: dict = field(default_factory=dict)


def _role_caps(es: list[Employee], pctile: float) -> dict[str, float]:
    caps = {}
    for d in {e.department for e in es}:
        good = sorted(e.token_cost for e in es if e.department == d and e.roi > 0 and e.segment != "idle")
        if not good:
            caps[d] = 0.0
            continue
        k = min(len(good) - 1, int(pctile * len(good)))
        caps[d] = good[k]
    return caps


def _seat(e: Employee, p: Policy) -> float:
    return e.seat_cost if p.seat_fee is None else p.seat_fee


def _run(es: list[Employee], a: Assumptions, p: Policy, caps: dict[str, float], peak: bool) -> tuple[float, float]:
    """Cost and value of a policy. peak=True prices every person at their own worst month."""
    cost = value = 0.0
    dept_budget: dict[str, float] = {}
    dept_demand: dict[str, float] = {}
    dept_n: dict[str, int] = {}
    for e in es:
        if p.reclaim_idle and e.segment == "idle":
            continue  # seat reclaimed: no cost, and we forgo whatever value they produced
        cap = {"none": None, "flat": p.flat_cap, "role": caps.get(e.department)}[p.cap_mode]
        spend = (e.peak_token_cost if peak else e.token_cost) * p.price_multiplier
        if cap is not None and p.pooled:
            dept_budget[e.department] = dept_budget.get(e.department, 0.0) + cap
            dept_demand[e.department] = dept_demand.get(e.department, 0.0) + spend
            dept_n[e.department] = dept_n.get(e.department, 0) + 1
            continue
        kept = 1.0
        if cap is not None and spend > cap:
            kept = (cap / spend) ** a.elasticity
            spend = cap
        cost += _seat(e, p) + spend
        value += e.value * kept if e.value > 0 else e.value
    for d, bud in dept_budget.items():
        dem = dept_demand[d]
        spent = min(dem, bud)
        kept = (spent / dem) ** a.elasticity if dem else 1.0
        cost += sum(_seat(e, p) for e in es if e.department == d and not (p.reclaim_idle and e.segment == "idle")) + spent
        value += sum(e.value for e in es if e.department == d and not (p.reclaim_idle and e.segment == "idle")) * kept
    return cost, value


def simulate(ds: Dataset, a: Assumptions, p: Policy) -> dict:
    es = employees(ds, a)
    caps = _role_caps(es, p.cap_pctile) if p.cap_mode == "role" else {}
    cost, value = _run(es, a, p, caps, peak=False)
    worst, _ = _run(es, a, p, caps, peak=True)
    return dict(name=p.name, description=p.description, monthly_cost=round(cost, 2),
                monthly_value=round(value, 2), net=round(value - cost, 2),
                roi=round((value - cost) / cost, 3) if cost else 0.0,
                worst_case_cost=round(worst, 2),
                bill_risk=round(worst / cost - 1, 3) if cost else 0.0)


def standard_policies() -> list[Policy]:
    return [
        Policy("Status quo", "Everyone keeps a seat; token spend is uncapped."),
        Policy("Fixed budget", "Flat $60 token cap for everyone, seats unchanged.",
               cap_mode="flat", flat_cap=60.0),
        Policy("Pay per use", "No seats. Tokens bought at list price (1.6x the seat-plan rate), uncapped.",
               seat_fee=0.0, price_multiplier=1.6),
        Policy("Variable by role", "Seats only for active users; token cap set per department from what "
               "ROI-positive colleagues actually spend; unused allowance pooled in the department.",
               reclaim_idle=True, cap_mode="role", pooled=True),
    ]


def compare_policies(ds: Dataset, a: Assumptions) -> list[dict]:
    rows = [simulate(ds, a, p) for p in standard_policies()]
    best_net = max(rows, key=lambda r: r["net"])["name"]
    safest = min(rows, key=lambda r: r["bill_risk"])["name"]
    for r in rows:  # computed here so the model never has to compare rows itself
        r["highest_net"] = r["name"] == best_net
        r["lowest_bill_risk"] = r["name"] == safest
    return rows


def budget_recommendations(ds: Dataset, a: Assumptions) -> dict:
    """Per-department verdict: fixed or variable, and a per-head monthly budget."""
    es = employees(ds, a)
    caps = _role_caps(es, 0.75)
    out = {}
    for d in sorted({e.department for e in es}):
        group = [e for e in es if e.department == d]
        spend = [e.token_cost for e in group]
        mean = st.mean(spend)
        cv = (st.pstdev(spend) / mean) if mean else 0.0
        active = [e for e in group if e.segment != "idle"]
        roll = _roll(group)
        if roll["roi"] < 0:
            verdict = "restrict"
            reason = "Department ROI is negative. Cut seats to active users and cap spend until usage is tied to outcomes."
        elif cv > 0.8:
            verdict = "variable"
            reason = "Spend varies widely between people (CV %.2f), so a flat budget would overpay some and starve others." % cv
        else:
            verdict = "fixed"
            reason = "Spend is similar across people (CV %.2f), so a predictable per-seat budget is simple and fair." % cv
        out[d] = dict(
            verdict=verdict, reason=reason, spend_cv=round(cv, 2),
            active_share=round(len(active) / len(group), 2),
            recommended_seat=round(st.median(e.seat_cost for e in group), 2),
            recommended_token_cap=round(caps.get(d, 0.0), 2),
            recommended_per_head=round(st.median(e.seat_cost for e in group) + caps.get(d, 0.0), 2),
            current_per_head=roll["cost_per_head"], dept_roi=roll["roi"],
        )
    return out
