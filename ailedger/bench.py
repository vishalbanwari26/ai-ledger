"""Benchmarks that put published findings to work on this company's numbers.

  breakeven   how large an AI effect on output this spend needs in order to pay for itself
  scenarios   the same company's return if the true effect matched each published output study
  by_level    the measured effect for less and more experienced people, next to what studies found
  perception  what employees say AI does for them against what was measured

All of it is arithmetic on the tool's own estimates plus the verified figures in `evidence.py`. Nothing here changes
the estimates. Published effects are for people who used AI, so they are applied to the people the tool counts as users.
"""
from __future__ import annotations

import statistics as st

from . import analysis as an
from . import evidence as ev
from .data import Dataset

Z95 = 1.96
NEAR_MISS_SHARE = 0.25  # a margin under this share of the range's half-width is reported as 'only just'


def _value_per_unit_effect(es: list[an.Employee], a: an.Assumptions) -> float:
    """Dollars of monthly value per 1.00 (100%) of effect, if every user gained the same share of their baseline."""
    return sum(a.realization * e.base * e.unit_value for e in es if e.treated)


def _fixed_benefit(es: list[an.Employee]) -> float:
    return sum(e.benefit for e in es if e.treated)


def breakeven(ds: Dataset, a: an.Assumptions) -> dict:
    es, stats = an._analyze(ds, a)
    c = an.summary(ds, a)["company"]

    def one(group: list[an.Employee], measured: float, lo: float, hi: float) -> dict:
        cost, s, fixed = sum(e.cost for e in group), _value_per_unit_effect(group, a), _fixed_benefit(group)
        be = max(0.0, cost - fixed) / s if s else None
        if be is None:
            verdict = "no users"
        elif lo > be:  # a small margin is "just", not "clearly"
            verdict = ("above break-even, but only just: the low end of the range is at it" if (lo - be) < NEAR_MISS_SHARE * (measured - lo)
                       else "clearly above break-even")
        elif hi < be:
            verdict = ("below break-even, but only just: the top of the range is at it" if (be - hi) < NEAR_MISS_SHARE * (hi - measured)
                       else "clearly below break-even")
        else:
            verdict = "not distinguishable from break-even"
        return dict(cost=round(cost, 2), breakeven=None if be is None else round(be, 4), measured=round(measured, 4),
                    low=round(lo, 4), high=round(hi, 4), verdict=verdict,
                    headroom=None if be is None else round(measured - be, 4))
    out = dict(company=one(es, c["did_lift"], c["did_ci_low"], c["did_ci_high"]), by_department={})
    for d, s_ in stats.items():
        out["by_department"][d] = one([e for e in es if e.department == d], s_["did_lift"], s_["ci_low"], s_["ci_high"])
    pub = ev.published_output_range()
    be = out["company"]["breakeven"]
    out["published"] = pub
    out["published_clear_it"] = None if be is None else pub["min"] / 100 > be
    return out


def scenarios(ds: Dataset, a: an.Assumptions) -> list[dict]:
    es, _ = an._analyze(ds, a)
    cost, s, fixed = sum(e.cost for e in es), _value_per_unit_effect(es, a), _fixed_benefit(es)
    c = an.summary(ds, a)["company"]
    rows = [("No effect", 0.0, "scenario"), ("Your measured effect", c["did_lift"], "measured")]
    seen: set[float] = set()
    for x in sorted((x for x in ev.STUDIES if x["metric"] == "output"), key=lambda x: x["value"]):
        if x["value"] in seen:
            continue
        seen.add(x["value"])
        rows.append((f"{x['short']} ({x['year']})", x["value"] / 100, x["id"]))
    out = []
    for label, e, key in rows:
        v = e * s + fixed
        out.append(dict(label=label, key=key, effect=round(e, 4), value=round(v, 2), net=round(v - cost, 2),
                        back_per_dollar=round(v / cost, 3) if cost else 0.0, pays_off=v >= cost))
    return out


