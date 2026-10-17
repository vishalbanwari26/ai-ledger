# Where every value comes from

Generated from the running code by `tools/build_sources_doc.py`; the same entries appear on the Sources tab and in the ⓘ pop-ups. Most dollar figures are assumptions, and each says so.

Price lists and studies were read on 2026-10-18.

## Kinds

- **Taken from a published study** (`published`)
- **Anchored to a public price list** (`list-price`)
- **Standard statistical convention** (`convention`)
- **Our method choice (tested)** (`design`)
- **Our rule of thumb** (`judgement`)
- **Our assumption, no source** (`assumption`)
- **Invented for the demo company** (`demo-data`)
- **Defined by you** (`yours`)
- **Computed from your data** (`data`)

## Dollars and prices

### Share of extra output counted as real value

- **Value used:** 50%
- **Origin:** Our assumption, no source
- **Used in:** Every dollar figure for value, ROI and break-even
- **Why:** Extra output is not automatically extra money, so only part is counted. Half is a placeholder; the break-even credit on each department shows how much it matters.
- **Caveat:** The Danish study is context for counting less than all of it (it found no effect on earnings or hours); it does not give 50%.
- **Reference:** [Humlum, Vestergaard (2025)](https://www.nber.org/papers/w33777), read 2026-10-18. Precise null effects on earnings and recorded hours; effects larger than 2% ruled out two years after ChatGPT's launch. Employers shifted people toward new tasks such as AI oversight.

### What one unit of output is worth

- **Value used:** hours per unit x hourly rate, from the data
- **Origin:** Computed from your data
- **Used in:** Value per user, ROI, break-even, policies
- **Why:** By default each department's own hours per unit and hourly rate from your data. Replace it with a dollar value per unit, or add a benefit per user, on the Your value tab.
- **Caveat:** In the demo company these rates and hours are invented (see demo-data entries).

### Share of a reclaimed seat's cost actually saved

- **Value used:** 80%
- **Origin:** Our assumption, no source
- **Used in:** Unused-seat savings, the plan's saving, the headline
- **Why:** Contracts have minimums and notice periods, so not every cancelled dollar comes back.
- **Caveat:** The Claude Enterprise listing shows a 20-seat minimum and annual billing, so minimums exist; the 80% itself is ours.
- **Reference:** [Claude plans and pricing](https://claude.com/pricing), read 2026-10-18. Team plan standard seat $20 a month billed annually ($25 monthly), premium seat $100 ($125 monthly). Enterprise: $20 per seat a month billed annually with a 20-seat minimum, usage charged on top at API rates.

### Blended price of a frontier model, per 1M tokens

- **Value used:** $5.00
- **Origin:** Our assumption, no source
- **Used in:** Token cost in the demo data, routing saving
- **Why:** A blend of input and output prices at 3 input tokens for each output token. Sonnet 5.5 ($2 in, $10 out) blends to $4.00 and Opus 5.5 ($4 in, $20 out) to $8.00, so $5.00 sits between them.
- **Caveat:** The 3-to-1 input-to-output mix is ours. Use your own invoices.
- **Reference:** [Anthropic API pricing](https://platform.claude.com/docs/en/about-claude/pricing), read 2026-10-18. Claude Sonnet 5.5: $2 input and $10 output per million tokens. Opus 5.5: $4 and $20. Fable 5.1: $10 and $50.

### Price of the cheaper model for routine work, per 1M tokens

- **Value used:** $0.60
- **Origin:** Our assumption, no source
- **Used in:** Model routing estimate
- **Why:** Deliberately above the listed price of the smallest Nemotron models (about $0.06 in and $0.24 out), to stay conservative.
- **Caveat:** The listing is third-party and not confirmed on Nebius's own page.
- **Reference:** [Nemotron prices on Nebius (third-party listing)](https://custom.typingmind.com/tools/estimate-llm-usage-costs/nebius/nemotron-3-5-lightning), not confirmed. A third-party listing shows the smallest Nemotron models on Nebius at about $0.06 input and $0.24 output per million tokens, Super 120B at $0.30 and $0.90, Ultra 550B at $1.00 and $3.00. Nebius's own price page did not load here, so these are not confirmed.

### Value lost on tokens moved to the cheaper model

- **Value used:** 2%
- **Origin:** Our assumption, no source
- **Used in:** Model routing estimate
- **Why:** A small penalty so routing is not shown as free. No measurement behind it.
- **Caveat:** Measure it on your own tasks.

### Share of tokens that are routine, by department

- **Value used:** Engineering 50%, Support 80%, Sales 70%, Marketing 60%, Finance 60%, Legal 40%
- **Origin:** Our assumption, no source
- **Used in:** Model routing estimate
- **Why:** A planning guess: how much of each department's use is summaries, drafts and lookups a smaller model could do.
- **Caveat:** Measure it on your own traffic before relying on it.

### List price of tokens without a seat plan, as a multiple of the seat-plan rate

- **Value used:** 1.6x
- **Origin:** Our assumption, no source
- **Used in:** The pay-per-use policy and its break-even price
- **Why:** A placeholder. The page shows the break-even multiplier, which matters more than this value.
- **Caveat:** Seat plans bundle usage and pay-as-you-go does not, so the multiple depends on your contract. Get a real quote.
- **Reference:** [Claude plans and pricing](https://claude.com/pricing), read 2026-10-18. Team plan standard seat $20 a month billed annually ($25 monthly), premium seat $100 ($125 monthly). Enterprise: $20 per seat a month billed annually with a 20-seat minimum, usage charged on top at API rates.

### Value lost because people ration metered use

- **Value used:** 5%
- **Origin:** Our assumption, no source
- **Used in:** The pay-per-use policy
- **Why:** People tend to use a metered tool less. 5% is a small guess with no source.
- **Caveat:** Highly uncertain; try 20% to 40% in the policy sensitivity.

### How much value is lost when someone's allowance is cut

- **Value used:** 0.5
- **Origin:** Our assumption, no source
- **Used in:** Fixed budget and token-cap policies: value kept = (cap / usage)^elasticity
- **Why:** 0 means no loss, 1 means value falls in step with usage. Half is a middle guess.
- **Caveat:** Not measured.

### Token cap in the fixed-budget policy

- **Value used:** $60 per person a month
- **Origin:** Our rule of thumb
- **Used in:** The fixed-budget policy
- **Why:** A round figure near what a heavy user spends in the demo data.


## How the effect is measured

### Months used as baseline and as the measured window

- **Value used:** first 2 and last 3
- **Origin:** Our method choice (tested)
- **Used in:** The AI effect, ROI, the chart of output over time
- **Why:** Two baseline months let a person be compared with their own past. Three measured months let a median shrug off one month of leave.
- **Caveat:** A 2-month window overstated the effect by about 2.9 points in the stress test.
- **Reference:** [Stress tests (docs/robustness.md)](https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/robustness.md), read 2026-10-18. Results of re-running the method on companies with a known true effect.

### Sessions a month below which a seat counts as unused

- **Value used:** 3
- **Origin:** Our rule of thumb
- **Used in:** Unused seats, control group, the headline
- **Why:** A seat opened fewer than three times a month is not in meaningful use.
- **Caveat:** Changing it changes who is a user and who is in the control group.

### Remove a growth gap adopters already had before rollout

- **Value used:** on
- **Origin:** Our method choice (tested)
- **Used in:** The AI effect and its range
- **Why:** If people who later adopted AI were already growing faster, that gap is extrapolated and removed, and a warning shows.
- **Caveat:** Without it a +1% a month self-selection bias overstated the effect by 25% in the stress test.
- **Reference:** [Stress tests (docs/robustness.md)](https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/robustness.md), read 2026-10-18. Results of re-running the method on companies with a known true effect.

### Multiplier for a 95% range

- **Value used:** 1.96
- **Origin:** Standard statistical convention
- **Used in:** Every range and confidence label
- **Why:** Plus or minus 1.96 standard errors covers 95% of a normal distribution.

### Assumption values tried in the robustness check

- **Value used:** realization 25%, 35%, 50%, 75%, 100%; price multiple 1.2x, 1.6x, 2x, 2.6x
- **Origin:** Our rule of thumb
- **Used in:** The 180-scenario robustness card
- **Why:** A wide, plausible spread around each default. Wider ranges make fewer decisions look robust.

### Margin that counts as 'only just' above or below break-even

- **Value used:** 25% of the range's half-width
- **Origin:** Our rule of thumb
- **Used in:** The break-even verdict
- **Why:** Stops a 0.03-point margin being called 'clearly' above break-even.


## Rules of thumb

### A seat is 'high spend' above this multiple of its peers' median spend

- **Value used:** 1.5x
- **Origin:** Our rule of thumb
- **Used in:** High-spend seats, the above-norm spend in the headline
- **Why:** Peers are people of the same department and level; the rule also needs a negative ROI.
- **Caveat:** A flag to start a conversation, not a verdict. Precision is about 0.78 in the stress test.

### Percentile of ROI-positive peers' spend used as the token cap

- **Value used:** 75%
- **Origin:** Our rule of thumb
- **Used in:** Token caps, the ceiling per active person, above-norm spend
- **Why:** Generous enough that most heavy-but-productive users sit under it.

### Smallest peer group that is compared on its own

- **Value used:** 8 people
- **Origin:** Our method choice (tested)
- **Used in:** Peer norms, caps and control groups
- **Why:** Below this a group falls back to its whole department.
- **Reference:** [Stress tests (docs/robustness.md)](https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/robustness.md), read 2026-10-18. Results of re-running the method on companies with a known true effect.

### Smallest group ever shown

- **Value used:** 10 people
- **Origin:** Our method choice (tested)
- **Used in:** Every list, action and chart that groups people
- **Why:** So no figure points at one person. Smaller groups are merged and then hidden.

### Monthly spend jump that raises a drift alert

- **Value used:** 15% and at least $500
- **Origin:** Our rule of thumb
- **Used in:** The drift alerts on spend over time
- **Why:** Large enough to ignore ordinary variation.

### Levels never capped below the department cap

- **Value used:** intern, junior
- **Origin:** Our method choice (tested)
- **Used in:** Token caps by level
- **Why:** Dollar ROI depends on hourly rate, so a peer norm would understate what learners need. Two studies also found less experienced people gain more.
- **Reference:** [Brynjolfsson, Li, Raymond (2023)](https://www.nber.org/papers/w31161), read 2026-10-18. Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal impact.
- **Reference:** [Cui, Demirer, Jaffe, Musolff, Peng, Salz (2025)](https://papers.ssrn.com/abstract=4945566), read 2026-10-18. 26.08% increase in completed tasks, standard error 10.3%. Less experienced developers adopted more and gained more.


## Published numbers used

### Range of published effects on output

- **Value used:** 12.2% to 26.1% (median 19.0%)
- **Origin:** Taken from a published study
- **Used in:** The Evidence tab, the comparison with your estimate, the what-if scenarios
- **Why:** The smallest and largest output effects among the four studies that measure output.
- **Caveat:** These studies follow volunteers and early adopters. A company-wide estimate is expected to be lower.
- **Reference:** [Dell'Acqua et al. (2023)](https://www.bcg.com/publications/2023/how-people-create-and-destroy-value-with-gen-ai), read 2026-10-18. Inside the AI frontier: 12.2% more of the task completed, 25.1% faster, higher quality (BCG's write-up says 40% higher). Outside the frontier, performance was 23% lower than the control group (BCG).
- **Reference:** [Brynjolfsson, Li, Raymond (2023)](https://www.nber.org/papers/w31161), read 2026-10-18. Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal impact.
- **Reference:** [Murphy-Hill, Butler, Savelieva (2026)](https://arxiv.org/abs/2607.01418), read 2026-10-18. Adopters merged roughly 24% more pull requests than they would have otherwise; the lift persisted across the four-month window.
- **Reference:** [Cui, Demirer, Jaffe, Musolff, Peng, Salz (2025)](https://papers.ssrn.com/abstract=4945566), read 2026-10-18. 26.08% increase in completed tasks, standard error 10.3%. Less experienced developers adopted more and gained more.

### Developers' expected and believed speedup against the measured result

- **Value used:** expected 24% faster, believed 20% faster, measured 19% slower
- **Origin:** Taken from a published study
- **Used in:** The perception-gap check
- **Why:** The reason the tool measures output instead of asking people.
- **Caveat:** One study, early-2025 tools.
- **Reference:** [Becker, Rush, Barnes, Rein (2025)](https://arxiv.org/abs/2507.09089), read 2026-10-18. Allowing AI increased completion time by 19%. Developers had predicted a 24% speedup and, afterwards, believed they had been 20% faster.

### Gain for novice and low-skilled workers

- **Value used:** 34% (experienced workers: minimal impact)
- **Origin:** Taken from a published study
- **Used in:** The calibration of the demo company by level
- **Why:** Used to set the intern lift multiplier.
- **Reference:** [Brynjolfsson, Li, Raymond (2023)](https://www.nber.org/papers/w31161), read 2026-10-18. Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal impact.

### Gain for power and steady users in the demo company (mid-level)

- **Value used:** 24% and 14%
- **Origin:** Taken from a published study
- **Used in:** The synthetic company's true effect
- **Why:** Chosen inside the published adopter range so the demo reflects what studies found.
- **Caveat:** The range is published; the two specific values are our choice within it.
- **Reference:** [Dell'Acqua et al. (2023)](https://www.bcg.com/publications/2023/how-people-create-and-destroy-value-with-gen-ai), read 2026-10-18. Inside the AI frontier: 12.2% more of the task completed, 25.1% faster, higher quality (BCG's write-up says 40% higher). Outside the frontier, performance was 23% lower than the control group (BCG).
- **Reference:** [Brynjolfsson, Li, Raymond (2023)](https://www.nber.org/papers/w31161), read 2026-10-18. Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal impact.
- **Reference:** [Murphy-Hill, Butler, Savelieva (2026)](https://arxiv.org/abs/2607.01418), read 2026-10-18. Adopters merged roughly 24% more pull requests than they would have otherwise; the lift persisted across the four-month window.
- **Reference:** [Cui, Demirer, Jaffe, Musolff, Peng, Salz (2025)](https://papers.ssrn.com/abstract=4945566), read 2026-10-18. 26.08% increase in completed tasks, standard error 10.3%. Less experienced developers adopted more and gained more.
- **Reference:** [Evidence and calibration (docs/evidence.md)](https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/evidence.md), read 2026-10-18. What was read in each study, and how the demo company was calibrated.

### How much of the gain each level gets

- **Value used:** intern 1.45x, junior 1.3x, mid 1x, senior 0.7x
- **Origin:** Taken from a published study
- **Used in:** The synthetic company's true effect by level
- **Why:** Set so a power-user intern gains about 35% (the novice figure) and a senior about 17%.
- **Caveat:** The direction is published; the exact multipliers are ours. 'Minimal impact' for experienced agents was read modestly for software.
- **Reference:** [Brynjolfsson, Li, Raymond (2023)](https://www.nber.org/papers/w31161), read 2026-10-18. Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal impact.
- **Reference:** [Cui, Demirer, Jaffe, Musolff, Peng, Salz (2025)](https://papers.ssrn.com/abstract=4945566), read 2026-10-18. 26.08% increase in completed tasks, standard error 10.3%. Less experienced developers adopted more and gained more.
- **Reference:** [Evidence and calibration (docs/evidence.md)](https://github.com/vishalbanwari26/ai-ledger/blob/main/docs/evidence.md), read 2026-10-18. What was read in each study, and how the demo company was calibrated.


## The demo company

### Seat price per person a month

- **Value used:** Engineering $60, Sales $40 (others as Sales)
- **Origin:** Invented for the demo company
- **Used in:** Cost, unused-seat savings, every policy
- **Why:** $40 is close to a Copilot Pro+ seat or a Claude Team premium-seat range; $60 for engineers assumes a coding assistant plus a chat seat.
- **Caveat:** The $60 sum is ours; Copilot Business and Enterprise prices were not listed.
- **Reference:** [GitHub Copilot plans](https://github.com/features/copilot/plans), read 2026-10-18. Copilot Pro $10 a month, Pro+ $39, Max $100. Prices for Business and Enterprise are not listed on the page.
- **Reference:** [Claude plans and pricing](https://claude.com/pricing), read 2026-10-18. Team plan standard seat $20 a month billed annually ($25 monthly), premium seat $100 ($125 monthly). Enterprise: $20 per seat a month billed annually with a 20-seat minimum, usage charged on top at API rates.

### Hours per unit and hourly rates by department

- **Value used:** Engineering 3 h at $85; Support 0.5 h at $38; Sales 4 h at $70; Marketing 3.5 h at $55; Finance 5 h at $62; Legal 2.5 h at $120
- **Origin:** Invented for the demo company
- **Used in:** Value per unit of output
- **Why:** Invented to look plausible. Replace by uploading your data or on the Your value tab.

### Company-wide output growth a month

- **Value used:** 2.5%
- **Origin:** Invented for the demo company
- **Used in:** The busy-season effect the control group removes
- **Why:** Built in so a naive before-and-after check would credit AI with growth that was not AI.

### Output, token use and pay by level

- **Value used:** intern output 0.55x, pay 0.45x, junior output 0.8x, pay 0.7x, mid output 1x, pay 1x, senior output 1.1x, pay 1.4x
- **Origin:** Invented for the demo company
- **Used in:** The synthetic company
- **Why:** Invented.

### Headcount, usage mix and token multipliers by department

- **Value used:** Engineering 640, Support 440, Sales 360, Marketing 200, Finance 180, Legal 80
- **Origin:** Invented for the demo company
- **Used in:** The synthetic company
- **Why:** Invented to give a spread of behaviours.
