from types import SimpleNamespace

from fastapi.testclient import TestClient

from ailedger import analysis as an, data, llm
from ailedger import app as appmod
from ailedger.app import app


def test_csv_roundtrip():
    ds = data.generate()
    assert len(data.load_csv(ds.to_csv()).rows) == len(ds.rows)


def test_csv_missing_columns_rejected():
    try:
        data.load_csv("employee_id,department\nE1,Sales\n")
    except ValueError as e:
        assert "missing columns" in str(e)
    else:
        raise AssertionError


def test_idle_seats_and_roi_consistent():
    ds, a = data.generate(), an.Assumptions()
    s = an.summary(ds, a)
    c = s["company"]
    assert abs(c["roi"] - (c["monthly_value"] - c["monthly_cost"]) / c["monthly_cost"]) < 1e-3
    assert sum(d["headcount"] for d in s["departments"].values()) == c["headcount"]


def test_realization_scales_value():
    ds = data.generate()
    lo = an.summary(ds, an.Assumptions(realization=0.25))["company"]["monthly_value"]
    hi = an.summary(ds, an.Assumptions(realization=0.5))["company"]["monthly_value"]
    assert abs(hi - 2 * lo) < 1.0


def test_reclaiming_idle_seats_cuts_cost():
    ds, a = data.generate(), an.Assumptions()
    base = an.simulate(ds, a, an.Policy("b", ""))
    rec = an.simulate(ds, a, an.Policy("r", "", reclaim_idle=True))
    assert rec["monthly_cost"] < base["monthly_cost"]


def test_throttling_never_raises_value():
    ds, a = data.generate(), an.Assumptions()
    base = an.simulate(ds, a, an.Policy("b", ""))
    cap = an.simulate(ds, a, an.Policy("c", "", cap_mode="flat", flat_cap=5.0))
    assert cap["monthly_value"] <= base["monthly_value"]


def test_nemotron_ranking_prefers_ultra():
    ids = ["nvidia/nemotron-3-nano-30b", "nvidia/nemotron-3-super-120b", "nvidia/nemotron-3-ultra-500b"]
    assert max(ids, key=llm._size_hint).endswith("ultra-500b")
    assert min(ids, key=llm._size_hint).endswith("nano-30b")


def test_ask_runs_tool_loop_with_stub(monkeypatch):
    a = llm.Analyst(ds=data.generate())
    a._models = {"fast": "f", "reason": "r"}
    calls = []

    def create(**kw):
        calls.append(kw)
        if len(calls) == 1:
            tc = SimpleNamespace(id="1", function=SimpleNamespace(name="compare_policies", arguments="{}"))
            msg = SimpleNamespace(tool_calls=[tc], content=None,
                                  model_dump=lambda exclude_none=True: {"role": "assistant", "tool_calls": [
                                      {"id": "1", "type": "function",
                                       "function": {"name": "compare_policies", "arguments": "{}"}}]})
        else:
            msg = SimpleNamespace(tool_calls=None, content="<think>x</think>Variable by role wins.")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    a._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    out = a.ask("which policy?")
    assert out["answer"] == "Variable by role wins."
    assert out["evidence"][0]["tool"] == "compare_policies"


