"""ROI maths, employee segmentation and budget-policy simulation.

All numbers here are computed in plain Python so every figure the LLM quotes can be traced back to rows.
Assumptions are explicit parameters, not hidden constants.

How value is estimated (the part a skeptic will attack, so it is spelled out):
  1. Each person's output in the first `pre_months` months is their own baseline (before rollout).
  2. Growth = median output in the last `window_months` months / baseline - 1.
  3. People who did not adopt (idle all window) are the control group. Their growth is what happens
     anyway: seasonality, a busy quarter. The AI effect is (1 + treated growth) / (1 + control growth) - 1
     (difference-in-differences in ratio form, because effects multiply with trend). Growth is a ratio,
     so an intern and a senior are comparable.
  3b. Parallel-trends check: before rollout, adopters and non-adopters should have grown alike. If adopters
     were already growing faster (self-selection), that gap is extrapolated and removed, and a warning is shown.
  4. Each person's estimate is shrunk toward their department's treated average, by how noisy the
     individual numbers are. This stops one lucky or unlucky month deciding anyone's ROI.
  5. Dollar value = effect x baseline output x hours per unit x hourly rate x `realization`.
Limit: the pre-rollout check only sees differences that show up before rollout, and assumes they continue at a
steady rate. Adopters who improve for reasons that start at rollout cannot be told apart from the AI effect.
"""
from __future__ import annotations

import statistics as st
from dataclasses import dataclass, field

from .data import Dataset, TOKEN_PRICE_PER_M

Z95 = 1.96
LEARNING_LEVELS = ("intern", "junior")
# Share of each department's tokens that are routine (summaries, drafts, lookups) and could run on a
# cheaper open model. These are planning assumptions, not measurements.
ROUTINE_SHARE = {"Engineering": 0.5, "Support": 0.8, "Sales": 0.7, "Marketing": 0.6, "Finance": 0.6, "Legal": 0.4}


@dataclass
class Assumptions:
    window_months: int = 3
    pre_months: int = 2
    realization: float = 0.5          # share of the estimated extra output that is real, bankable value
    elasticity: float = 0.5           # value kept = (cap/usage)^elasticity when spend is capped
    idle_sessions: float = 3.0        # avg sessions/month below this = idle seat
    seat_savings_realized: float = 0.8  # contract minimums and notice periods: not every reclaimed $ is saved
    friction: float = 0.05            # pay per use: people use AI less when they see a meter
    cheap_price_per_m: float = 0.6    # $/1M tokens on a smaller open model. Set to your Token Factory price.
    quality_penalty: float = 0.02     # value lost on tokens moved to the cheaper model
    min_cohort: int = 8               # peer groups smaller than this fall back to the whole department
    min_group: int = 10               # groups smaller than this are never shown separately
    adjust_pretrend: bool = True      # remove a growth gap that adopters already had before rollout
    ppu_multiplier: float = 1.6       # pay per use: list price of tokens vs the seat-plan rate. Get a real quote.
    ppu_friction: float = 0.05        # pay per use: share of value lost because people ration metered use


@dataclass
class Employee:
    employee_id: str
    department: str
    role: str
    level: str
    cost: float = 0.0            # avg monthly seat + token cost
    token_cost: float = 0.0      # avg monthly token spend
    peak_token_cost: float = 0.0
    seat_cost: float = 0.0
    sessions: float = 0.0
    treated: bool = False
    own_baseline: bool = False   # has pre-rollout months of their own
    growth: float | None = None  # output growth vs own baseline
    base: float = 0.0            # baseline output per month (own first months, or implied)
    lift: float = 0.0            # estimated AI effect (shrunk DiD), as a fraction of baseline output
    value: float = 0.0           # avg monthly dollar value after realization
    value_low: float = 0.0
    value_high: float = 0.0
    segment: str = ""

    @property
    def roi(self) -> float:
        return (self.value - self.cost) / self.cost if self.cost else 0.0


# Only these assumptions change the per-person estimates. The others (elasticity, prices, seat savings) only
# change what policies do with them, so robustness sweeps can reuse the same estimates.
_ANALYSIS_FIELDS = ("window_months", "pre_months", "realization", "idle_sessions", "min_cohort", "adjust_pretrend")


def _akey(a: "Assumptions") -> tuple:
    return tuple((f, getattr(a, f)) for f in _ANALYSIS_FIELDS)


def _var(xs: list[float]) -> float:
    return st.variance(xs) if len(xs) >= 2 else 0.0


