# AI Ledger

Is your company's AI spend paying off, and should each team's budget be fixed or variable?

AI Ledger joins per-employee AI cost (seats, tokens) with outcome data (PRs merged, tickets closed, and so on),
estimates the real effect of AI with a control group, finds recoverable waste, simulates budget policies on your own
data, and lets you question the results in plain English. Answers come from NVIDIA Nemotron on Nebius Token Factory.

## How it uses NVIDIA Nemotron and Nebius

- **Nebius Token Factory** serves both models through its OpenAI-compatible API (`https://api.tokenfactory.nebius.com/v1/`), so the
  standard `openai` client is all the app needs. Model IDs are discovered at runtime from the Token Factory model list.
- **NVIDIA Nemotron 3 Ultra (550B)** answers questions as a tool-calling agent. It calls eleven tools backed by the app's own maths
  and never sees raw rows. A tool-calling answer took about 5 seconds in a test on 27 October 2026.
- **NVIDIA Nemotron 3.5 Lightning** writes the plain-English summary, the cheaper tier for a routine task (about 8 seconds).
- **Hosting:** the demo is a static site on GitHub Pages. The analysis runs in your browser (Python compiled to WebAssembly), and
  live questions call Token Factory straight from the page with your own key. A server build is also included and can run on a
  Nebius Serverless Endpoint (see the deploy section), but the hosted demo does not use one.
- **Track:** Best Apps and Agents.

## Try it

**https://vishalbanwari.tech/ai-ledger/** runs the whole app in your browser, with no server. The analysis (sliders, value
definition, rules, CSV upload) works straight away. To ask the Nemotron analyst anything, open the Ask tab and paste your own Nebius
Token Factory key: it is stored only in your browser and sent only to `api.tokenfactory.nebius.com`. Without a key you can read
real answers recorded from Nemotron 3 Ultra, clearly labelled.

To rebuild and publish the static site: `./tools/publish_site.sh`. To record fresh answers: `NEBIUS_API_KEY=... python tools/record_answers.py`.

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
  and marked with what was verified and what was left out ([docs/evidence.md](docs/evidence.md)). Context, not proof. It also puts the studies' metrics to work: the break-even effect this spend needs,
  what-if returns if the effect matched each published study, the measured effect by experience level, and a check of
  what employees say against what was measured.
- **Lets you define what AI output is worth:** the Your value tab sets, per department, how a unit of output is valued (hours x
  hourly rate from the data, or your own dollar figure per unit), what one unit of output is called, how several metrics
  count towards output (for example a pull request = 1, a review = 0.3), plus an optional benefit per user. Every result updates, a
  before-and-after shows what changed, and the definition can be downloaded as JSON.
- **References every value:** a Sources tab and an ⓘ next to each value say where it comes from: a published study, a public
  price list, our rule of thumb, or an assumption with no source. Values are read from the running code, and a test keeps
  [docs/sources.md](docs/sources.md) in sync and fails if an assumption is added without a source note.
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

Needs Python 3.11 or newer (tested on 3.13).

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
export NEBIUS_API_KEY=...        # Nebius Token Factory key
.venv/bin/uvicorn ailedger.app:app --port 8077
```

If `python3 -m venv` fails on your machine (some Homebrew Python 3.14 builds do), use [uv](https://docs.astral.sh/uv/) instead:

```bash
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -r requirements.txt
```

Open http://localhost:8077. The dashboard works without a key; the brief and Q&A need it.

## Tests

```bash
.venv/bin/pip install pytest httpx && .venv/bin/pytest
```

## Using real data

Upload a CSV with one row per employee per month. Required columns: `employee_id, department, role, month, seat_cost,
token_cost, tokens, sessions, outcome_units, hours_per_unit, hourly_rate`. Optional: `level` (intern, junior, mid,
senior; default mid), a time-per-task column such as `outcome_task_minutes` (lower is better; choose it as the speed metric), `unit_name` (what one unit of `outcome_units` is called, e.g. "story points"), and any number of
extra `outcome_<metric>` columns (e.g. `outcome_reviews`). Names use letters, digits, spaces and light punctuation only.
On the Your value tab you can rename the unit and define output as a weighted mix of your metrics. You need at least 4 months, and the first 2 should be before AI rollout: they are each person's
baseline. Join vendor billing (cost, tokens, sessions) with your work systems (outcome units) and HR data (role, rate).
Download the sample CSV from the UI to see the exact shape.

## Deploy on Nebius Serverless Endpoints

The quickest path is the guided script, which also covers the manual steps (CLI login, a demo-only key, making the image public,
checking the live app, the video and the form): `./deploy/wizard.sh`. The commands it runs are below.

The app is a CPU container; the models run on Token Factory, so no GPU is needed.

```bash
IMAGE=ghcr.io/<you>/ai-ledger:latest NEBIUS_API_KEY=... ./deploy/deploy.sh
```

The script builds a linux/amd64 image, pushes it, creates a public endpoint with `nebius ai endpoint create`, and
prints the HTTPS URL. The endpoint has no token auth so reviewers can open it; the app caps model calls per hour
(`LEDGER_LLM_PER_HOUR`, default 120) and gives every visitor their own session, so uploads never leak between people.
Use a key created only for the demo and rotate it afterwards. Stop or delete the endpoint when judging ends.

## What you can customize

| What | Where | Notes |
|---|---|---|
| Your data | Upload CSV | Optional `level`, `unit_name` and extra `outcome_<metric>` columns |
| What one unit of output is called, and how several metrics count towards output | Your value tab | A weighted mix is a new unit, so it must be priced |
| Whether to measure the effect on volume or on speed (time to finish a task) | Your value tab | Speed needs a time column such as `outcome_task_minutes`; it is applied to baseline task volume and priced as freed-up hours |
| What a unit of output is worth (hours x rate, or your dollars per unit) and an optional benefit per user | Your value tab | Per department, with a default for all |
| Share of extra output counted as real, elasticity, cheaper model price, pay-per-use price | Sliders in "Data and assumptions" | |
| When a seat is unused, what counts as high spend, the peer percentile for caps, the smallest peer group | Rules tab | Out-of-range values are refused |
| Baseline and measured months, the pre-rollout adjustment | Rules tab | Risky settings come with a warning from the stress tests |
| Seat savings realized, rationing, quality penalty, the fixed-budget cap | Rules tab | |
| Drift-alert threshold, routine share of tokens by department | Rules tab | |
| Smallest group ever shown | Rules tab | Can be raised, never below 10 |

Not yet customizable: your own budget policies, excluding people or departments, rollout dates by team, extra cost lines such as
training, currency, and saved side-by-side scenarios.

## Limits

- The demo company is synthetic. Value is an estimate built on stated assumptions; the sliders show how sensitive the
  conclusions are, and "break-even credit" shows how much of the estimated gain must be real for a team to pay for itself.
- Adopters choose to adopt. The control group removes shared trends such as seasonality, and the pre-rollout check
  removes a gap that already existed. Differences that start only at rollout cannot be told apart from the AI effect.
  A rollout with random or staggered assignment would be stronger evidence.
- Pay per use depends on an assumed list-price multiplier. The app shows the break-even multiplier; get a real quote.
- Level differences in dollar ROI mostly reflect hourly rate. Do not cut a level's access on ROI alone.
- The routine-token share per department and the cheaper model's price are planning assumptions, not measurements.
