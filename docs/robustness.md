# Where the analysis holds and where it breaks

Reproduce: `.venv/bin/python tools/stress.py` and `.venv/bin/python tools/policy_sensitivity.py`.
Each scenario is 12 random companies (about 1,900 people). The generator knows the true effect of AI for everyone,
so the estimates can be scored. "Coverage" is how often the true department ROI falls inside the stated 95% range
(it should be near 95%). "Bias" is estimated minus true company-wide effect, in points of output.
The demo company is calibrated to published findings (see `docs/evidence.md`); these results are for that company.

## Current results

| Scenario | Bias (points) | Coverage | Right sign of dept ROI | Dept ranking (rank corr.) | High-spend flag precision / recall |
|---|---|---|---|---|---|
| Baseline | -0.1 | 99% | 86% | 0.95 | 0.78 / 0.77 |
| Company trend 0% a month | -0.3 | 96% | 85% | 0.96 | 0.77 / 0.78 |
| Company trend 10% a month | +0.1 | 94% | 82% | 0.93 | 0.78 / 0.72 |
| Adopters were ahead before rollout, +1% a month | -0.2 | 97% | 85% | 0.91 | 0.77 / 0.77 |
| Adopters ahead, +2% a month | -0.3 | 96% | 78% | 0.83 | 0.76 / 0.75 |
| Adopters behind, -1% a month | 0.0 | 100% | 89% | 0.97 | 0.78 / 0.77 |
| Output noise 3% | -0.2 | 97% | 92% | 0.96 | 0.88 / 0.87 |
| Output noise 15% | 0.0 | 100% | 78% | 0.90 | 0.61 / 0.62 |
| Output noise 25% | +0.3 | 100% | 65% | 0.62 | 0.52 / 0.53 |
| Output noise 40% | +1.1 | 99% | 60% | 0.46 | 0.47 / 0.47 |
| 95 people | +0.5 | 100% | 68% | 0.68 | 0.84 / 0.67 |
| 285 people | -0.2 | 97% | 69% | 0.80 | 0.78 / 0.66 |
| No part-timers, leave or new hires | -0.1 | 94% | 86% | 0.96 | 0.78 / 0.83 |
| Only 1 pre-rollout month | -0.4 | 92% | 86% | 0.94 | 0.73 / 0.76 |
| Window of 2 months (unsafe) | +2.9 | 69% | 72% | 0.78 | 0.65 / 0.49 |

Unused seats are flagged with precision 1.00 in every scenario, because they come from usage and not from noisy output.
The same budget policy won on net dollars (pay per use) and variable by role beat the status quo in all 18 scenarios,
12 of 12 seeds each, which shows the policy ranking is stable to the data and sensitive to the pricing assumptions below.

## What the first stress test found and what we changed

These "before" figures come from the first stress test, run on an earlier, uncalibrated version of the demo company
before the fixes; they cannot be reproduced with today's code, which is why the table above is the current result.

| Weakness found | Before | After the fix |
|---|---|---|
| Large company-wide trend (10% a month) inflated the AI effect, because the control group was subtracted additively but effects multiply | bias +1.9 points, value overstated 29%, coverage 58% | ratio form: bias about 0, coverage 94% or better |
| Self-selection: adopters would have grown faster anyway (+1% a month) | bias +2.0 points, value +25%, coverage 50% | pre-rollout parallel-trends check removes the gap: bias about 0, coverage 97% |
| Self-selection, strong (+2% a month) | bias +3.8 points, value +51%, coverage 14% | bias -0.3 points, coverage 96% |
| "Only adjust if significant" gate missed small selection effects (the check is low-powered) | gap of 0.45% a month undetected | point estimate always applied, its uncertainty added to the ranges |
| Pay-per-use winning depended on a number we invented (1.6x list price) | no way to see it | break-even price shown (about 2.4x); slider; the winner flips to "variable by role" above it |

## Weak spots that remain (read these before trusting a number)

- **Noisy output data.** At 15% monthly noise, the correct sign of a department's ROI is found 78% of the time. At 25% it
  is 65% and department ranking falls to 0.62; at 40%, 60% and 0.46. The ranges stay honest (coverage 99-100%), but they
  become wide, and most departments read "uncertain". If your outcome metric is noisy, the tool says so rather than guess.
- **Small companies.** At 95 to 285 people, department ROI sign is right 68-69% of the time and control groups fall back
  to company-wide pooling. Use company-level numbers, not department splits.
- **Seats with high spend and no matching gain** are found with about 0.78 precision and 0.77 recall in the default
  setting, and both fall to about 0.5 under heavy noise. Treat these as a list of groups to talk to, never a verdict.
- **A window of 2 months is unsafe**: the median no longer protects against a month of leave, and the effect is overstated
  by about 2.9 points. The app uses 3. With only 1 pre-rollout month the selection check cannot run.
- **Differences that begin at rollout** (for example, the most motivated people adopt first and also start a new project
  that month) cannot be separated from the AI effect by any check on pre-rollout data.
- **Policy ranking depends on assumptions, not data:** the price of pay per use, how much people ration metered use, how
  much seat cost can really be cancelled, and elasticity. In the default company pay per use is best below a list price of
  about 2.36x the seat-plan rate, and above it variable by role is best. The same flip happens if people ration metered
  use by somewhere between 20% and 40% (it flips at 40% in the sensitivity run). The break-even price is the number to check against a real vendor quote.
- **Value is time saved times hourly rate, times a realization share.** At a 20% realization share, no policy has a
  positive net. Each department's "break-even credit" shows how much of the estimated gain must be real.
- The synthetic company was built with the same structure the method assumes (staggered rollout, a pre-period, a
  never-adopting control group). Real data may violate that. The scores above show the method works when its assumptions
  hold and degrades in the ways listed when they do not.

## Defending the numbers: "isn't this all subjective?"

Partly. The tool does not hide it. Every number is one of four kinds, shown on the page under "How much of this is opinion?":

- **Measured:** seats, token spend, sessions, output. Counted from your data.
- **Estimated:** the AI effect and department ROI, with 95% ranges.
- **Assumed:** realization, elasticity, pay-per-use price, seat savings, routing share. Sliders.
- **Judgement:** what counts as "high" spend compared with peers. A choice, shown so you can disagree.

Then each decision is re-run in 180 combinations of the assumptions. In the default company, two hold in all of them
(reassigning unused seats; variable by role beating the status quo on net dollars). "Pay per use is best" holds in 75%.
Company-wide ROI above zero holds in 60%. Legal's ROI is positive in every scenario, Support's in 80%, Engineering,
Marketing and Sales in 60%, and Finance's in 40%. Act on what holds. For the rest, get the missing number (a vendor quote,
a pilot).

"Reassigning unused seats raises net value" is true by construction, because a seat with no usage produces no AI value.
It is robust, but it is not a finding about the people in those seats. Whether to reassign is a conversation with the team.

### "A junior might need more tokens than the cap allows"

Correct, and the first version got this wrong. Caps came from what ROI-positive peers spend. Dollar ROI depends on
hourly rate, so juniors only looked ROI-positive when they spent little, which made their cap circular. Now interns and
juniors are never capped below the department-wide cap, and the page labels all caps as peer norms (what colleagues
spend), not need (what the work requires). Two published studies also found that less experienced people gain more from AI,
which points the same way. What the tool still cannot do is tell a junior who iterates more because they are learning from
one who is stuck on a poor workflow. That takes a conversation, which is why the action list says "ask the team first, try
training before any cap".