def _analyze(ds: Dataset, a: Assumptions) -> tuple[list[Employee], dict]:
    cache = ds.__dict__.setdefault("_cache", {})
    key = _akey(a)
    if key in cache:
        return cache[key]
    months = sorted({r["month"] for r in ds.rows})
    pre_m = months[:a.pre_months]
    win_m = months[a.pre_months:][-a.window_months:]
    by_emp: dict[str, list[dict]] = {}
    for r in ds.rows:
        by_emp.setdefault(r["employee_id"], []).append(r)

    es: list[Employee] = []
    units_pre: dict[str, float] = {}
    units_win: dict[str, float] = {}
    g01: dict[str, float] = {}  # growth between the two pre-rollout months, for the parallel-trends check
    for eid, rs in by_emp.items():
        w = [r for r in rs if r["month"] in win_m]
        if not w:
            continue
        pre = [r for r in rs if r["month"] in pre_m]
        n = len(w)
        e = Employee(eid, rs[0]["department"], rs[0]["role"], rs[0].get("level", "mid"))
        e.seat_cost = sum(r["seat_cost"] for r in w) / n
        e.token_cost = sum(r["token_cost"] for r in w) / n
        e.peak_token_cost = max(r["token_cost"] for r in w)
        e.cost = e.seat_cost + e.token_cost
        e.sessions = sum(r["sessions"] for r in w) / n
        e.treated = e.sessions >= a.idle_sessions
        units_win[eid] = st.median(r["outcome_units"] for r in w)  # median: one leave month must not decide it
        um = {r["month"]: r["outcome_units"] for r in rs}
        if len(pre_m) >= 2 and um.get(pre_m[0], 0) > 0 and pre_m[1] in um:
            g01[eid] = um[pre_m[1]] / um[pre_m[0]] - 1
        if pre:
            units_pre[eid] = st.mean(r["outcome_units"] for r in pre)
            if units_pre[eid] > 0:
                e.own_baseline = True
                e.growth = units_win[eid] / units_pre[eid] - 1
        e.hpu = w[0]["hours_per_unit"]  # type: ignore[attr-defined]
        e.rate = w[0]["hourly_rate"]    # type: ignore[attr-defined]
        es.append(e)

    # --- parallel-trends check: did adopters already grow faster than non-adopters before rollout?
    sel = dict(tested=False, gap_per_month=0.0, se=0.0, significant=False, horizon=0.0, adjusted=False,
               adjustment=0.0)
    gt = [g01[e.employee_id] for e in es if e.treated and e.employee_id in g01]
    gc = [g01[e.employee_id] for e in es if not e.treated and e.employee_id in g01]
    horizon = (st.mean(months.index(m) for m in win_m) - st.mean(months.index(m) for m in pre_m)) if pre_m else 0.0
    if len(gt) >= a.min_cohort and len(gc) >= a.min_cohort:
        gap = (1 + st.mean(gt)) / (1 + st.mean(gc)) - 1
        gse = ((_var(gt) / len(gt) + _var(gc) / len(gc)) ** 0.5) / (1 + st.mean(gc))
        sel.update(tested=True, gap_per_month=gap, se=gse, significant=abs(gap) > Z95 * gse, horizon=horizon)
        if a.adjust_pretrend:  # always apply the point estimate; its noise is added to the ranges below
            sel.update(adjusted=True, adjustment=(1 + gap) ** horizon - 1)
    drift = (1 + sel["gap_per_month"]) ** sel["horizon"] if sel["adjusted"] else 1.0

    # --- difference-in-differences per department (control = non-adopters with a baseline)
    company_ctrl = [e.growth for e in es if not e.treated and e.growth is not None]
    stats: dict[str, dict] = {}
    for d in sorted({e.department for e in es}):
        group = [e for e in es if e.department == d]
        ctrl = [e.growth for e in group if not e.treated and e.growth is not None]
        pooled = len(ctrl) < a.min_cohort
        if pooled:
            ctrl = company_ctrl
        c_raw = st.mean(ctrl) if ctrl else 0.0
        c_eff = (1 + c_raw) * drift - 1  # what treated people would have grown without AI
        c_var = _var(ctrl)
        tr = [e for e in group if e.treated and e.growth is not None]
        t_growth = [e.growth for e in tr]
        naive = st.mean(t_growth) if t_growth else 0.0
        did = (1 + naive) / (1 + c_eff) - 1
        v_t = _var(t_growth)
        se = ((v_t / len(t_growth) if t_growth else 0.0) + (c_var / len(ctrl) if ctrl else 0.0)) / (1 + c_eff) ** 2
        se = (se + ((1 + did) * sel["horizon"] * sel["se"] if sel["adjusted"] else 0.0) ** 2) ** 0.5
        shrink = max(0.0, 1 - c_var / v_t) if v_t > 0 else 0.0
        stats[d] = dict(naive_lift=naive, did_lift=did, se=se, ci_low=did - Z95 * se, ci_high=did + Z95 * se,
                        control_n=len(ctrl), control_pooled=pooled, treated_n=len(tr), control_growth=c_eff, control_raw=c_raw,
                        shrink=shrink)
        for e in group:
            if not e.treated:
                continue  # did not use it: no AI value, whatever their output did
            lift_hat = ((1 + e.growth) / (1 + c_eff) - 1) if e.growth is not None else did
            e.lift = did + shrink * (lift_hat - did)
            base = units_pre[e.employee_id] if e.employee_id in units_pre else units_win[e.employee_id] / ((1 + did) * (1 + c_eff))
            e.base = base
            scale = a.realization * base * e.hpu * e.rate  # type: ignore[attr-defined]
            e.value = max(0.0, e.lift * scale)
            e.value_low = max(0.0, (e.lift - Z95 * se) * scale)
            e.value_high = max(0.0, (e.lift + Z95 * se) * scale)

    # --- segments, judged against peers of the same role AND level (an intern is not a senior)
    peers = _peer_median(es, a.min_cohort)
    for e in es:
        if not e.treated:
            e.segment = "idle"
        elif e.roi >= 1.0:
            e.segment = "high-return"
        elif e.roi >= 0.0:
            e.segment = "break-even"
        elif e.token_cost > 1.5 * peers(e):
            e.segment = "high-spend"
        else:
            e.segment = "low-return"
    out = (es, stats)
    cache[("sel",) + key] = sel
    if len(cache) > 24:
        cache.clear()
    cache[key] = out
    return out


def selection(ds: Dataset, a: Assumptions) -> dict:
    """Result of the parallel-trends check: did adopters already grow faster before rollout?"""
    _analyze(ds, a)
    return ds.__dict__["_cache"][("sel",) + _akey(a)]


def _cohort_counts(es: list[Employee], pred) -> dict[tuple, int]:
    counts: dict[tuple, int] = {}
    for e in es:
        if pred(e):
            counts[(e.department, e.level)] = counts.get((e.department, e.level), 0) + 1
            counts[(e.department, None)] = counts.get((e.department, None), 0) + 1
    return counts


def _peer_median(es: list[Employee], min_cohort: int):
    active = [e for e in es if e.treated]
    counts = _cohort_counts(es, lambda e: e.treated)
    meds: dict[tuple, float] = {}
    for key in counts:
        d, lv = key
        xs = [e.token_cost for e in active if e.department == d and (lv is None or e.level == lv)]
        meds[key] = st.median(xs) if xs else 0.0

    def med(e: Employee) -> float:
        k = (e.department, e.level)
        return meds[k] if counts.get(k, 0) >= min_cohort else meds.get((e.department, None), 0.0)
    return med


