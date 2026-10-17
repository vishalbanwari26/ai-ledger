"""Stress test: score the analysis against the generator's true effect across scenarios."""
import statistics as st
import sys

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from ailedger import analysis as an, data  # noqa: E402

SEEDS = range(1, 13)


def spearman(a, b):
    def rk(x):
        o = sorted(range(len(x)), key=lambda i: x[i])
        r = [0] * len(x)
        for k, i in enumerate(o):
            r[i] = k
        return r
    ra, rb = rk(a), rk(b)
    n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def run(label, a=None, **gen):
    a = a or an.Assumptions()
    bias, cover, sign_ok, rank, comp_err = [], [], [], [], []
    idle_p, over_r, over_p, ctrl_n = [], [], [], []
    best = {}
    for seed in SEEDS:
        ds = data.generate(seed=seed, **gen)
        es, stats = an._analyze(ds, a)
        s = an.summary(ds, a)
        tl = [ds.truth[e.employee_id]["lift_window"] for e in es if e.treated and e.own_baseline]
        true_lift = st.mean(tl) if tl else 0.0
        bias.append(s["company"]["did_lift"] - true_lift)
        est, tru = [], []
        for d, v in s["departments"].items():
            group = [e for e in es if e.department == d]
            tv = a.realization * sum(
                ds.truth[e.employee_id]["lift_window"] * ds.truth[e.employee_id]["base_units"] * e.hpu * e.rate
                for e in group if e.treated)
            cost = v["monthly_cost"]
            troi = (tv - cost) / cost
            est.append(v["roi"]); tru.append(troi)
            cover.append(v["roi_low"] <= troi <= v["roi_high"])
            sign_ok.append((v["roi"] > 0) == (troi > 0))
        rank.append(spearman(est, tru))
        c = s["company"]
        ctv = sum(a.realization * ds.truth[e.employee_id]["lift_window"] * ds.truth[e.employee_id]["base_units"]
                  * e.hpu * e.rate for e in es if e.treated)
        comp_err.append((c["monthly_value"] - ctv) / ctv if ctv else 0)
        v = an.validate(ds, a)
        idle_p.append(v["idle_vs_nonusers"]["precision"]); over_r.append(v["high_spend"]["recall"])
        over_p.append(v["high_spend"]["precision"])
        ctrl_n.append(min(x["control_n"] for x in stats.values()))
        pol = an.compare_policies(ds, a)
        w = max(pol, key=lambda r: r["net"])["name"]
        best[w] = best.get(w, 0) + 1
        vbr = next(r for r in pol if r["name"] == "Variable by role"); sq = next(r for r in pol if r["name"] == "Status quo")
        best["VbR>SQ"] = best.get("VbR>SQ", 0) + (vbr["net"] > sq["net"])
    f = lambda x: f"{st.mean(x):+.3f}" if x else "n/a"  # noqa: E731
    print(f"{label:34} bias {f(bias)} (sd {st.pstdev(bias):.3f}) | cover {st.mean(cover):.0%} sign {st.mean(sign_ok):.0%} "
          f"rank {st.mean(rank):.2f} | co.value err {st.mean(comp_err):+.0%} | idle P {st.mean(idle_p):.2f} "
          f"over R {st.mean(over_r):.2f} P {st.mean(over_p):.2f} | min ctrl n {min(ctrl_n)} | best {dict(sorted(best.items()))}")


print("--- baseline and trend")
run("baseline")
for t in (0.0, 0.05, 0.10):
    run(f"trend {t:.0%}/mo", trend=t)
print("--- output noise (+/- per month)")
for n in (0.03, 0.15, 0.25, 0.40):
    run(f"noise {n:.0%}", noise=n)
print("--- self-selection: adopters would have grown faster anyway")
for d in (0.005, 0.01, 0.02, -0.01):
    run(f"adopter drift {d:+.1%}/mo", adopter_drift=d)
print("--- company size")
for sc in (0.05, 0.15, 0.4):
    run(f"headcount x{sc} ({round(1900*sc)} people)", scale=sc)
print("--- messy cases off")
run("no messy cases", messy=False)
print("--- analysis settings")
run("pre_months=1", a=an.Assumptions(pre_months=1))
run("window_months=2", a=an.Assumptions(window_months=2))
