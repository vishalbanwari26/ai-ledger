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