def employees(ds: Dataset, a: Assumptions) -> list[Employee]:
    return _analyze(ds, a)[0]


def _roll(es: list[Employee], a: Assumptions) -> dict:
    cost = sum(e.cost for e in es)
    value = sum(e.value for e in es)
    low = sum(e.value_low for e in es)
    high = sum(e.value_high for e in es)
    r = lambda v: round((v - cost) / cost, 3) if cost else 0.0  # noqa: E731
    idle = [e for e in es if e.segment == "idle"]
    return dict(
        headcount=len(es), monthly_cost=round(cost, 2), monthly_value=round(value, 2),
        value_low=round(low, 2), value_high=round(high, 2), net=round(value - cost, 2),
        roi=r(value), roi_low=r(low), roi_high=r(high),
        confidence="clear" if r(low) > 0 or r(high) < 0 else "uncertain",
        break_even_realization=round(a.realization * cost / value, 3) if value > 0 else None,
        cost_per_head=round(cost / len(es), 2) if es else 0.0,
        idle=len(idle), idle_waste=round(sum(e.seat_cost for e in idle), 2),
        high_spend=sum(1 for e in es if e.segment == "high-spend"),
    )


def summary(ds: Dataset, a: Assumptions) -> dict:
    es, stats = _analyze(ds, a)
    depts: dict[str, list[Employee]] = {}
    levels: dict[str, list[Employee]] = {}
    for e in es:
        depts.setdefault(e.department, []).append(e)
        levels.setdefault(e.level, []).append(e)
    segs: dict[str, int] = {}
    for e in es:
        segs[e.segment] = segs.get(e.segment, 0) + 1
    naive = [s["naive_lift"] * s["treated_n"] for s in stats.values()]
    nt = sum(s["treated_n"] for s in stats.values()) or 1
    ctrl = sum(s["control_growth"] * s["treated_n"] for s in stats.values()) / nt
    n_avg = sum(naive) / nt
    company = _roll(es, a) | dict(naive_lift=round(n_avg, 4), control_growth=round(ctrl, 4),
                                 did_lift=round((1 + n_avg) / (1 + ctrl) - 1, 4), selection=selection(ds, a))
    order = ["intern", "junior", "mid", "senior"]
    return dict(
        assumptions=a.__dict__,
        company=company,
        departments={d: _roll(v, a) | {"role": v[0].role} | {k: round(x, 4) if isinstance(x, float) else x
                                                              for k, x in stats[d].items()}
                     for d, v in sorted(depts.items())},
        levels={lv: _roll(levels[lv], a) for lv in order if lv in levels},
        segments=segs,
    )


def list_people(ds: Dataset, a: Assumptions, department: str | None = None, segment: str | None = None,
                limit: int = 10, worst: bool = True) -> list[dict]:
    """Groups of at least `min_group` people, by department and level. Individuals are never returned: the
    unit of analysis is how seats and budgets are set up, not any one person's behaviour."""
    es = [e for e in employees(ds, a)
          if (department is None or e.department.lower() == department.lower())
          and (segment is None or e.segment == segment)]
    groups: dict[tuple, list[Employee]] = {}
    for e in es:
        groups.setdefault((e.department, e.level), []).append(e)
    rows = []
    for (d, lv), g in groups.items():
        if len(g) < a.min_group:
            continue  # too small to show without pointing at individuals
        c, v = sum(e.cost for e in g), sum(e.value for e in g)
        rows.append(dict(department=d, level=lv, people=len(g), segment=segment or "all",
                         monthly_cost=round(c, 2), monthly_value=round(v, 2),
                         roi=round((v - c) / c, 2) if c else 0.0))
    rows.sort(key=lambda r: r["roi"], reverse=not worst)
    return rows[:limit]


# ---------------------------------------------------------------- waste and actions

def _caps(es: list[Employee], a: Assumptions, pctile: float) -> dict[tuple, float]:
    """Token cap per (department, level): what ROI-positive active peers actually spend."""
    good = [e for e in es if e.treated and e.roi > 0]
    caps: dict[tuple, float] = {}
    keys = {(e.department, e.level) for e in es} | {(e.department, None) for e in es}
    for d, lv in keys:
        xs = sorted(e.token_cost for e in good if e.department == d and (lv is None or e.level == lv))
        if lv is not None and len(xs) < a.min_cohort:
            continue
        if xs:
            caps[(d, lv)] = xs[min(len(xs) - 1, int(pctile * len(xs)))]
    # Learning floor. Dollar ROI depends on hourly rate, so juniors only look ROI-positive when they spend little.
    # A peer norm therefore describes how much they use today, not what they need. Juniors and interns iterate
    # more while they learn, so their cap is never set below the department-wide one.
    for d in {e.department for e in es}:
        for lv in LEARNING_LEVELS:
            if (d, None) in caps:
                caps[(d, lv)] = max(caps.get((d, lv), 0.0), caps[(d, None)])
    return caps


def _cap_for(e: Employee, caps: dict[tuple, float]) -> float:
    return caps.get((e.department, e.level), caps.get((e.department, None), 0.0))


def waste(ds: Dataset, a: Assumptions) -> dict:
    """Recoverable monthly spend: unused seats (after contract friction) plus high spend above peer norms."""
    es = employees(ds, a)
    caps = _caps(es, a, 0.75)
    per: dict[str, dict] = {}
    for e in es:
        d = per.setdefault(e.department, dict(idle_seats=0, idle_cost=0.0, over_people=0, over_cost=0.0))
        if e.segment == "idle":
            d["idle_seats"] += 1
            d["idle_cost"] += e.seat_cost * a.seat_savings_realized
        elif e.segment == "high-spend":
            d["over_people"] += 1
            d["over_cost"] += max(0.0, e.token_cost - _cap_for(e, caps))
    for d in per.values():
        d["idle_cost"], d["over_cost"] = round(d["idle_cost"], 2), round(d["over_cost"], 2)
        d["total"] = round(d["idle_cost"] + d["over_cost"], 2)
    idle = round(sum(d["idle_cost"] for d in per.values()), 2)
    over = round(sum(d["over_cost"] for d in per.values()), 2)
    return dict(idle_seats=sum(d["idle_seats"] for d in per.values()), idle_monthly=idle,
                over_people=sum(d["over_people"] for d in per.values()), over_monthly=over,
                total_monthly=round(idle + over, 2), total_annual=round((idle + over) * 12, 2),
                seat_savings_realized=a.seat_savings_realized,
                by_department=dict(sorted(per.items(), key=lambda kv: -kv[1]["total"])))


