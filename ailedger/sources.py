"""Where every value in the tool comes from.

Each entry reads its value from the live code constant, so a reference cannot drift from what the tool actually uses.
An entry says what the value is, which kind of origin it has, where it is used, why it was chosen, and links to what
supports it. Honest labels matter more than impressive ones: most dollar figures are assumptions, and the page says so.

Kinds
  published   taken from a published study (the study is linked)
  list-price  anchored to a public price list that was read on the date shown
  convention  a standard statistical convention
  design      our method choice, tested in docs/robustness.md
  judgement   our rule of thumb; change it if you disagree
  assumption  our guess with no source; a slider or a quote from your vendor should replace it
  demo-data   invented for the synthetic demo company; upload your own data to replace it
  yours       a value you defined on the Your value tab
  data        computed from your data
"""
from __future__ import annotations

from . import analysis as an
from . import bench
from . import data as dt
from . import evidence as ev

READ_ON = "2026-10-18"

KINDS = {
    "published": "Taken from a published study",
    "list-price": "Anchored to a public price list",
    "convention": "Standard statistical convention",
    "design": "Our method choice (tested)",
    "judgement": "Our rule of thumb",
    "assumption": "Our assumption, no source",
    "demo-data": "Invented for the demo company",
    "yours": "Defined by you",
    "data": "Computed from your data",
}

REFS: dict[str, dict] = {
    "anthropic-pricing": dict(
        label="Anthropic API pricing", url="https://platform.claude.com/docs/en/about-claude/pricing", read=READ_ON, confirmed=True,
        says="Claude Sonnet 5.5: $2 input and $10 output per million tokens. Opus 5.5: $4 and $20. Fable 5.1: $10 and $50."),
    "claude-plans": dict(
        label="Claude plans and pricing", url="https://claude.com/pricing", read=READ_ON, confirmed=True,
        says="Team plan standard seat $20 a month billed annually ($25 monthly), premium seat $100 ($125 monthly). Enterprise: $20 "
             "per seat a month billed annually with a 20-seat minimum, usage charged on top at API rates."),
    "copilot-plans": dict(
        label="GitHub Copilot plans", url="https://github.com/features/copilot/plans", read=READ_ON, confirmed=True,
        says="Copilot Pro $10 a month, Pro+ $39, Max $100. Prices for Business and Enterprise are not listed on the page."),
    "nebius-prices-listing": dict(
        label="Nemotron prices on Nebius (third-party listing)",
        url="https://custom.typingmind.com/tools/estimate-llm-usage-costs/nebius/nemotron-3-5-lightning", read=READ_ON, confirmed=False,
        says="A third-party listing shows the smallest Nemotron models on Nebius at about $0.06 input and $0.24 output per million "
             "tokens, Super 120B at $0.30 and $0.90, Ultra 550B at $1.00 and $3.00. Nebius's own price page did not load here, so these "
             "are not confirmed."),
    "doc-robustness": dict(label="Stress tests (docs/robustness.md)", url="https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/robustness.md",
                           read=READ_ON, confirmed=True, says="Results of re-running the method on companies with a known true effect."),
    "doc-evidence": dict(label="Evidence and calibration (docs/evidence.md)", url="https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/evidence.md",
                         read=READ_ON, confirmed=True, says="What was read in each study, and how the demo company was calibrated."),
}
for _s in ev.STUDIES:
    REFS["study:" + _s["id"]] = dict(label=f"{_s['authors']} ({_s['year']})", url=_s["url"], read=ev.VERIFIED_ON,
                                     confirmed=True, says=_s["reported"])


def _pct(x: float, d: int = 0) -> str:
    return f"{x * 100:.{d}f}%"


