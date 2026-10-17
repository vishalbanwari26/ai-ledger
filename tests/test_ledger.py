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
    for path in [*root.glob("ailedger/*.py"), root / "static/index.html", root / "README.md"]:
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