def actions(ds: Dataset, a: Assumptions) -> list[dict]:
    """Proposed changes, one row per department and level, each with a reason. Approve before acting.
    Groups under `min_group` people are merged per department; no row ever identifies a person."""
    es = employees(ds, a)
    caps = _caps(es, a, 0.75)
    buckets: dict[tuple, list[Employee]] = {}
    for e in es:
        if e.segment in ("idle", "high-spend"):
            buckets.setdefault((e.segment, e.department, e.level), []).append(e)
    merged: dict[tuple, list[Employee]] = {}
    for (seg, d, lv), g in buckets.items():
        if len(g) >= a.min_group:
            merged[(seg, d, lv)] = g
        else:
            merged.setdefault((seg, d, "all levels"), []).extend(g)
    rows: list[dict] = []
    leftovers: dict[str, list[Employee]] = {}
    for (seg, d, lv), g in list(merged.items()):
        if len(g) < a.min_group:
            leftovers.setdefault(seg, []).extend(g)
            del merged[(seg, d, lv)]
    for seg, g in leftovers.items():
        if len(g) >= a.min_group:
            merged[(seg, "Several departments", "various")] = g  # small groups pooled so the total still adds up
    for (seg, d, lv), g in merged.items():
        if seg == "idle":
            saving = sum(e.seat_cost for e in g) * a.seat_savings_realized
            row = dict(kind="reassign unused seats", department=d, level=lv, people=len(g),
                       monthly_saving=round(saving, 2),
                       reason=f"Seats with fewer than {a.idle_sessions:g} sessions a month for {a.window_months} months. "
                              "Ask the team first: the tool may not fit their work, or they may not know it exists.")
        else:
            saving = sum(max(0.0, e.token_cost - _cap_for(e, caps)) for e in g)
            cap = max((_cap_for(e, caps) for e in g), default=0.0)
            row = dict(kind="review usage and set a team budget", department=d, level=lv, people=len(g),
                       monthly_saving=round(saving, 2),
                       reason=f"High spend with no matching gain in output, above what {d} {lv} peers spend. "
                              f"Start with training and workflow fit; a team budget near ${cap:,.0f} per person per month is the fallback.")
        rows.append(row)
    rows.sort(key=lambda r: -r["monthly_saving"])
    for i, r in enumerate(rows):
        r["id"] = i
    return rows


# ---------------------------------------------------------------- model routing

def routing(ds: Dataset, a: Assumptions) -> dict:
    """What if routine tokens ran on a cheaper open model (e.g. Nemotron Nano on Token Factory)?"""
    months = sorted({r["month"] for r in ds.rows})
    win_m = set(months[a.pre_months:][-a.window_months:])
    tokens: dict[str, float] = {}
    for r in ds.rows:
        if r["month"] in win_m:
            tokens[r["department"]] = tokens.get(r["department"], 0.0) + r["tokens"] / len(win_m)
    es, _ = _analyze(ds, a)
    value = {}
    for e in es:
        value[e.department] = value.get(e.department, 0.0) + e.value
    per = {}
    for d, tok in tokens.items():
        share = ROUTINE_SHARE.get(d, 0.5)
        routed = tok * share
        saving = routed / 1e6 * max(0.0, TOKEN_PRICE_PER_M - a.cheap_price_per_m)
        risk = a.quality_penalty * share * value.get(d, 0.0)
        per[d] = dict(routine_share=share, monthly_tokens_m=round(tok / 1e6, 1), saving=round(saving, 2),
                      value_at_risk=round(risk, 2), net_gain=round(saving - risk, 2))
    tot = lambda k: round(sum(v[k] for v in per.values()), 2)  # noqa: E731
    return dict(frontier_price=TOKEN_PRICE_PER_M, cheap_price=a.cheap_price_per_m, quality_penalty=a.quality_penalty,
                saving=tot("saving"), value_at_risk=tot("value_at_risk"), net_gain=tot("net_gain"),
                by_department=dict(sorted(per.items(), key=lambda kv: -kv[1]["net_gain"])))


# ---------------------------------------------------------------- spend trend and drift alerts

def trend(ds: Dataset, drift: float = 0.15, min_dollars: float = 500.0) -> dict:
    months = sorted({r["month"] for r in ds.rows})
    series: dict[str, dict[str, float]] = {}
    for r in ds.rows:
        s = series.setdefault(r["department"], {m: 0.0 for m in months})
        s[r["month"]] += r["seat_cost"] + r["token_cost"]
    alerts = []
    for d, s in series.items():
        vals = [s[m] for m in months]
        if len(vals) >= 3 and vals[-2] > 0:
            prev, last = vals[-2], vals[-1]
            if last > prev * (1 + drift) and last - prev > min_dollars:
                alerts.append(dict(department=d, month=months[-1], previous=round(prev), latest=round(last),
                                   change=round(last / prev - 1, 3)))
    total = [round(sum(series[d][m] for d in series)) for m in months]
    return dict(months=months, company=total, alerts=sorted(alerts, key=lambda x: -x["change"]),
                by_department={d: [round(s[m]) for m in months] for d, s in sorted(series.items())})


# ---------------------------------------------------------------- policies

