"""Assemble the static site (the whole app running in the browser) into a folder you can host anywhere, e.g. GitHub Pages.
Usage: python tools/build_site.py [outdir]     (default: site/)"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_ONLY = {"app.py", "llm.py"}  # need FastAPI / the OpenAI client; the browser engine does not


def build(out: str) -> list[str]:
    os.makedirs(out, exist_ok=True)
    html = open(os.path.join(ROOT, "static", "index.html"), encoding="utf-8").read()
    marker = '<script src="/static/charts.js"></script>\n<script>'
    if marker not in html:
        raise SystemExit("static/index.html changed: update the marker in tools/build_site.py")
    html = html.replace(marker, '<script src="charts.js"></script>\n<script>window.AIL_STATIC=true;</script>\n'
                                '<script src="static-mode.js"></script>\n<script>', 1)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(html)
    for src, name in (("static/charts.js", "charts.js"), ("web/static-mode.js", "static-mode.js"),
                      ("web/pyworker.js", "pyworker.js"), ("web/recorded.json", "recorded.json")):
        shutil.copy(os.path.join(ROOT, src), os.path.join(out, name))
    with zipfile.ZipFile(os.path.join(out, "ailedger.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(os.listdir(os.path.join(ROOT, "ailedger"))):
            if f.endswith(".py") and f not in SERVER_ONLY:
                z.write(os.path.join(ROOT, "ailedger", f), f"ailedger/{f}")
    open(os.path.join(out, ".nojekyll"), "w").close()   # serve files as they are
    shutil.copy(os.path.join(ROOT, "LICENSE"), os.path.join(out, "LICENSE"))
    return sorted(os.listdir(out))


if __name__ == "__main__":
    dest = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "site")
    print("built", dest, build(dest))
