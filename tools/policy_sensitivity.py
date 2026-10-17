import sys
sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__))))
from ailedger import analysis as an, data

ds = data.generate()
def table(label, a, pm=1.6, fr=0.05):
    pols = an.standard_policies()
    for p in pols:
        if p.name == "Pay per use":
            p.price_multiplier, p.friction = pm, fr
    rows = {r["name"]: r for r in (an.simulate(ds, a, p) for p in pols)}
    best = max(rows.values(), key=lambda r: r["net"])["name"]
    print(f"{label:38} best={best:17} " + " ".join(f"{k[:6]} {v['net']:>8.0f}" for k, v in rows.items()))
print("--- pay-per-use list-price multiplier (default 1.6)")
for pm in (1.0, 1.6, 2.5, 3.5, 5.0): table(f"price x{pm}", an.Assumptions(), pm=pm)
print("--- pay-per-use friction (default 5%)")
for fr in (0.05, 0.2, 0.4, 0.6): table(f"friction {fr:.0%}", an.Assumptions(), fr=fr)
print("--- both: x2.5 price and 20% friction"); table("price x2.5 + friction 20%", an.Assumptions(), pm=2.5, fr=0.2)
print("--- seat savings realized (default 0.8)")
for r in (0.8, 0.5, 0.2, 0.0): table(f"seat savings {r:.0%}", an.Assumptions(seat_savings_realized=r))
print("--- elasticity (default 0.5)")
for e in (0.2, 0.5, 0.8, 1.0): table(f"elasticity {e}", an.Assumptions(elasticity=e))
print("--- realization (default 0.5)")
for r in (0.2, 0.35, 0.5, 0.8, 1.0): table(f"realization {r:.0%}", an.Assumptions(realization=r))