def by_level(ds: Dataset, a: an.Assumptions) -> dict:
    """Measured AI effect by experience level, with the same control-group method as the departments."""
    es, stats = an._analyze(ds, a)
    sel = an.selection(ds, a)
    drift = (1 + sel["gap_per_month"]) ** sel["horizon"] if sel["adjusted"] else 1.0
    company_ctrl = [e.growth for e in es if not e.treated and e.growth is not None]

    def effect(group: list[an.Employee]) -> dict:
        tr = [e.growth for e in group if e.treated and e.growth is not None]
        ct = [e.growth for e in group if not e.treated and e.growth is not None]
        pooled = len(ct) < a.min_cohort
        if pooled:
            ct = company_ctrl
        if len(tr) < 2 or not ct:
            return dict(effect=None, low=None, high=None, treated=len(tr), control=len(ct), pooled=pooled)
        c_eff = (1 + st.mean(ct)) * drift - 1
        did = (1 + st.mean(tr)) / (1 + c_eff) - 1
        se = ((an._var(tr) / len(tr) + an._var(ct) / len(ct)) / (1 + c_eff) ** 2) ** 0.5
        se = (se ** 2 + ((1 + did) * sel["horizon"] * sel["se"] if sel["adjusted"] else 0.0) ** 2) ** 0.5
        return dict(effect=round(did, 4), low=round(did - Z95 * se, 4), high=round(did + Z95 * se, 4), se=se,
                    treated=len(tr), control=len(ct), pooled=pooled)
    levels = []
    for lv in ("intern", "junior", "mid", "senior"):
        g = [e for e in es if e.level == lv]
        if g:
            levels.append(dict(level=lv, people=len(g)) | {k: v for k, v in effect(g).items() if k != "se"})
    nov, exp = effect([e for e in es if e.level in an.LEARNING_LEVELS]), effect([e for e in es if e.level not in an.LEARNING_LEVELS])
    if nov["effect"] is None or exp["effect"] is None:
        verdict, diff = "not enough people to compare", None
    else:
        diff = nov["effect"] - exp["effect"]
        se = (nov["se"] ** 2 + exp["se"] ** 2) ** 0.5
        if abs(diff) <= Z95 * se:
            verdict = "no clear difference between less and more experienced people"
        else:
            verdict = "less experienced people gain more" if diff > 0 else "more experienced people gain more"
    return dict(levels=levels, difference=None if diff is None else round(diff, 4), verdict=verdict,
                published=[dict(study="Brynjolfsson et al. 2023", text="Novice and low-skilled support agents gained 34%; experienced agents saw minimal impact."),
                           dict(study="Cui et al. 2025", text="Less experienced developers had higher adoption and greater productivity gains.")])


def perception(ds: Dataset, a: an.Assumptions, self_reported_pct: float) -> dict:
    """Compare what employees say AI does for their output with what the tool measured."""
    c = an.summary(ds, a)["company"]
    est, lo, hi = c["did_lift"] * 100, c["did_ci_low"] * 100, c["did_ci_high"] * 100
    gap = self_reported_pct - est
    if self_reported_pct > hi:
        verdict, text = "overstated", (f"Employees say {ev.p1(self_reported_pct)}%. The measured effect is {ev.p1(est)}% (range {ev.p1(lo)}% to {ev.p1(hi)}%). "
                                       f"Their own estimate is {ev.p1(gap)} points above even the top of the range.")
    elif self_reported_pct < lo:
        verdict, text = "understated", (f"Employees say {ev.p1(self_reported_pct)}%. The measured effect is {ev.p1(est)}% (range {ev.p1(lo)}% to {ev.p1(hi)}%): "
                                        f"they credit AI with less than the data shows.")
    else:
        verdict, text = "consistent", (f"Employees say {ev.p1(self_reported_pct)}%, inside the measured range ({ev.p1(lo)}% to {ev.p1(hi)}%) around {ev.p1(est)}%.")
    return dict(self_reported=self_reported_pct, measured=round(est, 2), low=round(lo, 2), high=round(hi, 2), gap=round(gap, 2),
                verdict=verdict, text=text,
                note="In METR's trial, experienced developers expected a 24% speedup and afterwards believed they had been 20% "
                     "faster, while the measured result was 19% slower. One study, early-2025 tools, but it is why this tool "
                     "measures output instead of relying on what people report.")


def speed_effects(ds: Dataset, a: an.Assumptions) -> dict:
    """For departments measured by speed: the change in time per task (negative = faster), comparable with the time studies.
    A rate gain g means time falls to 1 / (1 + g), so the time change is 1 / (1 + g) - 1."""
    es, stats = an._analyze(ds, a)
    rows, lo_w, hi_w, est_w, n_tot = {}, 0.0, 0.0, 0.0, 0
    for d, s in stats.items():
        sp = an.dept_speed(a, d)
        if not sp:
            continue
        t = lambda g: 1 / (1 + g) - 1  # noqa: E731
        n = s["treated_n"]
        rows[d] = dict(metric=sp[0], effect=round(t(s["did_lift"]), 4), low=round(t(s["ci_high"]), 4), high=round(t(s["ci_low"]), 4), users=n)
        est_w += t(s["did_lift"]) * n; lo_w += t(s["ci_high"]) * n; hi_w += t(s["ci_low"]) * n; n_tot += n
    if not rows:
        return dict(departments={}, combined=None)
    return dict(departments=rows, combined=dict(effect=round(est_w / n_tot, 4), low=round(lo_w / n_tot, 4), high=round(hi_w / n_tot, 4), users=n_tot))


def bundle(ds: Dataset, a: an.Assumptions) -> dict:
    """Everything the Evidence tab and the analyst need, in one object."""
    company = an.summary(ds, a)["company"]
    return ev.payload(company) | dict(breakeven=breakeven(ds, a), scenarios=scenarios(ds, a), by_level=by_level(ds, a), speed=speed_effects(ds, a))