@dataclass
class Policy:
    name: str
    description: str
    seat_fee: float | None = None        # flat $/seat/month; None = each person's actual seat cost
    reclaim_idle: bool = False           # idle employees lose the seat
    cap_mode: str = "none"               # none | flat | role
    flat_cap: float = 0.0                # monthly token $ cap per employee
    cap_pctile: float = 0.75             # for role mode: percentile of ROI-positive peer spend
    pooled: bool = False                 # unused allowance pooled within a department
    price_multiplier: float = 1.0        # list-price premium when buying tokens without a seat plan
    friction: float = 0.0                # share of value lost because people ration use they can see being metered
    extra: dict = field(default_factory=dict)


def _seat(e: Employee, p: Policy) -> float:
    return e.seat_cost if p.seat_fee is None else p.seat_fee


def _run(es: list[Employee], a: Assumptions, p: Policy, caps: dict, peak: bool) -> tuple[float, float]:
    """Cost and value of a policy. peak=True prices every person at their own worst month."""
    cost = value = 0.0
    dept_budget: dict[str, float] = {}
    dept_demand: dict[str, float] = {}
    dept_people: dict[str, list[Employee]] = {}
    for e in es:
        if p.reclaim_idle and e.segment == "idle":
            cost += e.seat_cost * (1 - a.seat_savings_realized)  # contract minimums: part of the seat is still owed
            continue
        cap = None
        if p.cap_mode == "flat":
            cap = p.flat_cap
        elif p.cap_mode == "role":
            cap = _cap_for(e, caps)
        spend = (e.peak_token_cost if peak else e.token_cost) * p.price_multiplier
        if cap is not None and p.pooled:
            dept_budget[e.department] = dept_budget.get(e.department, 0.0) + cap
            dept_demand[e.department] = dept_demand.get(e.department, 0.0) + spend
            dept_people.setdefault(e.department, []).append(e)
            continue
        kept = 1.0
        if cap is not None and spend > cap:
            kept = (cap / spend) ** a.elasticity
            spend = cap
        cost += _seat(e, p) + spend
        value += e.value * kept * (1 - p.friction)
    for d, bud in dept_budget.items():
        dem = dept_demand[d]
        spent = min(dem, bud)
        kept = (spent / dem) ** a.elasticity if dem else 1.0
        cost += sum(_seat(e, p) for e in dept_people[d]) + spent
        value += sum(e.value for e in dept_people[d]) * kept * (1 - p.friction)
    return cost, value


def simulate(ds: Dataset, a: Assumptions, p: Policy) -> dict:
    es = employees(ds, a)
    caps = _caps(es, a, p.cap_pctile) if p.cap_mode == "role" else {}
    cost, value = _run(es, a, p, caps, peak=False)
    worst, _ = _run(es, a, p, caps, peak=True)
    return dict(name=p.name, description=p.description, monthly_cost=round(cost, 2),
                monthly_value=round(value, 2), net=round(value - cost, 2),
                roi=round((value - cost) / cost, 3) if cost else 0.0,
                worst_case_cost=round(worst, 2),
                bill_risk=round(worst / cost - 1, 3) if cost else 0.0)


def standard_policies(a: Assumptions | None = None) -> list[Policy]:
    a = a or Assumptions()
    return [
        Policy("Status quo", "Everyone keeps a seat; token spend is uncapped."),
        Policy("Fixed budget", "Flat $60 token cap for everyone, seats unchanged.", cap_mode="flat", flat_cap=60.0),
        Policy("Pay per use", f"No seats. Tokens bought at list price ({a.ppu_multiplier:g}x the seat-plan rate), "
               f"uncapped. Assumes {a.ppu_friction:.0%} less use because people see the meter.",
               seat_fee=0.0, price_multiplier=a.ppu_multiplier, friction=a.ppu_friction),
        Policy("Variable by role", "Seats only for active users; token cap set per department and level from what "
               "ROI-positive peers actually spend; unused allowance pooled in the department.",
               reclaim_idle=True, cap_mode="role", pooled=True),
    ]


POLICY_ASSUMPTIONS = [
    "Value kept under a cap is (cap / usage)^elasticity. Elasticity is a slider, not a measurement.",
    "Reclaiming a seat saves only the 'seat savings realized' share: annual commits and notice periods mean some cost is still owed.",
    "Pay per use assumes list-price tokens cost a multiple of the seat-plan rate and that people ration metered use. Both are set in the assumptions, and the break-even price below shows how much the result depends on them.",
    "Bill risk = extra monthly cost if everyone spends at their own highest month in the window.",
    "Seats not in use produce no AI value by definition; reassigning them is assumed to cost no output.",
]


def compare_policies(ds: Dataset, a: Assumptions) -> list[dict]:
    rows = [simulate(ds, a, p) for p in standard_policies(a)]
    best_net = max(rows, key=lambda r: r["net"])["name"]
    safest = min(rows, key=lambda r: r["bill_risk"])["name"]
    for r in rows:  # computed here so the model never has to compare rows itself
        r["highest_net"] = r["name"] == best_net
        r["lowest_bill_risk"] = r["name"] == safest
    return rows


def pay_per_use_breakeven(ds: Dataset, a: Assumptions) -> dict:
    """List-price multiplier at which pay per use stops being the highest-net policy (bisection)."""
    others = max(simulate(ds, a, p)["net"] for p in standard_policies(a) if p.name != "Pay per use")

    def ppu_net(m: float) -> float:
        from dataclasses import replace
        pol = next(p for p in standard_policies(a) if p.name == "Pay per use")
        return simulate(ds, a, replace(pol, price_multiplier=m))["net"]

    lo, hi = 0.5, 12.0
    if ppu_net(lo) < others:
        return dict(multiplier=None, note="Pay per use is never the best policy at any price.", assumed=a.ppu_multiplier)
    if ppu_net(hi) > others:
        return dict(multiplier=None, note=f"Pay per use stays best even at {hi:g}x list price.", assumed=a.ppu_multiplier)
    for _ in range(30):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ppu_net(mid) > others else (lo, mid)
    m = round((lo + hi) / 2, 2)
    return dict(multiplier=m, assumed=a.ppu_multiplier, still_best=a.ppu_multiplier < m,
                note=f"Pay per use is the highest-net policy only while list price stays under {m}x the seat-plan rate.")