def _entries(a: an.Assumptions) -> list[dict]:
    d0 = an.Assumptions()
    fixed = next(p for p in an.standard_policies(d0) if p.name == "Fixed budget")
    pub = ev.published_output_range()
    E: list[dict] = []

    def add(id, group, label, value, kind, where, why, refs=(), caveat="", slider=None, current=None):
        E.append(dict(id=id, group=group, label=label, value=value, kind=kind, where=where, why=why, refs=list(refs),
                      caveat=caveat, slider=slider, current=current))

    G1, G2, G3, G4, G5 = ("Dollars and prices", "How the effect is measured", "Rules of thumb", "Published numbers used",
                          "The demo company")
    yours = bool(an.value_defs(a))

    # ----- dollars and prices
    add("realization", G1, "Share of extra output counted as real value", _pct(d0.realization), "assumption",
        "Every dollar figure for value, ROI and break-even",
        "Extra output is not automatically extra money, so only part is counted. Half is a placeholder; the break-even credit "
        "on each department shows how much it matters.", ["study:humlum-2025"],
        "The Danish study is context for counting less than all of it (it found no effect on earnings or hours); it does not "
        "give 50%.", "realization", _pct(a.realization))
    add("value_unit", G1, "What one unit of output is worth", "hours per unit x hourly rate, from the data",
        "yours" if yours else "data", "Value per user, ROI, break-even, policies",
        "By default each department's own hours per unit and hourly rate from your data. Replace it with a dollar value per unit, "
        "or add a benefit per user, on the Your value tab.", caveat="In the demo company these rates and hours are invented (see demo-data entries).")
    add("output_unit", G1, "What counts as one unit of output", "the main outcome column, named by your data", "yours" if yours else "data",
        "The AI effect on output, value per unit, every dollar figure",
        "Your CSV's outcome_units column is the output, named by its unit_name column. You can rename it, or define output as a "
        "weighted mix of extra outcome_<name> columns, on the Your value tab.",
        caveat="In the demo company the unit names and extra metrics are invented.")
    add("seat_savings_realized", G1, "Share of a reclaimed seat's cost actually saved", _pct(d0.seat_savings_realized), "assumption",
        "Unused-seat savings, the plan's saving, the headline",
        "Contracts have minimums and notice periods, so not every cancelled dollar comes back.", ["claude-plans"],
        "The Claude Enterprise listing shows a 20-seat minimum and annual billing, so minimums exist; the 80% itself is ours.",
        None, _pct(a.seat_savings_realized))
    add("frontier_token_price", G1, "Blended price of a frontier model, per 1M tokens", f"${dt.TOKEN_PRICE_PER_M:.2f}", "assumption",
        "Token cost in the demo data, routing saving",
        "A blend of input and output prices at 3 input tokens for each output token. Sonnet 5.5 ($2 in, $10 out) blends to $4.00 and "
        "Opus 5.5 ($4 in, $20 out) to $8.00, so $5.00 sits between them.", ["anthropic-pricing"],
        "The 3-to-1 input-to-output mix is ours. Use your own invoices.")
    add("cheap_token_price", G1, "Price of the cheaper model for routine work, per 1M tokens", f"${d0.cheap_price_per_m:.2f}", "assumption",
        "Model routing estimate",
        "Deliberately above the listed price of the smallest Nemotron models (about $0.06 in and $0.24 out), to stay conservative.",
        ["nebius-prices-listing"], "The listing is third-party and not confirmed on Nebius's own page.", "cheap", f"${a.cheap_price_per_m:.2f}")
    add("quality_penalty", G1, "Value lost on tokens moved to the cheaper model", _pct(d0.quality_penalty), "assumption",
        "Model routing estimate", "A small penalty so routing is not shown as free. No measurement behind it.", caveat="Measure it on your own tasks.")
    add("routine_share", G1, "Share of tokens that are routine, by department",
        ", ".join(f"{k} {_pct(v)}" for k, v in an.ROUTINE_SHARE.items()), "assumption", "Model routing estimate",
        "A planning guess: how much of each department's use is summaries, drafts and lookups a smaller model could do.",
        caveat="Measure it on your own traffic before relying on it.")
    add("ppu_multiplier", G1, "List price of tokens without a seat plan, as a multiple of the seat-plan rate", f"{d0.ppu_multiplier:g}x", "assumption",
        "The pay-per-use policy and its break-even price", "A placeholder. The page shows the break-even multiplier, which matters more than this value.",
        ["claude-plans"], "Seat plans bundle usage and pay-as-you-go does not, so the multiple depends on your contract. Get a real quote.",
        "ppu", f"{a.ppu_multiplier:g}x")
    add("ppu_friction", G1, "Value lost because people ration metered use", _pct(d0.ppu_friction), "assumption", "The pay-per-use policy",
        "People tend to use a metered tool less. 5% is a small guess with no source.", caveat="Highly uncertain; try 20% to 40% in the policy sensitivity.")
    add("elasticity", G1, "How much value is lost when someone's allowance is cut", f"{d0.elasticity:g}", "assumption",
        "Fixed budget and token-cap policies: value kept = (cap / usage)^elasticity",
        "0 means no loss, 1 means value falls in step with usage. Half is a middle guess.", caveat="Not measured.", slider="elasticity", current=f"{a.elasticity:g}")
    add("fixed_cap", G1, "Token cap in the fixed-budget policy", f"${fixed.flat_cap:,.0f} per person a month", "judgement",
        "The fixed-budget policy", "A round figure near what a heavy user spends in the demo data.")

    # ----- how the effect is measured
    add("windows", G2, "Months used as baseline and as the measured window", f"first {d0.pre_months} and last {d0.window_months}", "design",
        "The AI effect, ROI, the chart of output over time",
        "Two baseline months let a person be compared with their own past. Three measured months let a median shrug off one month of leave.",
        ["doc-robustness"], "A 2-month window overstated the effect by about 2.9 points in the stress test.")
    add("idle_sessions", G2, "Sessions a month below which a seat counts as unused", f"{d0.idle_sessions:g}", "judgement",
        "Unused seats, control group, the headline", "A seat opened fewer than three times a month is not in meaningful use.",
        caveat="Changing it changes who is a user and who is in the control group.")
    add("pretrend", G2, "Remove a growth gap adopters already had before rollout", "on" if d0.adjust_pretrend else "off", "design",
        "The AI effect and its range", "If people who later adopted AI were already growing faster, that gap is extrapolated and removed, and a warning shows.",
        ["doc-robustness"], "Without it a +1% a month self-selection bias overstated the effect by 25% in the stress test.")
    add("z95", G2, "Multiplier for a 95% range", f"{an.Z95}", "convention", "Every range and confidence label",
        "Plus or minus 1.96 standard errors covers 95% of a normal distribution.")
    add("realization_scale_robust", G2, "Assumption values tried in the robustness check",
        f"realization {', '.join(_pct(x) for x in an.GRID['realization'])}; price multiple {', '.join(f'{x:g}x' for x in an.GRID['ppu_multiplier'])}", "judgement",
        "The 180-scenario robustness card", "A wide, plausible spread around each default. Wider ranges make fewer decisions look robust.")
    add("near_miss", G2, "Margin that counts as 'only just' above or below break-even", f"{_pct(bench.NEAR_MISS_SHARE)} of the range's half-width", "judgement",
        "The break-even verdict", "Stops a 0.03-point margin being called 'clearly' above break-even.")

    # ----- rules of thumb
    add("high_spend", G3, "A seat is 'high spend' above this multiple of its peers' median spend", f"{an.HIGH_SPEND_MULT:g}x", "judgement",
        "High-spend seats, the above-norm spend in the headline", "Peers are people of the same department and level; the rule also needs a negative ROI.",
        caveat="A flag to start a conversation, not a verdict. Precision is about 0.78 in the stress test.", slider=None)
    add("peer_percentile", G3, "Percentile of ROI-positive peers' spend used as the token cap", _pct(an.PEER_PERCENTILE), "judgement",
        "Token caps, the ceiling per active person, above-norm spend", "Generous enough that most heavy-but-productive users sit under it.")
    add("min_cohort", G3, "Smallest peer group that is compared on its own", f"{d0.min_cohort} people", "design",
        "Peer norms, caps and control groups", "Below this a group falls back to its whole department.", ["doc-robustness"])
    add("min_group", G3, "Smallest group ever shown", f"{d0.min_group} people", "design", "Every list, action and chart that groups people",
        "So no figure points at one person. Smaller groups are merged and then hidden.")
    add("drift", G3, "Monthly spend jump that raises a drift alert", f"{_pct(an.DRIFT_ALERT)} and at least ${an.DRIFT_MIN_DOLLARS:,.0f}", "judgement",
        "The drift alerts on spend over time", "Large enough to ignore ordinary variation.")
    add("learning_floor", G3, "Levels never capped below the department cap", ", ".join(an.LEARNING_LEVELS), "design",
        "Token caps by level", "Dollar ROI depends on hourly rate, so a peer norm would understate what learners need. Two studies also found less experienced people gain more.",
        ["study:brynjolfsson-2023", "study:cui-2025"])

    # ----- published numbers
    add("published_range", G4, "Range of published effects on output", f"{pub['min']:.1f}% to {pub['max']:.1f}% (median {pub['median']:.1f}%)", "published",
        "The Evidence tab, the comparison with your estimate, the what-if scenarios",
        "The smallest and largest output effects among the four studies that measure output.",
        ["study:dellacqua-2023", "study:brynjolfsson-2023", "study:murphy-hill-2026", "study:cui-2025"],
        "These studies follow volunteers and early adopters. A company-wide estimate is expected to be lower.")
    add("metr_perception", G4, "Developers' expected and believed speedup against the measured result", "expected 24% faster, believed 20% faster, measured 19% slower",
        "published", "The perception-gap check", "The reason the tool measures output instead of asking people.", ["study:becker-2025"],
        "One study, early-2025 tools.")
    add("novice_gain", G4, "Gain for novice and low-skilled workers", "34% (experienced workers: minimal impact)", "published",
        "The calibration of the demo company by level", "Used to set the intern lift multiplier.", ["study:brynjolfsson-2023"])
    add("archetype_lifts", G4, "Gain for power and steady users in the demo company (mid-level)",
        f"{_pct(dt.ARCHETYPES['power']['lift'])} and {_pct(dt.ARCHETYPES['steady']['lift'])}", "published", "The synthetic company's true effect",
        "Chosen inside the published adopter range so the demo reflects what studies found.",
        ["study:dellacqua-2023", "study:brynjolfsson-2023", "study:murphy-hill-2026", "study:cui-2025", "doc-evidence"],
        "The range is published; the two specific values are our choice within it.")
    add("level_lift", G4, "How much of the gain each level gets",
        ", ".join(f"{k} {v['lift']:g}x" for k, v in dt.LEVELS.items()), "published", "The synthetic company's true effect by level",
        "Set so a power-user intern gains about 35% (the novice figure) and a senior about 17%.", ["study:brynjolfsson-2023", "study:cui-2025", "doc-evidence"],
        "The direction is published; the exact multipliers are ours. 'Minimal impact' for experienced agents was read modestly for software.")

    # ----- the demo company
    add("seat_costs", G5, "Seat price per person a month", ", ".join(f"{k} ${v:,.0f}" for k, v in dt.SEAT_COSTS.items() if k in ("Engineering", "Sales")) + " (others as Sales)",
        "demo-data", "Cost, unused-seat savings, every policy",
        "$40 is close to a Copilot Pro+ seat or a Claude Team premium-seat range; $60 for engineers assumes a coding assistant plus a chat seat.",
        ["copilot-plans", "claude-plans"], "The $60 sum is ours; Copilot Business and Enterprise prices were not listed.")
    add("rates", G5, "Hours per unit and hourly rates by department",
        "; ".join(f"{k} {v[2]:g} h at ${v[3]}" for k, v in dt.ROLES.items()), "demo-data", "Value per unit of output",
        "Invented to look plausible. Replace by uploading your data or on the Your value tab.")
    add("company_trend", G5, "Company-wide output growth a month", _pct(dt.COMPANY_TREND, 1), "demo-data", "The busy-season effect the control group removes",
        "Built in so a naive before-and-after check would credit AI with growth that was not AI.")
    add("levels_units", G5, "Output, token use and pay by level",
        ", ".join(f"{k} output {v['units']:g}x, pay {v['rate']:g}x" for k, v in dt.LEVELS.items()), "demo-data", "The synthetic company", "Invented.")
    add("headcount", G5, "Headcount, usage mix and token multipliers by department",
        ", ".join(f"{k} {v:,}" for k, v in dt.HEADCOUNT.items()), "demo-data", "The synthetic company", "Invented to give a spread of behaviours.")
    return E


def registry(a: an.Assumptions | None = None) -> dict:
    a = a or an.Assumptions()
    entries = _entries(a)
    used = {r for e in entries for r in e["refs"]}
    refs = {k: v for k, v in REFS.items() if k in used}
    return dict(read_on=READ_ON, kinds=KINDS, entries=entries, refs=refs)


# Every adjustable assumption must be explained here. The test fails if a new one is added without a source note.
ENTRY_FIELDS = {
    "window_months": "windows", "pre_months": "windows", "realization": "realization", "elasticity": "elasticity",
    "idle_sessions": "idle_sessions", "seat_savings_realized": "seat_savings_realized", "friction": "ppu_friction",
    "min_cohort": "min_cohort", "min_group": "min_group", "adjust_pretrend": "pretrend", "ppu_multiplier": "ppu_multiplier",
    "ppu_friction": "ppu_friction", "cheap_price_per_m": "cheap_token_price", "quality_penalty": "quality_penalty",
    "value_json": "value_unit",
}