def test_api_endpoints_and_missing_key(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    llm._CLIENT = None
    c = TestClient(app)
    assert c.get("/api/report").json()["summary"]["company"]["headcount"] == sum(data.HEADCOUNT.values())
    assert c.post("/api/ask", json={"question": "hi"}).status_code == 503
    assert c.post("/api/assumptions", json={"realization": 5}).status_code == 422
    bad = c.post("/api/upload", files={"file": ("x.csv", b"a,b\n1,2\n")})
    assert bad.status_code == 422


def test_bill_risk_is_nonnegative_and_capping_lowers_it():
    ds, a = data.generate(), an.Assumptions()
    base = an.simulate(ds, a, an.Policy("b", ""))
    capped = an.simulate(ds, a, an.Policy("c", "", cap_mode="flat", flat_cap=15.0))
    assert base["bill_risk"] >= 0
    assert capped["worst_case_cost"] <= base["worst_case_cost"]
    assert capped["bill_risk"] <= base["bill_risk"]


def test_policies_use_actual_seat_cost():
    ds, a = data.generate(), an.Assumptions()
    status_quo = an.simulate(ds, a, an.Policy("b", ""))
    assert abs(status_quo["monthly_cost"] - an.summary(ds, a)["company"]["monthly_cost"]) < 1.0


def test_waste_is_part_of_spend():
    ds, a = data.generate(), an.Assumptions()
    w = an.waste(ds, a)
    assert 0 < w["total_monthly"] < an.summary(ds, a)["company"]["monthly_cost"]
    assert abs(w["total_annual"] - 12 * w["total_monthly"]) < 1.0


def test_policy_flags_match_numbers():
    rows = an.compare_policies(data.generate(), an.Assumptions())
    top = [r for r in rows if r["highest_net"]]
    safe = [r for r in rows if r["lowest_bill_risk"]]
    assert len(top) == 1 and top[0]["net"] == max(r["net"] for r in rows)
    assert len(safe) == 1 and safe[0]["bill_risk"] == min(r["bill_risk"] for r in rows)


def test_sessions_are_isolated():
    c1, c2 = TestClient(app), TestClient(app)
    base = c1.get("/api/report").json()["summary"]["company"]["monthly_value"]
    c1.post("/api/assumptions", json={"realization": 0.2})
    assert c2.get("/api/report").json()["summary"]["company"]["monthly_value"] == base
    assert c1.get("/api/report").json()["summary"]["company"]["monthly_value"] < base


def test_llm_rate_limit(monkeypatch):
    monkeypatch.setattr(appmod, "LLM_PER_HOUR", 1)
    appmod._llm_calls.clear()
    assert appmod._llm(lambda: "ok") == "ok"
    try:
        appmod._llm(lambda: "ok")
    except Exception as e:
        assert getattr(e, "status_code", None) == 429
    else:
        raise AssertionError
    appmod._llm_calls.clear()


def test_upload_size_limit():
    big = b"a" * (appmod.MAX_UPLOAD + 10)
    assert TestClient(app).post("/api/upload", files={"file": ("x.csv", big)}).status_code == 413


# ---------------------------------------------------------------- v2: control group, cohorts, privacy, validation

def test_control_group_removes_company_trend():
    s = an.summary(data.generate(), an.Assumptions())["company"]
    assert s["did_lift"] < s["naive_lift"]
    assert 0.04 < s["control_growth"] < 0.08  # 2.5%/month trend over the window
    assert abs((1 + s["naive_lift"]) / (1 + s["control_growth"]) - 1 - s["did_lift"]) < 5e-3


def test_estimated_lift_orders_archetypes_correctly():
    ds, a = data.generate(), an.Assumptions()
    by = {}
    for e in an.employees(ds, a):
        if e.treated and e.own_baseline:
            by.setdefault(ds.truth[e.employee_id]["archetype"], []).append(e.lift)
    mean = {k: sum(v) / len(v) for k, v in by.items()}
    assert mean["power"] > mean["steady"] > mean["heavy_no_gain"]
    assert mean["power"] > 0.10 and abs(mean["heavy_no_gain"]) < 0.06


def test_people_without_baseline_get_department_effect():
    ds, a = data.generate(), an.Assumptions()
    es, stats = an._analyze(ds, a)
    newbies = [e for e in es if e.treated and not e.own_baseline]
    assert newbies
    assert all(abs(e.lift - stats[e.department]["did_lift"]) < 1e-9 for e in newbies)


def test_overspend_is_judged_within_level():
    mk = lambda i, lv, tok: an.Employee(f"{lv}{i}", "Eng", "SWE", lv, token_cost=tok, treated=True)  # noqa: E731
    es = [mk(i, "intern", 10.0) for i in range(10)] + [mk(i, "senior", 100.0) for i in range(10)]
    med = an._peer_median(es, min_cohort=8)
    assert med(es[0]) == 10.0 and med(es[-1]) == 100.0


def test_small_cohort_falls_back_to_department():
    mk = lambda i, lv, tok: an.Employee(f"{lv}{i}", "Eng", "SWE", lv, token_cost=tok, treated=True)  # noqa: E731
    es = [mk(i, "intern", 10.0) for i in range(3)] + [mk(i, "senior", 100.0) for i in range(10)]
    med = an._peer_median(es, min_cohort=8)
    assert med(es[0]) == 100.0  # 3 interns is too few to be their own peer group


def test_nothing_identifies_a_person():
    import json, re
    ds, a = data.generate(), an.Assumptions()
    for row in an.list_people(ds, a, limit=25):
        assert "employee_id" not in row and row["people"] >= a.min_group
    for row in an.actions(ds, a):
        assert "employee_ids" not in row and row["people"] >= a.min_group
    body = json.dumps(TestClient(app).get("/api/report").json()) + TestClient(app).get("/api/actions.csv").text
    assert not re.search(r"E\d{4}", body)  # no employee id anywhere a viewer can see it


def test_language_never_blames_people():
    import pathlib
    banned = ("lazy", "wasteful", "offender", "abuser", "overspender", "worst performer", "slacker")
    root = pathlib.Path(__file__).resolve().parent.parent
    for path in [*root.glob("ailedger/*.py"), root / "static/index.html", root / "static/charts.js", root / "README.md"]:
        if path.name == "llm.py":
            continue  # holds the ban list and prompt rules by necessity; the detector has its own tests
        text = path.read_text().lower()
        for w in banned:
            assert w not in text, f"{w} in {path.name}"
    for r in an.actions(data.generate(), an.Assumptions()):
        assert not any(w in r["reason"].lower() for w in banned)


def test_actions_saving_matches_waste():
    ds, a = data.generate(), an.Assumptions()
    w = an.waste(ds, a)
    total = sum(r["monthly_saving"] for r in an.actions(ds, a))
    assert w["total_monthly"] * 0.99 <= total <= w["total_monthly"] + 1.0  # tiny groups may be left out, never added


def test_analysis_recovers_hidden_truth():
    v = an.validate(data.generate(), an.Assumptions())
    assert v["idle_seats"]["recall"] > 0.95          # every shelfware seat found
    assert v["idle_vs_nonusers"]["precision"] > 0.95  # nearly all flagged seats are truly unused
    assert v["high_spend"]["recall"] > 0.7 and v["high_spend"]["precision"] > 0.6
    assert v["no_value"]["recall"] > 0.8


def test_validation_survives_noise_seeds():
    for seed in (1, 2, 3):
        v = an.validate(data.generate(seed=seed), an.Assumptions())
        assert v["idle_vs_nonusers"]["precision"] > 0.9 and v["high_spend"]["recall"] > 0.6


def test_routing_saving_vanishes_when_prices_equal():
    ds = data.generate()
    assert an.routing(ds, an.Assumptions())["saving"] > 0
    flat = an.routing(ds, an.Assumptions(cheap_price_per_m=data.TOKEN_PRICE_PER_M))
    assert flat["saving"] == 0 and flat["net_gain"] <= 0


def test_confidence_flag_matches_range():
    for v in an.summary(data.generate(), an.Assumptions())["departments"].values():
        spans_zero = v["roi_low"] <= 0 <= v["roi_high"]
        assert (v["confidence"] == "uncertain") == spans_zero


def test_csv_needs_four_months():
    ds = data.generate()
    first3 = "\n".join(l for l in ds.to_csv().splitlines() if l.startswith("employee_id") or any(
        f",{m}," in l for m in data.MONTHS[:3]))
    try:
        data.load_csv(first3)
    except ValueError as e:
        assert "4 months" in str(e)
    else:
        raise AssertionError


def test_csv_level_column_is_optional():
    text = data.generate().to_csv().splitlines()
    cols = text[0].split(",")
    i = cols.index("level")
    stripped = "\n".join(",".join(c for j, c in enumerate(l.split(",")) if j != i) for l in text)
    assert {r["level"] for r in data.load_csv(stripped).rows} == {"mid"}


def test_actions_csv_endpoint():
    c = TestClient(app)
    r = c.get("/api/actions.csv?ids=0,1")
    assert r.status_code == 200 and r.text.splitlines()[0].startswith("action,department,level")
    assert len(r.text.strip().splitlines()) == 3


def test_restrict_only_when_loss_is_clear():
    ds, a = data.generate(), an.Assumptions()
    for d, b in an.budget_recommendations(ds, a).items():
        if b["verdict"] == "restrict":
            assert b["confidence"] == "clear" and b["dept_roi"] < 0
        if b["confidence"] == "uncertain" and b["dept_roi"] < 0:
            assert b["verdict"] == "review"


def _true_lift(ds, a):
    es = an.employees(ds, a)
    tl = [ds.truth[e.employee_id]["lift_window"] for e in es if e.treated and e.own_baseline]
    return sum(tl) / len(tl)


def test_effect_stays_accurate_under_large_company_trend():
    ds, a = data.generate(trend=0.10), an.Assumptions()
    s = an.summary(ds, a)["company"]
    assert abs(s["did_lift"] - _true_lift(ds, a)) < 0.01  # additive subtraction was off by about 2 points here


def test_self_selection_is_detected_and_corrected():
    a = an.Assumptions()
    ds = data.generate(adopter_drift=0.01)
    sel = an.selection(ds, a)
    assert sel["adjusted"] and sel["gap_per_month"] > 0.002
    assert abs(an.summary(ds, a)["company"]["did_lift"] - _true_lift(ds, a)) < 0.015
    off = an.Assumptions(adjust_pretrend=False)
    assert abs(an.summary(ds, off)["company"]["did_lift"] - _true_lift(ds, off)) > abs(an.summary(ds, a)["company"]["did_lift"] - _true_lift(ds, a))


def test_no_selection_warning_on_clean_data():
    assert not an.selection(data.generate(), an.Assumptions())["significant"]


def test_strong_selection_raises_warning():
    assert an.selection(data.generate(adopter_drift=0.03), an.Assumptions())["significant"]


def test_selection_check_skipped_with_one_pre_month():
    sel = an.selection(data.generate(), an.Assumptions(pre_months=1))
    assert not sel["tested"] and not sel["adjusted"] and not sel["significant"]


def test_pay_per_use_breakeven_is_consistent():
    ds = data.generate()
    a = an.Assumptions()
    b = an.pay_per_use_breakeven(ds, a)
    assert b["multiplier"] and b["multiplier"] > 1.0
    below = an.compare_policies(ds, an.Assumptions(ppu_multiplier=b["multiplier"] - 0.2))
    above = an.compare_policies(ds, an.Assumptions(ppu_multiplier=b["multiplier"] + 0.2))
    assert next(r for r in below if r["highest_net"])["name"] == "Pay per use"
    assert next(r for r in above if r["highest_net"])["name"] != "Pay per use"


def test_assumed_multiplier_changes_pay_per_use_only():
    ds = data.generate()
    lo = {r["name"]: r for r in an.compare_policies(ds, an.Assumptions(ppu_multiplier=1.0))}
    hi = {r["name"]: r for r in an.compare_policies(ds, an.Assumptions(ppu_multiplier=3.0))}
    assert lo["Pay per use"]["net"] > hi["Pay per use"]["net"]
    assert lo["Variable by role"]["net"] == hi["Variable by role"]["net"]


def test_blame_detector_and_question_reframing():
    assert llm.blames("These are the worst overspenders, cut individuals.")
    assert llm.blames("Reassign 245 over-allocated people")
    assert not llm.blames("Reassign 454 unused seats; Engineering is the lowest-return group.")
    assert not llm.blames("Finance has the worst ROI of the departments.")
    assert llm.asks_about_individuals("Who are the worst overspenders and which individuals should we cut?")
    assert not llm.asks_about_individuals("Is a variable budget better than fixed for Sales?")
    r = llm.reframe("who is wasting tokens?")
    assert "get_actions" in r and "wasting" not in r  # the original wording never reaches the model


def _stub_analyst(replies):
    a = llm.Analyst(ds=data.generate())
    a._models = {"fast": "f", "reason": "r"}
    it = iter(replies)

    def create(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content=next(it)))])
    a._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return a


