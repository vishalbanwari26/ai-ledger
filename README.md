# AI Ledger

Is your company's AI spend paying off, and should each team's budget be fixed or variable?

AI Ledger joins per-employee AI cost (seats, tokens) with outcome data (PRs merged, tickets closed, and so on),
estimates the real effect of AI with a control group, finds recoverable waste, simulates budget policies on your own
data, and lets you question the results in plain English. Answers come from NVIDIA Nemotron on Nebius Token Factory.

## What it does

- **Finds waste:** unused seats and above-norm spend on high-spend seats, with the share of a seat you can actually cancel after contract friction.
- **Estimates return honestly:** compares each person to their own first two months, then subtracts what happened to
  people who never adopted (difference-in-differences). Growth is a ratio, so an intern and a senior are comparable.
  Estimates are shrunk toward the department mean by how noisy individuals are, and every ROI carries a 95% range.
  A department whose range includes zero is labelled uncertain, and gets "review", never "restrict".
- **Shows its working:** a "Show the math" section walks each department through nine steps with its own numbers
  (cost, growth, control group, range, dollars, ROI, break-even, recoverable spend), plus how each budget policy is computed.
- **Shows four charts, each answering one question:** which departments clearly pay off (return per $1 with its 95% range),
  where each AI dollar goes, whether output rose because of AI or for everyone (adopters against a control group over time),
  and the budget trade-off (net value against bill risk). Each has hover details and a table view.
- **Checks itself against published research:** an Evidence tab compares the tool's estimate with nine studies, each linked
  and marked with what was verified and what was left out ([docs/evidence.md](docs/evidence.md)). Context, not proof.
- **Explains every term:** a Glossary tab with plain definitions and worked examples that use the live numbers.
- **Separates fact from opinion:** every number is labelled measured, estimated, assumed or judgement, and each decision is
  re-run in 180 assumption scenarios to show which hold and which depend on assumptions.
- **Checks that adopters were not already ahead:** compares adopters and non-adopters in the months before rollout and
  removes any pre-existing gap, with a warning when it is significant.
- **Compares peers fairly:** high spend is judged against people of the same role and level, never the whole department.
  Interns and juniors are never capped below the department cap, since they iterate more while learning.
- **Simulates four budget policies:** status quo, fixed, pay per use, variable by role. Ranked on net dollars and bill
  risk (extra cost if everyone spends at their own peak month), not on the ROI ratio, which rises whenever spend falls.
- **Prices model routing:** what moving routine tokens to a cheaper open model saves, and the value put at risk.
- **Turns findings into actions:** a list of seats to reclaim and spend to cap, each with a reason; approve what you
  want and download it as CSV.
- **Watches drift:** monthly spend per department with alerts for sudden jumps.
- **Checks itself:** on the synthetic company the generator keeps hidden truth labels, and the app scores how well the
  analysis recovers them (precision and recall), including part-timers, people on leave and new hires.
- **No blaming, no individuals:** results are shown for groups of 10 or more. Nobody is named, ranked or exported, and
  the analyst is instructed to frame findings as seat allocation, training, tools and budget design, with enablement
  suggested before any seat or cap change. A test fails if blaming words or employee IDs reach the output.

## How the Nemotron analyst works

`ailedger/llm.py` is a tool-calling agent. The model never sees raw rows. It calls tools backed by the maths in
`ailedger/analysis.py`, and the UI shows every tool call behind an answer, so each number can be checked. Policy
rankings are pre-computed in code, so the model quotes them instead of comparing rows itself.
Two Nemotron tiers: the largest available model answers questions; the smallest writes the executive brief. Models are
discovered from the Token Factory model list, or set with `NEBIUS_MODEL_REASON` and `NEBIUS_MODEL_FAST`.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export NEBIUS_API_KEY=...        # Nebius Token Factory key
.venv/bin/uvicorn ailedger.app:app --port 8077
```

Open http://localhost:8077. The dashboard works without a key; the brief and Q&A need it.

## Tests

```bash
.venv/bin/pip install pytest httpx && .venv/bin/pytest
```

## Using real data

Upload a CSV with one row per employee per month. Required columns: `employee_id, department, role, month, seat_cost,
token_cost, tokens, sessions, outcome_units, hours_per_unit, hourly_rate`. Optional: `level` (intern, junior, mid,
senior; default mid). You need at least 4 months, and the first 2 should be before AI rollout: they are each person's
baseline. Join vendor billing (cost, tokens, sessions) with your work systems (outcome units) and HR data (role, rate).
Download the sample CSV from the UI to see the exact shape.

## Deploy on Nebius Serverless Endpoints

The app is a CPU container; the models run on Token Factory, so no GPU is needed.

```bash
IMAGE=ghcr.io/<you>/ai-ledger:latest NEBIUS_API_KEY=... ./deploy/deploy.sh
```

The script builds a linux/amd64 image, pushes it, creates a public endpoint with `nebius ai endpoint create`, and
prints the HTTPS URL. The endpoint has no token auth so reviewers can open it; the app caps model calls per hour
(`LEDGER_LLM_PER_HOUR`, default 120) and gives every visitor their own session, so uploads never leak between people.
Use a key created only for the demo and rotate it afterwards. Stop or delete the endpoint when judging ends.

## Limits

- The demo company is synthetic. Value is an estimate built on stated assumptions; the sliders show how sensitive the
  conclusions are, and "break-even credit" shows how much of the estimated gain must be real for a team to pay for itself.
- Adopters choose to adopt. The control group removes shared trends such as seasonality, and the pre-rollout check
  removes a gap that already existed. Differences that start only at rollout cannot be told apart from the AI effect.
  A rollout with random or staggered assignment would be stronger evidence.
- Pay per use depends on an assumed list-price multiplier. The app shows the break-even multiplier; get a real quote.
- Level differences in dollar ROI mostly reflect hourly rate. Do not cut a level's access on ROI alone.
- The routine-token share per department and the cheaper model's price are planning assumptions, not measurements.