def plan_savings(ds: Dataset, a: Assumptions) -> dict:
    """Where the 'Variable by role' plan's saving comes from, per department, and what it leaves on the table."""
    from dataclasses import replace
    es = employees(ds, a)
    caps = _caps(es, a, 0.75)
    plan = next(p for p in standard_policies(a) if p.name == "Variable by role")
    hard = replace(plan, pooled=False)  # same caps, enforced per person instead of pooled in the department
    sq = Policy("Status quo", "")

    def part(group: list[Employee]) -> dict:
        c0, v0 = _run(group, a, sq, caps, False)
        c1, v1 = _run(group, a, plan, caps, False)
        c2, v2 = _run(group, a, hard, caps, False)
        seats = sum(e.seat_cost for e in group if e.segment == "idle") * a.seat_savings_realized
        return dict(headcount=len(group), cost_now=round(c0, 2), cost_plan=round(c1, 2),
                    per_head_now=round(c0 / len(group), 2), per_head_plan=round(c1 / len(group), 2),
                    saving=round(c0 - c1, 2), from_seats=round(seats, 2), from_caps=round(c0 - c1 - seats, 2),
                    hard_cap_saving=round(c0 - c2, 2), hard_cap_value_lost=round(v0 - v2, 2))
    depts = {d: part([e for e in es if e.department == d]) for d in sorted({e.department for e in es})}
    return dict(company=part(es), by_department=depts)


def budget_recommendations(ds: Dataset, a: Assumptions) -> dict:
    """Per-department verdict: fixed or variable, and a per-head monthly budget by level."""
    es = employees(ds, a)
    caps = _caps(es, a, 0.75)
    plan = plan_savings(ds, a)["by_department"]
    out = {}
    for d in sorted({e.department for e in es}):
        group = [e for e in es if e.department == d]
        active = [e for e in group if e.treated]
        spend = [e.token_cost for e in active]
        mean = st.mean(spend) if spend else 0.0
        cv = (st.pstdev(spend) / mean) if mean else 0.0
        roll = _roll(group, a)
        if roll["roi"] < 0 and roll["confidence"] == "clear":
            verdict, reason = "restrict", ("ROI is negative and the range stays below zero. Cut seats to active "
                                           "users and cap spend until usage is tied to outcomes.")
        elif roll["roi"] < 0:
            verdict, reason = "review", ("ROI looks negative but the range includes zero, so the data cannot "
                                         "confirm a loss. Reassign unused seats and review high-spend usage with the teams; do not "
                                         "restrict everyone yet. Re-measure next quarter.")
        elif cv > 0.8:
            verdict, reason = "variable", (f"Spend varies widely between active people (CV {cv:.2f}), so a flat "
                                           "budget would overpay some and starve others.")
        else:
            verdict, reason = "fixed", (f"Spend is similar across active people (CV {cv:.2f}), so a predictable "
                                        "per-seat budget is simple and fair.")
        seat = round(st.median(e.seat_cost for e in group), 2)
        by_level = {lv: round(caps[(d, lv)], 2) for (dd, lv) in caps if dd == d and lv is not None}
        out[d] = dict(
            verdict=verdict, reason=reason, spend_cv=round(cv, 2), confidence=roll["confidence"],
            active_share=round(len(active) / len(group), 2), recommended_seat=seat,
            recommended_token_cap=round(caps.get((d, None), 0.0), 2), token_cap_by_level=by_level,
            ceiling_per_head=round(seat + caps.get((d, None), 0.0), 2),  # most one active person may use: seat + cap
            current_per_head=roll["cost_per_head"], expected_per_head=plan[d]["per_head_plan"],
            saving_monthly=plan[d]["saving"], saving_from_seats=plan[d]["from_seats"],
            saving_from_caps=plan[d]["from_caps"], dept_roi=roll["roi"],
        )
    return out


# ---------------------------------------------------------------- does the analysis find what is really there?

def validate(ds: Dataset, a: Assumptions) -> dict:
    """Score the analysis against the generator's hidden labels. Only meaningful on synthetic data."""
    if not ds.truth:
        return {}
    es = employees(ds, a)
    seg = {e.employee_id: e.segment for e in es}

    def pr(flagged: set[str], positive: set[str]) -> dict:
        tp = len(flagged & positive)
        return dict(precision=round(tp / len(flagged), 3) if flagged else 0.0,
                    recall=round(tp / len(positive), 3) if positive else 0.0,
                    flagged=len(flagged), actual=len(positive))

    ids = set(seg)
    idle = {i for i in ids if seg[i] == "idle"}
    over = {i for i in ids if seg[i] == "high-spend"}
    never = {i for i in ids if ds.truth[i]["archetype"] in ("unused", "light")}
    heavy = {i for i in ids if ds.truth[i]["archetype"] == "heavy_no_gain"}
    no_value = {i for i in ids if ds.truth[i]["archetype"] in ("heavy_no_gain", "light", "unused")}
    flagged_no_value = {i for i in ids if seg[i] in ("idle", "high-spend", "low-return")}
    s = summary(ds, a)["company"]
    return dict(
        idle_seats=pr(idle, {i for i in ids if ds.truth[i]["archetype"] == "unused"}) | {"vs": "seats never used"},
        idle_vs_nonusers=pr(idle, never) | {"vs": "never or barely used"},
        high_spend=pr(over, heavy) | {"vs": "heavy use with no real gain"},
        no_value=pr(flagged_no_value, no_value) | {"vs": "no real gain"},
        naive_vs_did=dict(naive_lift=s["naive_lift"], did_lift=s["did_lift"],
                          trend_removed=round(s["naive_lift"] - s["did_lift"], 4)),
        messy=dict(part_time=sum(1 for i in ids if ds.truth[i]["part_time"]),
                   new_hires=sum(1 for i in ids if ds.truth[i]["new_hire"]),
                   on_leave=sum(1 for i in ids if ds.truth[i]["leave"])),
    )