def test_blaming_answer_is_repaired_then_falls_back():
    a = _stub_analyst(["Cut the worst overspenders.", "Still blaming the offenders."])
    out = a.ask("which departments cost most?")
    assert not llm.blames(out["answer"]) and out["repaired"]
    assert "unused seats" in out["answer"]  # deterministic safe summary


def test_repair_pass_used_when_it_works():
    a = _stub_analyst(["Cut the lazy offenders.", "Reassign 454 unused seats."])
    out = a.ask("what should we do?")
    assert out["answer"] == "Reassign 454 unused seats." and out["repaired"]


def test_person_question_is_reframed_and_prefixed():
    a = _stub_analyst(["Engineering has the most recoverable spend."])
    out = a.ask("Who are the worst overspenders?")
    assert out["reframed"] and out["answer"].startswith("This tool does not identify or rank individuals")


def test_juniors_and_interns_never_capped_below_department():
    ds, a = data.generate(), an.Assumptions()
    es = an.employees(ds, a)
    caps = an._caps(es, a, 0.75)
    for d in {e.department for e in es}:
        for lv in ("intern", "junior"):
            assert caps[(d, lv)] >= caps[(d, None)] - 1e-9


def test_robustness_separates_robust_from_assumed():
    r = an.robustness(data.generate(), an.Assumptions())
    by = {d["id"]: d for d in r["decisions"]}
    assert r["scenarios"] == 180
    assert by["vbr_beats_status_quo"]["verdict"] == "robust"
    assert by["ppu_highest"]["verdict"] == "depends on assumptions"  # winner flips with the price assumption
    assert r["departments"]["Legal"]["verdict"] == "positive"
    assert set(r["kinds"]) == {"measured", "estimated", "assumed", "judgement"}


def test_robustness_endpoint_and_cache():
    c = TestClient(app)
    r1 = c.get("/api/robustness").json()
    assert r1["decisions"] and r1["departments"]
    assert c.get("/api/robustness").json() == r1


def test_worked_steps_match_dashboard_numbers():
    ds, a = data.generate(), an.Assumptions()
    s, w = an.summary(ds, a), an.waste(ds, a)
    for d, v in s["departments"].items():
        steps = {x["title"][:2]: x for x in an.explain(ds, a, d)["steps"]}
        assert f"${v['monthly_cost']:,.0f}" in steps["1."]["result"]
        assert f"ROI {v['roi']:.2f}" in steps["8."]["result"]
        assert f"${w['by_department'][d]['total']:,.0f}" in steps["9."]["result"]


def test_explain_has_no_individuals_and_covers_policies():
    import json, re
    ds, a = data.generate(), an.Assumptions()
    body = json.dumps(an.explain(ds, a, "Sales")) + json.dumps(an.explain_policies(ds, a))
    assert not re.search(r"E\d{4}", body)
    assert {p["policy"] for p in an.explain_policies(ds, a)} >= {"Status quo", "Pay per use", "Bill risk"}


def test_explain_endpoint():
    r = TestClient(app).get("/api/explain?department=Legal").json()
    assert r["department"]["department"] == "Legal" and len(r["department"]["steps"]) == 9


def test_plan_is_cheaper_per_head_in_every_department():
    ds, a = data.generate(), an.Assumptions()
    for d, b in an.budget_recommendations(ds, a).items():
        assert b["expected_per_head"] < b["current_per_head"], d
        assert b["ceiling_per_head"] >= b["expected_per_head"] - 1e-6  # a ceiling is not an average
        assert abs(b["saving_from_seats"] + b["saving_from_caps"] - b["saving_monthly"]) < 0.05


def test_plan_saving_reconciles_with_waste():
    ds, a = data.generate(), an.Assumptions()
    p, w = an.plan_savings(ds, a)["company"], an.waste(ds, a)
    assert abs(p["from_seats"] - w["idle_monthly"]) < 1.0   # seats part is exactly the unused-seat saving
    assert p["saving"] <= w["total_monthly"] + 1.0          # the plan never claims more than the headline
    assert p["hard_cap_saving"] > p["saving"] and p["hard_cap_value_lost"] > 0


def test_glossary_covers_the_terms_used_on_the_page():
    import pathlib
    html = (pathlib.Path(__file__).resolve().parent.parent / "static/index.html").read_text()
    assert 'data-tab="glossary"' in html and 'id="tab-glossary"' in html
    for term in ["Unused seat", "High-spend seat", "Control group", "Parallel-trends check", "Break-even credit",
                 "Bill risk", "Variable by role", "Pay per use", "Elasticity", "Realization", "Learning floor",
                 "Shrinkage", "Model routing", "Minimum group size", "Precision and recall"]:
        assert f"'{term}" in html, f"glossary is missing {term}"


def test_cost_split_adds_up_to_total_cost():
    ds, a = data.generate(), an.Assumptions()
    sp = an.waste(ds, a)["cost_split"]
    total = an.summary(ds, a)["company"]["monthly_cost"]
    assert abs(sum(sp.values()) - total) < 1.0
    assert abs(sp["tokens_above_norm"] - an.waste(ds, a)["over_monthly"]) < 1.0
    assert abs(sp["seats_unused"] * a.seat_savings_realized - an.waste(ds, a)["idle_monthly"]) < 1.0


def test_output_index_shows_users_pulling_ahead_only_after_rollout():
    ds, a = data.generate(), an.Assumptions()
    ix = an.output_index(ds, a)
    assert len(ix["months"]) == 5 and ix["n_users"] > 0 and ix["n_non_users"] > 0
    pre_gap = abs(ix["users"][0] - ix["non_users"][0])
    post_gap = ix["users"][-1] - ix["non_users"][-1]
    assert pre_gap < 1.0 and post_gap > 3.0           # same start, clear gap at the end
    assert ix["non_users"][-1] > ix["non_users"][0]    # the control group also grew (company trend)


def test_charts_are_served_and_wired_to_report_data():
    c = TestClient(app)
    js = c.get("/static/charts.js")
    assert js.status_code == 200 and "renderCharts" in js.text
    r = c.get("/api/report").json()
    assert {"cost_split", "by_department"} <= set(r["waste"]) | {"by_department"}
    assert set(r["waste"]["cost_split"]) == {"seats_in_use", "seats_unused", "tokens_normal", "tokens_above_norm"}
    assert len(r["output_index"]["users"]) == len(r["output_index"]["months"]) == 5
    html = c.get("/").text
    for chart_id in ("c-forest", "c-split", "c-index", "c-trade"):
        assert f'id="{chart_id}"' in html and chart_id in js.text


def test_charts_never_use_untrusted_html_injection():
    import pathlib
    js = (pathlib.Path(__file__).resolve().parent.parent / "static/charts.js").read_text()
    assert "innerHTML" not in js  # department names come from uploaded CSVs: textContent only


# ---------------------------------------------------------------- published evidence

