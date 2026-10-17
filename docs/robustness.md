# Where the analysis holds and where it breaks

Reproduce: `.venv/bin/python tools/stress.py` and `.venv/bin/python tools/policy_sensitivity.py`.
Each scenario is 12 random companies (about 1,900 people). The generator knows the true effect of AI for everyone,
so the estimates can be scored. "Coverage" is how often the true department ROI falls inside the stated 95% range
(it should be near 95%). "Bias" is estimated minus true company-wide effect, in points of output.

## What the stress test found and what we changed

| Weakness found | Before | After the fix |
|---|---|---|
| Large company-wide trend (10% a month) inflated the AI effect, because the control group was subtracted additively but effects multiply | bias +1.9 points, value overstated 29%, coverage 58% | ratio form: bias +0.3 points, value +6%, coverage 96% |
| Self-selection: adopters would have grown faster anyway (+1% a month) | bias +2.0 points, value +25%, coverage 50% | pre-rollout parallel-trends check removes the gap: bias 0.0, value -2%, coverage 99% |
| Self-selection, strong (+2% a month) | bias +3.8 points, value +51%, coverage 14% | bias -0.1 points, value -3%, coverage 94% |
| "Only adjust if significant" gate missed small selection effects (the check is low-powered) | gap of 0.45% a month undetected | point estimate always applied, its uncertainty added to the ranges |
| Pay-per-use winning depended on a number we invented (1.6x list price) | no way to see it | break-even price shown (about 2.4x); slider; the winner flips to "variable by role" above it |

## Weak spots that remain (read these before trusting a number)

- **Noisy output data.** At 15% monthly noise, the correct sign of a department's ROI is found 74% of the time and
  the ranking of departments degrades (rank correlation 0.83). At 25% noise it is 64% and 0.54; at 40% it is 60%
  and 0.35. The ranges stay honest (coverage 97-99%), but they become wide, and most departments read "uncertain".
  If your outcome metric is noisy, the tool will say so rather than guess.
- **Small companies.** At about 95 people, department ROI sign is right 69% of the time and control groups fall
  back to company-wide pooling. Use company-level numbers, not department splits.
- **Seats with high spend and no matching gain** are found with about 0.67 precision and 0.75-0.8 recall in the default
  setting, and precision falls to about 0.45 under heavy noise. Treat these as a list of groups to talk to,
  never as a verdict. Unused seats are reliable (precision 1.00 in every scenario) because they come from usage,
  not from noisy output.
- **A window of 2 months is unsafe**: the median no longer protects against a month of leave, and the effect is
  overstated by about 2.6 points. The app uses 3. With only 1 pre-rollout month the selection check cannot run.
- **Differences that begin at rollout** (for example, the most motivated people adopt first and also start a new
  project that month) cannot be separated from the AI effect by any check on pre-rollout data.
- **Policy ranking depends on assumptions, not data:** the price of pay per use, how much people ration metered
  use, how much seat cost can really be cancelled, and elasticity. Across all noise and size scenarios the same
  policy won, which shows the ranking is stable to the data and sensitive to those assumptions. The break-even price is
  the number to check against a real vendor quote.
- **Value is time saved times hourly rate, times a realization share.** At a 20% realization share, no policy has a
  positive net. Each department's "break-even credit" shows how much of the estimated gain must be real.
- The synthetic company was built with the same structure the method assumes (staggered rollout, a pre-period, a
  never-adopting control group). Real data may violate that. The scores above show the method works when its assumptions
  hold and degrades in the ways listed when they do not.
