"""Write docs/sources.md from the live registry, so the document cannot disagree with the code.
Usage: python tools/build_sources_doc.py        (a test fails if the committed file is out of date)"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from ailedger import sources  # noqa: E402


def render() -> str:
    r = sources.registry()
    out = ["# Where every value comes from", "",
           "Generated from the running code by `tools/build_sources_doc.py`; the same entries appear on the Sources tab and in the "
           "ⓘ pop-ups. Most dollar figures are assumptions, and each says so.", "",
           f"Price lists and studies were read on {r['read_on']}.", "", "## Kinds", ""]
    out += [f"- **{label}** (`{k}`)" for k, label in r["kinds"].items()]
    group = None
    for e in r["entries"]:
        if e["group"] != group:
            group = e["group"]
            out += ["", f"## {group}", ""]
        out += [f"### {e['label']}", "", f"- **Value used:** {e['value']}", f"- **Origin:** {r['kinds'][e['kind']]}",
                f"- **Used in:** {e['where']}", f"- **Why:** {e['why']}"]
        if e["caveat"]:
            out.append(f"- **Caveat:** {e['caveat']}")
        for ref in e["refs"]:
            x = r["refs"][ref]
            out.append(f"- **Reference:** [{x['label']}]({x['url']}), {'read ' + x['read'] if x['confirmed'] else 'not confirmed'}. {x['says']}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


if __name__ == "__main__":
    path = os.path.join(ROOT, "docs", "sources.md")
    open(path, "w").write(render())
    print("wrote", path)