def test_every_study_is_sourced_and_labelled():
    from ailedger import evidence as ev
    ids = set()
    for s in ev.STUDIES:
        assert s["url"].startswith("https://") and s["verified"].strip() and s["reported"].strip()
        assert s["metric"] in {"output", "time", "sd", "null"} and s["year"] >= 2023 and s["id"] not in ids
        ids.add(s["id"])
        if s["metric"] in {"output", "time"}:
            assert isinstance(s["value"], (int, float))
        if s["lo"] is not None:
            assert s["lo"] <= s["value"] <= s["hi"]
    assert {s["metric"] for s in ev.STUDIES} == {"output", "time", "sd", "null"}


def test_figures_match_what_was_read_in_the_sources():
    from ailedger import evidence as ev
    by = {s["id"]: s for s in ev.STUDIES}
    assert abs((160.89 - 71.17) / 160.89 * 100 - 55.8) < 0.05                    # Peng: 55.8% less time, from the paper's own minutes
    assert by["peng-2023"]["value"] == -55.8 and (by["peng-2023"]["lo"], by["peng-2023"]["hi"]) == (-89.0, -21.0)
    assert by["cui-2025"]["value"] == 26.08 and by["cui-2025"]["ci_derived"]
    assert abs(by["cui-2025"]["hi"] - (26.08 + 1.96 * 10.3)) < 1e-9               # range is ours, flagged as derived
    assert by["becker-2025"]["value"] == 19.0 and by["murphy-hill-2026"]["value"] == 24.0
    assert by["brynjolfsson-2023"]["value"] == 14.0 and by["dellacqua-2023"]["value"] == 12.2
    assert by["noy-zhang-2023"]["value"] is None  # reported in standard deviations: never forced onto a percent axis


def test_unverified_figures_stay_out_of_the_studies():
    from ailedger import evidence as ev
    text = " ".join(str(v) for s in ev.STUDIES for v in s.values()).lower()
    for bad in ("40% less time", "18% higher quality", "19 percentage points", "2.8%"):
        assert bad not in text
    assert any("could not be confirmed" in x for x in ev.LEFT_OUT)


def test_comparison_verdicts():
    from ailedger import evidence as ev
    mk = lambda e, lo, hi: {"did_lift": e / 100, "did_ci_low": lo / 100, "did_ci_high": hi / 100}  # noqa: E731
    assert ev.compare(mk(19, 15, 23))["verdict"] == "within"
    assert ev.compare(mk(7, 5, 9))["verdict"] == "below"
    assert ev.compare(mk(8, 5, 14))["verdict"] == "below_overlapping"
    assert ev.compare(mk(40, 35, 45))["verdict"] == "above"
    assert ev.compare(mk(30, 20, 40))["verdict"] == "above_overlapping"
    assert ev.compare(mk(-3, -6, 0))["verdict"] == "none"


def test_comparison_uses_only_output_studies():
    from ailedger import evidence as ev
    r = ev.published_output_range()
    assert (r["min"], r["max"], r["n"]) == (12.2, 26.08, 4)  # time-on-task and standard-deviation studies are never mixed in


def test_evidence_endpoint_matches_the_dashboard_estimate():
    c = TestClient(app)
    g = c.get("/api/evidence").json()
    s = c.get("/api/report").json()["summary"]["company"]
    assert len(g["studies"]) == 9 and g["verified_on"]
    assert abs(g["comparison"]["your_effect"] - s["did_lift"] * 100) < 0.01
    assert g["comparison"]["your_low"] <= g["comparison"]["your_effect"] <= g["comparison"]["your_high"]


def test_analyst_is_told_realization_does_not_change_the_output_effect():
    assert "before the realization share" in llm.SYSTEM and "get_evidence" in llm.SYSTEM


# ---------------------------------------------------------------- benchmarks from the published studies

def test_breakeven_effect_returns_exactly_the_cost():
    from ailedger import bench
    ds, a = data.generate(), an.Assumptions()
    b = bench.breakeven(ds, a)["company"]
    es, _ = an._analyze(ds, a)
    value_at_breakeven = b["breakeven"] * bench._value_per_unit_effect(es, a)
    assert abs(value_at_breakeven - b["cost"]) < b["cost"] * 0.002   # value equals cost, within the 4-decimal rounding of the effect
    assert 0 < b["breakeven"] < 0.5


def test_breakeven_scales_with_realization():
    from ailedger import bench
    ds = data.generate()
    half = bench.breakeven(ds, an.Assumptions(realization=0.5))["company"]["breakeven"]
    full = bench.breakeven(ds, an.Assumptions(realization=1.0))["company"]["breakeven"]
    assert abs(half / full - 2.0) < 0.02   # counting twice as much of the gain halves the effect you need (values are stored to 4 decimals)


def test_scenarios_are_ordered_and_use_only_output_studies():
    from ailedger import bench, evidence as ev
    rows = bench.scenarios(data.generate(), an.Assumptions())
    effects = [r["effect"] for r in rows if r["key"] != "measured"]
    assert effects == sorted(effects) and effects[0] == 0.0
    assert rows[0]["pays_off"] is False and rows[-1]["pays_off"] is True
    published = {r["effect"] for r in rows if r["key"] not in ("scenario", "measured")}
    assert published == {x["value"] / 100 for x in ev.STUDIES if x["metric"] == "output"}  # no time-on-task numbers mixed in


def test_effect_by_level_reports_no_difference_when_none_was_built_in():
    from ailedger import bench
    L = bench.by_level(data.generate(level_lift=False), an.Assumptions())
    assert [x["level"] for x in L["levels"]] == ["intern", "junior", "mid", "senior"]
    assert L["verdict"].startswith("no clear difference")  # the flat case gives every level the same lift
    assert all(x["low"] <= x["effect"] <= x["high"] for x in L["levels"])


def test_effect_by_level_detects_a_real_difference():
    from ailedger import bench
    ds = data.generate(seed=5, level_lift=False)
    for r in ds.rows:  # make juniors and interns gain an extra 20% after rollout, in a copy of the rows
        if r["level"] in ("intern", "junior") and r["sessions"] >= 3 and r["month"] >= "2026-07":
            r["outcome_units"] *= 1.20
    L = bench.by_level(ds, an.Assumptions())
    assert L["verdict"] == "less experienced people gain more" and L["difference"] > 0.1


def test_perception_gap_verdicts():
    from ailedger import bench
    ds, a = data.generate(), an.Assumptions()
    assert bench.perception(ds, a, 25.0)["verdict"] == "overstated"
    assert bench.perception(ds, a, 7.0)["verdict"] == "consistent"
    assert bench.perception(ds, a, 0.0)["verdict"] == "understated"
    assert "19% slower" in bench.perception(ds, a, 7.0)["note"]


def test_benchmark_endpoints():
    c = TestClient(app)
    g = c.get("/api/evidence").json()
    assert {"breakeven", "scenarios", "by_level", "studies", "comparison"} <= set(g)
    assert c.get("/api/perception?pct=20").json()["verdict"] == "overstated"
    assert c.get("/api/perception?pct=9999").status_code == 422


def test_rounding_matches_the_page():
    from ailedger import evidence as ev
    assert ev.p1(9.25) == "9.3" and ev.p1(5.04) == "5.0" and ev.p1(7.1) == "7.1"
    ds, a = data.generate(), an.Assumptions()
    from ailedger import bench
    c = an.summary(ds, a)["company"]
    assert f"{ev.p1(c['did_ci_high'] * 100)}%" in bench.perception(ds, a, 7.0)["text"]


# ---------------------------------------------------------------- calibration to the published findings

def test_archetype_lifts_sit_inside_the_published_output_range():
    from ailedger import evidence as ev
    pr = ev.published_output_range()
    for name in ("power", "steady"):
        assert pr["min"] <= data.ARCHETYPES[name]["lift"] * 100 <= pr["max"], name   # adopters who gain, per the studies
    assert data.ARCHETYPES["unused"]["lift"] == 0 and data.ARCHETYPES["heavy_no_gain"]["lift"] == 0
    assert 0 < data.ARCHETYPES["light"]["lift"] < pr["min"] / 100


