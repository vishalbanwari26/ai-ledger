# AI Ledger

Is your company's AI spend paying off, and should each team's budget be fixed or variable?

AI Ledger joins per-employee AI cost (seats, tokens) with outcome data (PRs merged, tickets closed, and so on),
computes ROI per person, team and company, simulates budget policies on your own data, and lets you question the
results in plain English. Answers come from NVIDIA Nemotron running on Nebius Token Factory.

## How it works

- `ailedger/analysis.py`: all the maths. Value = (units above the person's own baseline) x hours per unit x hourly
  rate x a realization factor. ROI = (value - cost) / cost. Employees are segmented as idle, overspender,
  low-return, break-even or high-return. Four budget policies are simulated: status quo, fixed budget,
  pay per use, and variable by role (seats only for active users, per-department token cap, pooled allowance).
- `ailedger/llm.py`: a tool-calling analyst. The model never sees raw rows. It calls tools backed by the maths
  above, and the UI shows every tool call behind an answer, so each number can be checked.
- Two Nemotron tiers: the largest available model handles multi-step questions; the smallest handles routine
  calls such as the executive brief. Models are discovered from the Token Factory model list, or set with
  `NEBIUS_MODEL_REASON` and `NEBIUS_MODEL_FAST`.
- Assumptions (value realization, throttle elasticity) are sliders in the UI and change every number live.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export NEBIUS_API_KEY=...        # Nebius Token Factory key
.venv/bin/uvicorn ailedger.app:app --port 8077
```

Open http://localhost:8077. The dashboard works without a key; the brief and Q&A need it.
Download the sample CSV from the UI to see the expected columns, then upload your own.

## Tests

```bash
.venv/bin/pip install pytest httpx && .venv/bin/pytest
```

## Limits

The demo company is synthetic. Value is an estimate built on stated assumptions, and attributing output gains to AI
is the hard part in practice: use the realization slider to see how sensitive the conclusions are.

## Deploy on Nebius Serverless Endpoints

The app is a CPU container; the models run on Token Factory, so no GPU is needed.

```bash
IMAGE=ghcr.io/<you>/ai-ledger:latest NEBIUS_API_KEY=... ./deploy/deploy.sh
```

The script builds a linux/amd64 image, pushes it, creates a public endpoint with `nebius ai endpoint create`, and
prints the HTTPS URL. The endpoint has no token auth so reviewers can open it; the app caps model calls per hour
(`LEDGER_LLM_PER_HOUR`, default 120) and gives every visitor their own session, so uploads never leak between people.
Use a key created only for the demo and rotate it afterwards. Stop or delete the endpoint when judging ends.

## Using real data

The CSV upload takes real exports. Required columns: `employee_id, department, role, month, seat_cost, token_cost,
tokens, sessions, outcome_units, baseline_units, hours_per_unit, hourly_rate`. Join your vendor billing (cost, tokens,
sessions) with your own work systems (outcome units, pre-AI baseline) and HR data (role, rate).
