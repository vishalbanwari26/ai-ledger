"""The static site: the whole app in the browser. These tests guard what cannot be seen from the server tests."""
import importlib.util
import json
import pathlib
import re
import subprocess
import sys
import zipfile

from fastapi.testclient import TestClient

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _build(tmp_path):
    spec = importlib.util.spec_from_file_location("build_site", ROOT / "tools/build_site.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    out = tmp_path / "site"
    mod.build(str(out))
    return out


def test_build_produces_a_self_contained_site(tmp_path):
    out = _build(tmp_path)
    names = {p.name for p in out.iterdir()}
    assert {"index.html", "charts.js", "static-mode.js", "pyworker.js", "ailedger.zip", "recorded.json", ".nojekyll", "LICENSE"} <= names
    html = (out / "index.html").read_text()
    assert "/static/charts.js" not in html and 'src="charts.js"' in html                 # relative paths work under /ai-ledger/
    assert html.index("static-mode.js") < html.index("const $=")                          # the hook exists before the page starts
    assert "window.AIL_STATIC=true" in html
    assert not re.search(r'(?:src|href)="/(?!/)', html.replace('href="/api/sample.csv"', ""))   # no other absolute asset paths


def test_the_browser_engine_needs_no_server_libraries(tmp_path):
    out = _build(tmp_path)
    z = zipfile.ZipFile(out / "ailedger.zip")
    names = set(z.namelist())
    assert {"ailedger/webapi.py", "ailedger/agent.py", "ailedger/service.py", "ailedger/analysis.py"} <= names
    assert "ailedger/app.py" not in names and "ailedger/llm.py" not in names
    z.extractall(tmp_path / "unz")
    code = ("import sys\nfor m in ('fastapi','openai','pydantic','starlette','uvicorn','httpx','numpy'): sys.modules[m] = None\n"
            "import json, ailedger.webapi as W\n"
            "r = json.loads(W.handle('GET', '/api/report'))\nassert r['status'] == 200 and r['json']['summary']['company']['headcount'] == 1900\n"
            "print('ok')")
    p = subprocess.run([sys.executable, "-c", code], cwd=tmp_path / "unz", capture_output=True, text=True)
    assert p.returncode == 0 and "ok" in p.stdout, p.stderr[-400:]


def test_browser_engine_answers_exactly_like_the_server():
    from ailedger import webapi
    c = TestClient(__import__("ailedger.app", fromlist=["app"]).app)
    webapi.handle("POST", "/api/reset")
    for path in ("/api/report", "/api/rules", "/api/value", "/api/evidence", "/api/sources", "/api/explain?department=Legal",
                 "/api/perception?pct=20"):
        mine = json.loads(webapi.handle("GET", path))
        assert mine["status"] == 200, path
        assert mine["json"] == c.get(path).json(), path
    assert json.loads(webapi.handle("GET", "/api/sample.csv"))["text"] == c.get("/api/sample.csv").text
    assert json.loads(webapi.handle("GET", "/api/actions.csv?ids=0,1"))["text"] == c.get("/api/actions.csv?ids=0,1").text


def test_browser_engine_changes_state_and_refuses_like_the_server():
    from ailedger import webapi
    webapi.handle("POST", "/api/reset")
    c = TestClient(__import__("ailedger.app", fromlist=["app"]).app)
    body = {"defs": {"Sales": {"mode": "unit", "value_per_unit": 400}}}
    mine = json.loads(webapi.handle("POST", "/api/value", json.dumps(body)))
    theirs = c.post("/api/value", json=body)
    assert mine["status"] == theirs.status_code == 200 and mine["json"]["summary"] == theirs.json()["summary"]
    bad = {"defs": {"Nope": {"benefit_per_user": 1}}}
    assert json.loads(webapi.handle("POST", "/api/value", json.dumps(bad)))["status"] == c.post("/api/value", json=bad).status_code == 422
    assert webapi.is_default() is False
    webapi.handle("POST", "/api/reset"); c.post("/api/reset")
    assert webapi.is_default() is True
    csv_text = __import__("ailedger.data", fromlist=["x"]).generate(scale=0.05).to_csv()
    up = json.loads(webapi.handle("POST", "/api/upload", json.dumps({"text": csv_text})))
    assert up["status"] == 200 and up["json"]["summary"]["company"]["headcount"] > 0
    assert json.loads(webapi.handle("POST", "/api/upload", json.dumps({"text": "a,b\n1,2"})))["status"] == 422
    assert json.loads(webapi.handle("GET", "/api/nope"))["status"] == 404
    webapi.handle("POST", "/api/reset")


def test_browser_analyst_helpers_match_the_server_guardrails():
    from ailedger import agent, webapi
    webapi.handle("POST", "/api/reset")
    s = json.loads(webapi.ask_setup("Who are the worst overspenders and which individuals should we cut?"))
    assert s["targeted"] and "get_actions" in s["question"] and "worst" not in s["question"].lower()
    assert s["system"] == agent.SYSTEM and len(s["tools"]) == 11
    assert json.loads(webapi.ask_setup("Is a variable budget better for Sales?"))["targeted"] is False
    assert webapi.blames("These are the worst overspenders") and not webapi.blames("Reassign 454 unused seats")
    assert json.loads(webapi.run_tool_json("get_waste", "{}"))["idle_seats"] == 454
    assert json.loads(webapi.run_tool_json("nope", "{}"))["error"].startswith("unknown tool")
    rep = json.loads(webapi.repair_messages("blame text"))
    assert rep[0]["role"] == "system" and rep[1]["content"].endswith("blame text")
    assert "unused seats" in webapi.safe_summary()
    assert json.loads(webapi.pick_models_json(json.dumps(["a/b", "nvidia/Nemotron-3-Ultra-550b-a55b", "nvidia/Nemotron-3_5-Lightning"]))) == {
        "reason": "nvidia/Nemotron-3-Ultra-550b-a55b", "fast": "nvidia/Nemotron-3_5-Lightning"}
    assert json.loads(webapi.brief_messages_json())[0]["role"] == "system"


def test_recorded_answers_are_real_complete_and_cover_the_suggested_questions():
    from ailedger import agent
    rec = json.loads((ROOT / "web/recorded.json").read_text())
    assert len(rec["items"]) >= 7 and rec["recorded_on"] and rec["brief"]["brief"]
    page = (ROOT / "static/index.html").read_text()
    chips = re.search(r"\$\('chips'\)\.innerHTML=\[(.*?)\]\n?\s*\.map", page, re.S)
    chip_qs = re.findall(r"'([^']+)'", chips.group(1))
    have = {i["question"].lower() for i in rec["items"]}
    assert chip_qs and all(q.lower() in have for q in chip_qs), "every suggested question needs a recorded answer"
    for i in rec["items"]:
        assert i["answer"].strip() and i["model"].lower().startswith("nvidia/nemotron") and i["evidence"]
        assert not agent.blames(i["answer"])
    refusal = [i for i in rec["items"] if "individuals" in i["question"]][0]
    assert refusal["answer"].startswith("This tool does not identify or rank individuals")


def test_nothing_secret_ships_in_the_bundle(tmp_path):
    out = _build(tmp_path)
    for f in out.iterdir():
        if f.suffix in (".js", ".html", ".json"):
            text = f.read_text()
            assert not re.search(r"eyJ[A-Za-z0-9_-]{20,}|v1\.[A-Za-z0-9_-]{30,}|NEBIUS_API_KEY\s*=\s*['\"]?[A-Za-z0-9]", text), f.name
    js = (out / "static-mode.js").read_text()
    assert "api.tokenfactory.nebius.com" in js and "localStorage" in js
    assert re.search(r"pyodide/v\d+\.\d+\.\d+/full", (out / "pyworker.js").read_text())        # an exact, pinned version