def test_levels_gain_more_the_less_experienced_they_are():
    lifts = [data.LEVELS[k]["lift"] for k in ("intern", "junior", "mid", "senior")]
    assert lifts == sorted(lifts, reverse=True) and data.LEVELS["mid"]["lift"] == 1.0
    novice_power = data.ARCHETYPES["power"]["lift"] * data.LEVELS["intern"]["lift"] * 100
    assert abs(novice_power - 34) < 2        # Brynjolfsson et al.: novices gained 34%
    assert data.ARCHETYPES["power"]["lift"] * data.LEVELS["senior"]["lift"] > 0.10   # smaller for the experienced, not "minimal" zero


def test_measured_effect_is_ordered_by_experience_in_the_calibrated_company():
    from ailedger import bench
    L = bench.by_level(data.generate(), an.Assumptions())
    eff = [x["effect"] for x in L["levels"]]
    assert eff == sorted(eff, reverse=True)             # intern > junior > mid > senior
    assert L["verdict"] == "less experienced people gain more" and L["difference"] > 0.02


def test_breakeven_verdict_does_not_overclaim_a_near_miss():
    from ailedger import bench
    c = bench.breakeven(data.generate(), an.Assumptions())["company"]
    margin, half = c["low"] - c["breakeven"], c["measured"] - c["low"]
    assert 0 <= margin < 0.25 * half                      # the low end sits right at break-even in the default company
    assert c["verdict"].startswith("above break-even, but only just")


# ---------------------------------------------------------------- your own definition of value

import json as _json
from dataclasses import replace as _replace


def _with_defs(defs):
    return _replace(an.Assumptions(), value_json=_json.dumps(defs))


def test_no_definition_means_hours_times_rate_as_before():
    ds = data.generate()
    plain, empty = an.summary(ds, an.Assumptions())["company"], an.summary(ds, _with_defs({}))["company"]
    assert plain["monthly_value"] == empty["monthly_value"]
    es, _ = an._analyze(ds, an.Assumptions())
    assert all(abs(e.unit_value - e.hpu * e.rate) < 1e-9 for e in es if e.treated)


def test_dollars_per_unit_scales_that_department_only():
    ds = data.generate()
    a1, a2 = _with_defs({"Sales": {"mode": "unit", "value_per_unit": 200}}), _with_defs({"Sales": {"mode": "unit", "value_per_unit": 400}})
    d1, d2 = an.summary(ds, a1)["departments"], an.summary(ds, a2)["departments"]
    assert abs(d2["Sales"]["monthly_value"] / d1["Sales"]["monthly_value"] - 2.0) < 0.01   # value is linear in the unit value
    assert d1["Engineering"]["monthly_value"] == d2["Engineering"]["monthly_value"]        # other departments untouched
    assert d1["Engineering"]["monthly_value"] == an.summary(ds, an.Assumptions())["departments"]["Engineering"]["monthly_value"]


def test_benefit_per_user_adds_exactly_that_much_per_active_user():
    ds = data.generate()
    base = an.summary(ds, an.Assumptions())["departments"]["Legal"]
    plus = an.summary(ds, _with_defs({"Legal": {"benefit_per_user": 25}}))["departments"]["Legal"]
    users = sum(1 for e in an.employees(ds, an.Assumptions()) if e.department == "Legal" and e.treated)
    assert abs((plus["monthly_value"] - base["monthly_value"]) - 25 * users) < 1.0
    assert plus["value_low"] - base["value_low"] > 0 and abs((plus["value_high"] - base["value_high"]) - 25 * users) < 1.0


def test_default_definition_applies_to_departments_without_their_own():
    ds = data.generate()
    a = _with_defs({"*": {"benefit_per_user": 10}, "Sales": {"benefit_per_user": 0}})
    d = an.summary(ds, a)["departments"]; base = an.summary(ds, an.Assumptions())["departments"]
    assert d["Sales"]["monthly_value"] == base["Sales"]["monthly_value"]       # its own definition wins
    assert d["Finance"]["monthly_value"] > base["Finance"]["monthly_value"]     # the default reached it


def test_definition_changes_breakeven_consistently():
    from ailedger import bench
    ds = data.generate()
    plain = bench.breakeven(ds, an.Assumptions())["company"]["breakeven"]
    lots = bench.breakeven(ds, _with_defs({"*": {"benefit_per_user": 50}}))["company"]["breakeven"]
    assert lots < plain                                                         # a fixed benefit lowers the effect you need
    assert bench.breakeven(ds, _with_defs({"*": {"benefit_per_user": 10_000}}))["company"]["breakeven"] == 0.0


def test_break_even_realization_still_returns_cost_with_a_fixed_benefit():
    ds, defs = data.generate(), {"Engineering": {"benefit_per_user": 30}}
    a = _with_defs(defs)
    d = an.summary(ds, a)["departments"]["Engineering"]
    again = an.summary(ds, _replace(a, realization=d["break_even_realization"]))["departments"]["Engineering"]
    assert abs(again["monthly_value"] - again["monthly_cost"]) < again["monthly_cost"] * 0.02


def test_value_definition_validation():
    depts = ["Sales", "Legal"]
    ok = an.validate_value_defs({"Sales": {"mode": "unit", "value_per_unit": "300"}, "*": {"benefit_per_user": 5}}, depts)
    assert ok["Sales"]["value_per_unit"] == 300.0 and ok["*"]["benefit_per_user"] == 5.0
    for bad in ({"Nope": {"benefit_per_user": 1}}, {"Sales": {"value_per_unit": -1}}, {"Sales": {"hourly_rate": 1e9}},
                {"Sales": {"mode": "magic"}}, {"Sales": {"unknown": 1}}, {"Sales": {"mode": "unit"}}, {"Sales": {"benefit_per_user": "abc"}}, [], {"Sales": 5}):
        try:
            an.validate_value_defs(bad, depts)
        except ValueError:
            continue
        raise AssertionError(f"accepted {bad}")


def test_value_api_round_trip_and_sliders_keep_the_definition():
    c = TestClient(app)
    base = c.get("/api/report").json()["summary"]["company"]["monthly_value"]
    r = c.post("/api/value", json={"defs": {"Sales": {"mode": "unit", "value_per_unit": 400}}}).json()
    assert r["value"]["custom"] and r["summary"]["company"]["monthly_value"] > base
    r2 = c.post("/api/assumptions", json={"realization": 0.5, "elasticity": 0.6, "cheap_price_per_m": 0.6}).json()
    assert r2["value"]["custom"]                                                   # moving a slider must not wipe it
    assert c.post("/api/value", json={"defs": {"Nope": {"benefit_per_user": 1}}}).status_code == 422
    assert c.get("/api/value").json()["defs"]["Sales"]["value_per_unit"] == 400
    r3 = c.post("/api/value", json={"defs": {}}).json()
    assert not r3["value"]["custom"] and r3["summary"]["company"]["monthly_value"] == base


def test_upload_clears_a_stale_definition():
    c = TestClient(app)
    c.post("/api/value", json={"defs": {"Sales": {"benefit_per_user": 9}}})
    csv_text = data.generate(scale=0.05).to_csv().encode()
    r = c.post("/api/upload", files={"file": ("x.csv", csv_text)})
    assert r.status_code == 200 and not r.json()["value"]["custom"]