# ---------------------------------------------------------------- how much of this is opinion?

KINDS = dict(
    measured=["Seats and token spend per person", "Sessions per month (what makes a seat unused)",
              "Output per person per month"],
    estimated=["AI effect on output: control group, shrinkage, 95% ranges", "Department ROI ranges",
               "Whether adopters were already pulling ahead before rollout"],
    assumed=["Realization: share of the extra output that is bankable value (slider)",
             "Elasticity: how much value is lost when spend is capped (slider)",
             "Pay-per-use list price and rationing (slider; break-even price shown)",
             "Seat savings realized after contract minimums",
             "Routine share of tokens and the cheaper model's price and quality (slider)",
             "Hourly rate by level: value is time saved times rate"],
    judgement=["Peer norms: what spend is 'high' compared with colleagues of the same role and level",
               "The 75th-percentile team budget, floored at the department level for interns and juniors"],
)

GRID = dict(realization=(0.25, 0.35, 0.5, 0.75, 1.0), elasticity=(0.2, 0.5, 0.8),
            ppu_multiplier=(1.2, 1.6, 2.0, 2.6), seat_savings_realized=(0.5, 0.8, 1.0))


def robustness(ds: Dataset, a: Assumptions) -> dict:
    """Re-run the conclusions across a grid of the assumptions that are opinion, and report how often each holds."""
    from dataclasses import replace
    from itertools import product
    cache = ds.__dict__.setdefault("_rob", {})
    ckey = tuple(sorted(a.__dict__.items()))
    if ckey in cache:
        return cache[ckey]
    claims = {
        "reassign_unused": "Reassigning unused seats raises net value",
        "vbr_beats_status_quo": "Variable by role beats the status quo on net dollars",
        "fixed_beats_status_quo": "A fixed $60 cap beats the status quo on net dollars",
        "ppu_highest": "Pay per use has the highest net of the four policies",
        "company_positive": "Company-wide AI spend returns more than it costs (ROI above 0)",
    }
    held = {k: 0 for k in claims}
    dept_pos: dict[str, int] = {}
    n = 0
    names = list(GRID)
    for combo in product(*(GRID[k] for k in names)):
        b = replace(a, **dict(zip(names, combo)))
        pol = {r["name"]: r for r in compare_policies(ds, b)}
        sq = pol["Status quo"]
        n += 1
        held["reassign_unused"] += (
            simulate(ds, b, Policy("r", "", reclaim_idle=True))["net"] > sq["net"])
        held["vbr_beats_status_quo"] += pol["Variable by role"]["net"] > sq["net"]
        held["fixed_beats_status_quo"] += pol["Fixed budget"]["net"] > sq["net"]
        held["ppu_highest"] += pol["Pay per use"]["highest_net"]
        held["company_positive"] += sq["roi"] > 0
        for d, v in summary(ds, b)["departments"].items():
            dept_pos[d] = dept_pos.get(d, 0) + (v["roi"] > 0)
    decisions = [dict(id=k, claim=c, holds=round(held[k] / n, 3),
                      verdict=("robust" if held[k] / n >= 0.95 else "depends on assumptions"
                               if held[k] / n > 0.05 else "robustly false")) for k, c in claims.items()]
    depts = {d: dict(roi_positive=round(v / n, 3),
                     verdict="positive" if v / n >= 0.95 else "negative" if v / n <= 0.05 else "depends on assumptions")
             for d, v in sorted(dept_pos.items())}
    notes = {"reassign_unused": "True by construction: a seat with no usage produces no AI value. Whether to reassign it "
                                "is a conversation with the team, which only they can settle."}
    for d in decisions:
        d["note"] = notes.get(d["id"], "")
    out = dict(scenarios=n, grid={k: list(v) for k, v in GRID.items()}, kinds=KINDS,
               decisions=decisions, departments=depts)
    if len(cache) > 8:
        cache.clear()
    cache[ckey] = out
    return out


# ---------------------------------------------------------------- show the working

def _m(x: float) -> str:
    return f"${x:,.0f}"