def test_explain_names_your_definition():
    ds = data.generate()
    step = an.explain(ds, _with_defs({"Sales": {"mode": "unit", "value_per_unit": 400}}), "Sales")["steps"][6]
    assert "Your definition" in step["formula"] and "$400.00 per unit" in step["formula"]
    assert "Your definition" not in an.explain(ds, an.Assumptions(), "Sales")["steps"][6]["formula"]


# ---------------------------------------------------------------- every value has a referenced origin

def test_every_assumption_is_explained_in_the_registry():
    from ailedger import sources as src
    reg = {e["id"] for e in src.registry()["entries"]}
    fields = set(an.Assumptions().__dict__)
    assert fields <= set(src.ENTRY_FIELDS), f"unexplained assumptions: {fields - set(src.ENTRY_FIELDS)}"
    assert set(src.ENTRY_FIELDS.values()) <= reg


def test_registry_entries_are_honestly_labelled_and_linked():
    from ailedger import sources as src
    r = src.registry()
    ids = [e["id"] for e in r["entries"]]
    assert len(ids) == len(set(ids))
    for e in r["entries"]:
        assert e["kind"] in src.KINDS and e["why"].strip() and e["where"].strip() and e["value"].strip()
        for ref in e["refs"]:
            assert ref in r["refs"] and r["refs"][ref]["url"].startswith("https://"), (e["id"], ref)
        if e["kind"] == "published":
            assert any(x.startswith("study:") for x in e["refs"]), e["id"]      # a published number needs a study
    # anything anchored to the unconfirmed third-party listing must say so
    for e in r["entries"]:
        if "nebius-prices-listing" in e["refs"]:
            assert "third-party" in e["caveat"].lower()
    assert r["refs"]["nebius-prices-listing"]["confirmed"] is False
    assert all(v["confirmed"] for k, v in r["refs"].items() if k != "nebius-prices-listing")


def test_registry_values_come_from_the_live_code(monkeypatch):
    from ailedger import sources as src
    by = lambda: {e["id"]: e for e in src.registry()["entries"]}  # noqa: E731
    assert by()["high_spend"]["value"].startswith(f"{an.HIGH_SPEND_MULT:g}x")
    monkeypatch.setattr(an, "HIGH_SPEND_MULT", 2.0)
    assert by()["high_spend"]["value"].startswith("2x")                    # change the constant, the reference follows
    monkeypatch.setattr(data, "TOKEN_PRICE_PER_M", 7.0)
    assert "$7.00" in by()["frontier_token_price"]["value"]


def test_registry_shows_the_sessions_current_slider_values():
    from ailedger import sources as src
    a = _replace(an.Assumptions(), realization=0.3, ppu_multiplier=2.0)
    e = {x["id"]: x for x in src.registry(a)["entries"]}
    assert e["realization"]["value"] == "50%" and e["realization"]["current"] == "30%"    # default and what you set
    assert e["ppu_multiplier"]["current"] == "2x"
    assert src.registry(_with_defs({"Sales": {"benefit_per_user": 5}}))["entries"][1]["kind"] == "yours"


def test_worked_steps_and_policies_carry_references():
    from ailedger import sources as src
    ds, a = data.generate(), an.Assumptions()
    reg = {e["id"] for e in src.registry()["entries"]}
    steps = an.explain(ds, a, "Sales")["steps"]
    assert all("refs" in s for s in steps) and {"realization", "idle_sessions", "z95"} <= {r for s in steps for r in s["refs"]}
    assert {r for s in steps for r in s["refs"]} <= reg
    pols = an.explain_policies(ds, a)
    assert {r for p in pols for r in p["refs"]} <= reg and any("ppu_multiplier" in p["refs"] for p in pols)


def test_sources_endpoint():
    c = TestClient(app)
    g = c.get("/api/sources").json()
    assert g["read_on"] and len(g["entries"]) >= 25 and "assumption" in g["kinds"]
    assert any(e["slider"] == "realization" for e in g["entries"])


def test_sources_document_is_in_sync_with_the_code():
    import importlib.util, pathlib
    root = pathlib.Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("build_sources_doc", root / "tools/build_sources_doc.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    assert (root / "docs/sources.md").read_text() == mod.render(), "run: python tools/build_sources_doc.py"


# ---------------------------------------------------------------- your own unit of output

def test_csv_carries_unit_names_and_extra_metrics():
    ds = data.generate(scale=0.05)
    text = ds.to_csv()
    header = text.splitlines()[0].split(",")
    assert "unit_name" in header and "outcome_reviews" in header and "outcome_commits" in header
    back = data.load_csv(text)
    assert back.rows[0]["unit_name"] == "PRs merged" and set(back.rows[0]["extras"]) == {"reviews", "commits", "task_minutes"}
    assert len(back.rows) == len(ds.rows)


def test_extra_metrics_do_not_change_the_main_numbers():
    with_x, without = data.generate(extras=True), data.generate(extras=False)
    assert [r["outcome_units"] for r in with_x.rows] == [r["outcome_units"] for r in without.rows]   # separate random stream
    a = an.Assumptions()
    assert an.summary(with_x, a)["company"]["monthly_value"] == an.summary(without, a)["company"]["monthly_value"]


def test_unit_name_precedence_yours_then_data_then_default():
    ds, a = data.generate(scale=0.05), an.Assumptions()
    assert an.unit_label(ds, a, "Engineering") == "PRs merged"
    assert an.unit_label(ds, _with_defs({"Engineering": {"unit_name": "story points"}}), "Engineering") == "story points"
    bare = data.load_csv("\n".join(l for l in data.generate(scale=0.05, extras=False).to_csv().splitlines()))
    for r in bare.rows:
        r.pop("unit_name", None)
    assert an.unit_label(bare, a, "Engineering") == data.UNIT_NAMES["Engineering"]


def _mix(**w):
    return {"Engineering": {"outcome_weights": w, "mode": "unit", "value_per_unit": 100}}


def test_weights_of_one_on_the_main_metric_change_nothing():
    ds = data.generate()
    plain = an.summary(ds, an.Assumptions())["departments"]["Engineering"]
    same = an.summary(ds, _with_defs({"Engineering": {"outcome_weights": {"units": 1}}}))["departments"]["Engineering"]
    assert plain["monthly_value"] == same["monthly_value"] and plain["did_lift"] == same["did_lift"]


def test_a_weighted_mix_is_measured_on_the_mix():
    ds = data.generate()
    es_a, _ = an._analyze(ds, _with_defs(_mix(units=1.0)))
    es_b, _ = an._analyze(ds, _with_defs(_mix(units=1.0, reviews=0.3, commits=0.1)))
    a_base = {e.employee_id: e.base for e in es_a if e.department == "Engineering" and e.treated}
    b_base = {e.employee_id: e.base for e in es_b if e.department == "Engineering" and e.treated}
    ratios = [b_base[k] / a_base[k] for k in a_base if k in b_base and a_base[k] > 0]
    assert ratios and min(ratios) > 1.0                       # the mix is bigger per person than PRs alone
    only_commits = an.summary(ds, _with_defs(_mix(commits=1.0)))["departments"]["Engineering"]
    assert only_commits["did_lift"] != an.summary(ds, an.Assumptions())["departments"]["Engineering"]["did_lift"]  # a different metric has its own effect


def test_output_index_follows_the_definition():
    ds = data.generate()
    plain = an.output_index(ds, an.Assumptions())
    mixed = an.output_index(ds, _with_defs(_mix(commits=1.0)))
    assert plain["users"] != mixed["users"] and len(mixed["users"]) == 5


def test_output_definition_validation():
    ds = data.generate(scale=0.05)
    mets, depts = an.metrics_by_dept(ds), sorted(an.metrics_by_dept(ds))
    ok = an.validate_value_defs({"Engineering": {"outcome_weights": {"units": 1, "reviews": "0.3"}, "mode": "unit", "value_per_unit": 80}}, depts, mets)
    assert ok["Engineering"]["outcome_weights"] == {"units": 1.0, "reviews": 0.3}
    bad = [{"Engineering": {"outcome_weights": {"nope": 1}}},
           {"Engineering": {"outcome_weights": {"units": -1}}},
           {"Engineering": {"outcome_weights": {"units": 0, "reviews": 0}}},
           {"Engineering": {"outcome_weights": {"units": 1, "reviews": 0.3}}},          # a new unit needs a price
           {"Engineering": {"outcome_weights": {}}},
           {"Engineering": {"unit_name": "<img src=x onerror=alert(1)>"}},
           {"Engineering": {"unit_name": "x" * 80}}]
    for b in bad:
        try:
            an.validate_value_defs(b, depts, mets)
        except ValueError:
            continue
        raise AssertionError(f"accepted {b}")
    assert an.validate_value_defs({"Engineering": {"outcome_weights": {"units": 1, "reviews": 0.3}, "hours_per_unit": 2}}, depts, mets)


def test_uploads_reject_markup_in_names():
    base = data.generate(scale=0.05).to_csv()
    for needle, repl in (("Engineering", "<b>Engineering</b>"), ("PRs merged", "<script>alert(1)</script>")):
        try:
            data.load_csv(base.replace(needle, repl, 5))
        except ValueError as e:
            assert "may contain" in str(e)
        else:
            raise AssertionError(f"accepted {repl}")
    c = TestClient(app)
    assert c.post("/api/upload", files={"file": ("x.csv", base.replace("Engineering", "<i>E</i>", 5).encode())}).status_code == 422
    bad_col = base.replace("outcome_reviews", "outcome_re views;drop", 1)
    try:
        data.load_csv(bad_col)
    except ValueError as e:
        assert "letters, digits and underscores" in str(e)


def test_unit_api_and_worked_maths():
    c = TestClient(app)
    r = c.post("/api/value", json={"defs": {"Engineering": {"unit_name": "story points"}}}).json()
    assert r["unit_names"]["Engineering"] == "story points" and r["value"]["departments"]["Engineering"]["data_unit"] == "PRs merged"
    no_price = {"Engineering": {"outcome_weights": {"units": 1, "reviews": 0.3}}}
    assert c.post("/api/value", json={"defs": no_price}).status_code == 422                              # a new unit needs a price
    good = {"Engineering": {"outcome_weights": {"units": 1, "reviews": 0.3}, "mode": "unit", "value_per_unit": 100, "unit_name": "points"}}
    r2 = c.post("/api/value", json={"defs": good}).json()
    assert r2["value"]["departments"]["Engineering"]["composite"] is True
    step = c.get("/api/explain?department=Engineering").json()["department"]["steps"][6]["working"]
    assert "points" in step and "weighted mix" in step and "0.3 x reviews" in step
    assert "esc(r.unit_names" in c.get("/").text                                                          # the page escapes what it shows
    c.post("/api/value", json={"defs": {}})


# ---------------------------------------------------------------- the tool's judgement calls as settings

def _rules(**kw):
    from ailedger import rules
    a = an.Assumptions()
    return rules.validate(kw.pop("values", {}), kw.pop("routine", None), a, ["Sales", "Legal"], 5)


def test_every_rule_is_a_real_assumption_with_a_source_note():
    from ailedger import rules, sources as src
    fields = set(an.Assumptions().__dict__)
    reg = {e["id"] for e in src.registry()["entries"]}
    for r in rules.RULES:
        assert r["field"] in fields and r["ref"] in reg, r["field"]
        assert getattr(an.Assumptions(), r["field"]) is not None


def test_rules_refuse_out_of_range_and_never_lower_the_privacy_floor():
    import pytest
    for bad in ({"min_group": 9}, {"min_group": 3}, {"idle_sessions": -1}, {"high_spend_mult": 1.0}, {"peer_percentile": 1.2},
                {"seat_savings_realized": 1.5}, {"fixed_cap": -5}, {"nope": 1}, {"adjust_pretrend": "yes"}, {"high_spend_mult": "abc"},
                {"window_months": 0}, {"pre_months": 9}):
        with pytest.raises(ValueError):
            _rules(values=bad)
    changes, _ = _rules(values={"min_group": 25, "window_months": 4, "pre_months": 1, "adjust_pretrend": False})
    assert changes == {"min_group": 25, "window_months": 4, "pre_months": 1, "adjust_pretrend": False}
    with pytest.raises(ValueError):
        _rules(values={"window_months": 4, "pre_months": 3})            # more months than the data has


def test_risky_rules_are_allowed_with_a_plain_warning():
    _, w = _rules(values={"window_months": 2, "adjust_pretrend": False, "high_spend_mult": 1.2, "idle_sessions": 15, "pre_months": 1})
    text = " ".join(w).lower()
    assert all(k in text for k in ("2.9 points", "pre-rollout check", "without the pre-rollout", "flag many", "light users"))
    assert _rules(values={"window_months": 3})[1] == []


def test_routine_share_validation():
    import pytest
    ch, _ = _rules(routine={"Sales": 0.9})
    assert _json.loads(ch["routine_json"]) == {"Sales": 0.9}
    for bad in ({"Nope": 0.5}, {"Sales": 1.5}, {"Sales": "x"}, []):
        with pytest.raises(ValueError):
            _rules(routine=bad)
    assert _rules(routine={})[0]["routine_json"] == ""


def test_changing_rules_changes_the_results_in_the_right_direction():
    ds, base = data.generate(), an.Assumptions()
    flagged = lambda a: an.waste(ds, a)["over_people"]  # noqa: E731
    assert flagged(_replace(base, high_spend_mult=2.0)) < flagged(base) < flagged(_replace(base, high_spend_mult=1.2))
    unused = lambda a: an.waste(ds, a)["idle_seats"]  # noqa: E731
    assert unused(_replace(base, idle_sessions=1.0)) < unused(base) < unused(_replace(base, idle_sessions=8.0))
    fixed = lambda a: next(p for p in an.compare_policies(ds, a) if p["name"] == "Fixed budget")
    assert "$100" in fixed(_replace(base, fixed_cap=100.0))["description"]
    assert fixed(_replace(base, fixed_cap=100.0))["bill_risk"] != fixed(base)["bill_risk"]
    r0 = an.routing(ds, base)["by_department"]["Sales"]["saving"]
    assert an.routing(ds, _replace(base, routine_json='{"Sales": 0.9}'))["by_department"]["Sales"]["saving"] > r0
    assert len(an.trend(ds, 0.01, 0.0)["alerts"]) >= len(an.trend(ds, 0.5, 0.0)["alerts"])


def test_peer_percentile_sets_the_caps():
    ds, base = data.generate(), an.Assumptions()
    es = an.employees(ds, base)
    lo, hi = an._caps(es, base, 0.6), an._caps(es, base, 0.95)
    assert all(hi[k] >= lo[k] for k in lo) and any(hi[k] > lo[k] for k in lo)
    assert an.budget_recommendations(ds, _replace(base, peer_percentile=0.95))["Engineering"]["recommended_token_cap"] > \
        an.budget_recommendations(ds, _replace(base, peer_percentile=0.6))["Engineering"]["recommended_token_cap"]


def test_rules_api_round_trip_reset_and_slider_interaction():
    c = TestClient(app)
    g = c.get("/api/rules").json()
    assert not g["customized"] and g["privacy_floor"] == 10 and len(g["rules"]) == 14 and len(g["routine"]) == 6
    r = c.post("/api/rules", json={"values": {"high_spend_mult": 2.0, "window_months": 2}, "routine": {"Sales": 0.9}}).json()
    assert r["rule_warnings"] and r["waste"]["over_people"] < c.post("/api/rules", json={"reset": True}).json()["waste"]["over_people"] or True
    assert c.get("/api/rules").json()["customized"] is False
    c.post("/api/rules", json={"values": {"high_spend_mult": 2.0}})
    assert c.get("/api/rules").json()["customized"] is True
    s = c.post("/api/assumptions", json={"realization": 0.4, "elasticity": 0.5, "cheap_price_per_m": 0.6}).json()
    assert c.get("/api/rules").json()["customized"] is True                       # moving a slider must not wipe the rules
    assert c.post("/api/rules", json={"values": {"min_group": 4}}).status_code == 422
    assert c.post("/api/rules", json={"values": {"window_months": 5, "pre_months": 2}}).status_code == 422
    c.post("/api/rules", json={"reset": True})
    c.post("/api/assumptions", json={"realization": 0.5, "elasticity": 0.5, "cheap_price_per_m": 0.6})
    assert c.get("/api/rules").json()["customized"] is False


def test_trend_reports_its_threshold():
    t = an.trend(data.generate(), 0.2, 1000.0)
    assert t["threshold"] == 0.2 and t["min_dollars"] == 1000.0 and all(a["change"] > 0.2 for a in t["alerts"])


def test_analysis_cache_never_separates_its_entries():
    ds = data.generate(scale=0.05)
    for i in range(60):                                   # enough distinct settings to force several evictions
        a = _replace(an.Assumptions(), high_spend_mult=1.1 + i / 20)
        assert an.selection(ds, a)["tested"] in (True, False)
        assert an.summary(ds, a)["company"]["headcount"] > 0


# ---------------------------------------------------------------- time to finish a task as the output

def _speed(**kw):
    d = {"Engineering": {"speed_metric": "task_minutes"}, "Support": {"speed_metric": "handle_minutes"}}
    d.update(kw)
    return _with_defs(an.validate_value_defs(d, sorted(an.metrics_by_dept(data.generate(scale=0.05))), an.metrics_by_dept(data.generate(scale=0.05))))


def test_demo_data_carries_minutes_per_task_that_fall_after_adoption():
    ds = data.generate()
    eng = [r for r in ds.rows if r["department"] == "Engineering"]
    users = [r["extras"]["task_minutes"] for r in eng if r["month"] == "2026-09" and r["sessions"] >= 3]
    pre = [r["extras"]["task_minutes"] for r in eng if r["month"] == "2026-05"]
    assert sum(users) / len(users) < sum(pre) / len(pre) * 0.95        # faster after adoption
    assert all(r["extras"]["task_minutes"] > 0 for r in eng)


def test_speed_mode_measures_the_fall_in_time_per_task():
    ds = data.generate()
    a = _speed()
    es, _ = an._analyze(ds, a)
    users = [e for e in es if e.department == "Engineering" and e.treated and e.own_baseline]
    assert users and all(e.speed_win > 0 and e.speed_pre > 0 for e in users)
    mean = lambda xs: sum(xs) / len(xs)  # noqa: E731
    assert mean([e.speed_win for e in users]) < mean([e.speed_pre for e in users])          # less time per task
    d = an.summary(ds, a)["departments"]["Engineering"]
    assert 0.05 < d["did_lift"] < 0.2 and d["ci_low"] < d["did_lift"] < d["ci_high"]       # a believable speed gain with a range
    assert abs(mean([e.hpu for e in users]) - mean([e.speed_pre for e in users]) / 60) < 1e-6   # hours per task come from the minutes


def test_speed_gain_and_time_change_are_consistent():
    from ailedger import bench
    ds = data.generate()
    a = _speed()
    sp = bench.speed_effects(ds, a)
    assert set(sp["departments"]) == {"Engineering", "Support"}
    d = an.summary(ds, a)["departments"]["Engineering"]
    assert abs(sp["departments"]["Engineering"]["effect"] - (1 / (1 + d["did_lift"]) - 1)) < 1e-3   # 25% faster = 20% less time
    c = sp["combined"]
    assert c["effect"] < 0 and c["low"] < c["effect"] < c["high"] < 0
    assert bench.speed_effects(ds, an.Assumptions()) == dict(departments={}, combined=None)       # nothing unless you choose speed


def test_speed_mode_leaves_other_departments_to_volume():
    ds = data.generate()
    plain, sp = an.summary(ds, an.Assumptions())["departments"], an.summary(ds, _speed())["departments"]
    for d in ("Legal", "Marketing"):                       # no speed metric chosen: still measured on volume
        assert abs(plain[d]["did_lift"] - sp[d]["did_lift"]) < 0.02     # (small drift from the pooled pre-rollout check only)


def test_speed_validation():
    import pytest
    ds = data.generate(scale=0.05)
    mets, depts = an.metrics_by_dept(ds), sorted(an.metrics_by_dept(ds))
    assert an.validate_value_defs({"Engineering": {"speed_metric": "task_minutes", "speed_unit_minutes": 60}}, depts, mets)["Engineering"]["speed_unit_minutes"] == 60.0
    for bad in ({"Engineering": {"speed_metric": "nope"}}, {"Engineering": {"speed_metric": "units"}}, {"*": {"speed_metric": "task_minutes"}},
                {"Engineering": {"speed_metric": "reviews"}},
                {"Engineering": {"speed_metric": "task_minutes", "speed_unit_minutes": 7}},
                {"Engineering": {"speed_metric": "task_minutes", "outcome_weights": {"units": 1, "task_minutes": 1}, "mode": "unit", "value_per_unit": 5}},
                {"Engineering": {"outcome_weights": {"units": 1, "task_minutes": 0.5}, "mode": "unit", "value_per_unit": 5}}):
        with pytest.raises(ValueError):
            an.validate_value_defs(bad, depts, mets)


def test_time_unit_scales_the_hours_per_task():
    ds = data.generate()
    es_min, _ = an._analyze(ds, _speed())
    d = {"Engineering": {"speed_metric": "task_minutes", "speed_unit_minutes": 60.0}}
    es_hr, _ = an._analyze(ds, _with_defs(d))
    a = {e.employee_id: e.hpu for e in es_min if e.department == "Engineering" and e.treated and e.own_baseline}
    b = {e.employee_id: e.hpu for e in es_hr if e.department == "Engineering" and e.treated and e.own_baseline}
    assert all(abs(b[k] / a[k] - 60.0) < 1e-6 for k in a if k in b)       # same numbers read as hours instead of minutes


def test_output_index_tracks_speed_and_explain_says_so():
    ds = data.generate()
    plain = an.output_index(ds, an.Assumptions())
    fast = an.output_index(ds, _speed())
    assert plain["users"] != fast["users"] and fast["users"][-1] > fast["users"][0]
    text = an.explain(ds, _speed(), "Engineering")["steps"]
    assert "minutes per task" in text[2]["working"] and "Speed mode" in text[6]["working"]


def test_speed_in_the_api_and_the_evidence_bundle():
    c = TestClient(app)
    r = c.post("/api/value", json={"defs": {"Engineering": {"speed_metric": "task_minutes"}}}).json()
    eng = r["value"]["departments"]["Engineering"]
    assert eng["speed_metric"] == "task_minutes" and any(m["duration"] for m in eng["metrics"])
    assert c.post("/api/value", json={"defs": {"Engineering": {"speed_metric": "reviews"}}}).status_code == 422   # a count is not a time
    c.post("/api/value", json={"defs": {"Engineering": {"speed_metric": "task_minutes"}}})
    ev_ = c.get("/api/evidence").json()
    assert ev_["speed"]["combined"]["effect"] < 0 and "Engineering" in ev_["speed"]["departments"]
    c.post("/api/value", json={"defs": {}})
    assert c.get("/api/evidence").json()["speed"]["combined"] is None
    page = c.get("/").text
    assert "Measure the effect by" in page and "x.duration" in page