def _p(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


def explain(ds: Dataset, a: Assumptions, dept: str | None = None) -> dict:
    """Step-by-step derivation of one department's ROI with its own numbers. Aggregates only, no individuals."""
    es, stats = _analyze(ds, a)
    sel = selection(ds, a)
    depts = sorted(stats)
    dept = dept if dept in stats else depts[0]
    st_ = stats[dept]
    g = [e for e in es if e.department == dept]
    tr = [e for e in g if e.treated]
    un = [e for e in g if not e.treated]
    n, k = len(g), len(tr)
    seat = st.mean(e.seat_cost for e in g)
    tok = st.mean(e.token_cost for e in g)
    cost = sum(e.cost for e in g)
    value = sum(e.value for e in g)
    roll = _roll(g, a)
    mean = lambda f: st.mean(f(e) for e in tr) if tr else 0.0  # noqa: E731
    base, hpu, rate = mean(lambda e: e.base), mean(lambda e: e.hpu), mean(lambda e: e.rate)  # type: ignore[attr-defined]
    lift = mean(lambda e: e.lift)
    caps = _caps(es, a, 0.75)
    hs = [e for e in g if e.segment == "high-spend"]
    over = sum(max(0.0, e.token_cost - _cap_for(e, caps)) for e in hs)
    steps = [
        dict(title="1. What it costs",
             formula="cost per person = seat price + average token spend, over the last %d months" % a.window_months,
             working=f"{n:,} people. Seat {_m(seat)} + tokens {_m(tok)} = {_m(seat + tok)} per head.",
             result=f"{_m(cost)} a month"),
        dict(title="2. Who is using AI",
             formula=f"using = average at least {a.idle_sessions:g} sessions a month. Everyone else is the control group.",
             working=f"{k:,} people use it. {len(un):,} do not and become the comparison group.",
             result=f"{k:,} users, {len(un):,} unused seats"),
        dict(title="3. How much did output grow?",
             formula="growth = output in the last months / own output in the first %d months - 1" % a.pre_months,
             working=f"People using AI grew {_p(st_['naive_lift'])}. People not using it grew {_p(st_['control_raw'])}.",
             result=f"{_p(st_['naive_lift'])} vs {_p(st_['control_raw'])}"),
        dict(title="4. Remove what would have happened anyway",
             formula="control growth to use = (1 + non-user growth) x (1 + pre-rollout gap per month)^months. "
                     "AI effect = (1 + user growth) / (1 + control growth to use) - 1",
             working=(f"Pre-rollout gap between the two groups: {_p(sel['gap_per_month'], 2)} a month over "
                      f"{sel['horizon']:g} months, so control growth to use = {_p(st_['control_growth'])}. "
                      f"(1 + {_p(st_['naive_lift'])}) / (1 + {_p(st_['control_growth'])}) - 1."),
             result=f"AI effect {_p(st_['did_lift'])} of baseline output"),
        dict(title="5. How sure are we?",
             formula="standard error = sqrt(var(users)/n users + var(control)/n control), plus the uncertainty of the "
                     "pre-rollout gap. 95% range = effect +/- 1.96 x standard error",
             working=f"Standard error {_p(st_['se'], 2)}. Range {_p(st_['ci_low'])} to {_p(st_['ci_high'])}. "
                     f"{st_['treated_n']} users, {st_['control_n']} in the control group"
                     f"{' (pooled company-wide: too few in this department)' if st_['control_pooled'] else ''}.",
             result=f"{_p(st_['ci_low'])} to {_p(st_['ci_high'])}"),
        dict(title="6. Shrink noisy individual estimates",
             formula="each person's effect = department effect + w x (their own - department effect), "
                     "w = 1 - control variance / user variance, never below 0",
             working=f"w = {st_['shrink']:.2f}. A low w means individual numbers are mostly noise, so they are pulled "
                     "toward the department average. Nobody is ranked on their own number.",
             result=f"w = {st_['shrink']:.2f}"),
        dict(title="7. Turn the effect into dollars",
             formula="value per user = realization x effect x baseline output x hours per unit x hourly rate",
             working=(f"Typical user: {_p(a.realization, 0)} x {_p(lift)} x {base:,.1f} units x {hpu:g} h x ${rate:,.0f}/h "
                      f"= {_m(a.realization * lift * base * hpu * rate)} a month. Summed over every user (each with their "
                      f"own numbers): {_m(value)}. Idle seats are valued at 0."),
             result=f"{_m(value)} a month (range {_m(roll['value_low'])} to {_m(roll['value_high'])})"),
        dict(title="8. ROI and break-even",
             formula="ROI = (value - cost) / cost.  Break-even credit = realization x cost / value",
             working=f"({_m(value)} - {_m(cost)}) / {_m(cost)} = {roll['roi']:.2f}. "
                     + (f"Break-even credit = {_p(a.realization, 0)} x {_m(cost)} / {_m(value)} = {_p(roll['break_even_realization'], 0)}"
                        if roll["break_even_realization"] else "No value estimated, so it never breaks even."),
             result=f"ROI {roll['roi']:.2f} (range {roll['roi_low']:.2f} to {roll['roi_high']:.2f}), {roll['confidence']}"),
        dict(title="9. Recoverable spend in this department",
             formula=f"unused seats x seat price x {_p(a.seat_savings_realized, 0)} realized + sum of (spend above the peer cap) "
                     "on high-spend seats",
             working=f"{len(un):,} x {_m(seat)} x {_p(a.seat_savings_realized, 0)} = {_m(len(un) * seat * a.seat_savings_realized)}; "
                     f"{len(hs)} high-spend seats, {_m(over)} above their peer cap.",
             result=f"{_m(len(un) * seat * a.seat_savings_realized + over)} a month"),
    ]
    return dict(department=dept, departments=depts, steps=steps)


def explain_policies(ds: Dataset, a: Assumptions) -> list[dict]:
    es = employees(ds, a)
    pols = compare_policies(ds, a)
    cap60 = sum(1 for e in es if e.token_cost > 60)
    idle = [e for e in es if e.segment == "idle"]
    by = {r["name"]: r for r in pols}
    f = lambda r: f"cost {_m(r['monthly_cost'])}, value {_m(r['monthly_value'])}, net {_m(r['net'])}"  # noqa: E731
    return [
        dict(policy="Status quo", formula="cost = sum(seat + token spend). value = sum(each person's value).",
             working=f(by["Status quo"])),
        dict(policy="Fixed budget",
             formula="spend above the cap is cut to the cap; value kept = (cap / spend)^elasticity",
             working=f"{cap60} people spend over $60. Elasticity {a.elasticity:g}. " + f(by["Fixed budget"])),
        dict(policy="Pay per use",
             formula="no seats. cost = tokens x list-price multiplier. value x (1 - ration rate)",
             working=f"multiplier {a.ppu_multiplier:g}, ration {_p(a.ppu_friction, 0)}. " + f(by["Pay per use"])),
        dict(policy="Variable by role",
             formula="unused seats reassigned (cost left = seat x (1 - realized)); active people share a department "
                     "pool = sum of their peer caps; value x (spend / demand)^elasticity if the pool binds",
             working=f"{len(idle)} unused seats, {_p(a.seat_savings_realized, 0)} of their cost realized. " + f(by["Variable by role"])),
        dict(policy="Bill risk",
             formula="bill risk = cost if everyone spends at their own highest month / cost - 1",
             working="; ".join(f"{r['name']} {_m(r['worst_case_cost'])} / {_m(r['monthly_cost'])} - 1 = {_p(r['bill_risk'], 0)}"
                               for r in pols)),
    ]
