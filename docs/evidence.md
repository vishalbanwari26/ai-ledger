# Published evidence, and what was checked

The Evidence tab compares this tool's company-wide AI effect with published studies. It is context, not calibration:
the studies measure different things in different settings, and nothing here changes the tool's estimate.
Numbers were read from the linked sources on 2026-10-18. The data lives in `ailedger/evidence.py`; tests check that
each figure matches what was read and that unconfirmed figures stay out.

## Studies used

| Study | What it measured | Result as reported | Checked how |
|---|---|---|---|
| [Murphy-Hill et al. 2026](https://arxiv.org/abs/2607.01418), Microsoft rollout of Claude Code and Copilot CLI | Merged pull requests, adopters vs a counterfactual, four months, tens of thousands of engineers | About 24% more merged PRs than they otherwise would have | Abstract. Method not read. |
| [Cui et al. 2025](https://papers.ssrn.com/abstract=4945566), three field experiments | Completed tasks, 4,867 developers at Microsoft, Accenture, a Fortune 100 firm | +26.08%, standard error 10.3% | Abstract. The 95% range we draw (5.9% to 46.3%) is our own, from the standard error. |
| [Brynjolfsson, Li, Raymond 2023](https://www.nber.org/papers/w31161), customer support | Issues resolved per hour, 5,179 agents | +14%; +34% for novices | Abstract. |
| Dell'Acqua et al. 2023, consultants ([BCG write-up](https://www.bcg.com/publications/2023/how-people-create-and-destroy-value-with-gen-ai)) | 758 consultants, GPT-4, tasks inside the "frontier" | 12.2% more of the task, 25.1% faster; quality +40% (BCG); outside the frontier, performance 23% lower (BCG) | 12.2% and 25.1% from the abstract as quoted in a search result; 40% and 23% from BCG's article. The paper itself could not be opened. |
| [Peng et al. 2023](https://arxiv.org/abs/2302.06590), Copilot | Time to write one HTTP server; 95 developers (35 per group finished) | 71.17 vs 160.89 minutes, 55.8% less time; 95% interval for the improvement 21% to 89% | Full text. |
| [Paradis et al. 2024](https://arxiv.org/abs/2410.12944), Google | Time on a task, 96 engineers | About 21% less; "confidence interval is large" | Abstract. |
| [Becker et al. 2025](https://arxiv.org/abs/2507.09089), METR | Time per task, 16 experienced developers, 246 tasks, early-2025 tools | 19% longer with AI; they forecast 24% faster and afterwards believed 20% faster | Abstract. |
| [Noy and Zhang 2023](https://economics.mit.edu/sites/default/files/inline-files/Noy_Zhang_1.pdf), writing | 444 professionals | Time down 0.8 standard deviations, quality up 0.4 | Abstract in the PDF. Shown in the table only, because standard deviations are not percentages. |
| [Humlum and Vestergaard](https://www.nber.org/papers/w33777), Denmark | Earnings and recorded hours, difference-in-differences | Precise nulls; effects over 2% ruled out | Abstract. Not an output measure, so not on the chart. |

## What was left out, and why

- **"40% less time" and "18% higher quality" for Noy and Zhang.** The abstract reports standard deviations.
- **"19 percentage points less likely to be correct"** for the consultants study. Could not be confirmed here; BCG's article gives a different measure (23% lower performance), which is what is shown.
- **A "3% of hours saved" figure for Denmark.** Only a secondary source; the abstract has no time-savings figure.
- **METR's 2026 follow-up.** Secondary sources say METR later called the early-2025 result out of date. METR's own pages were not found, so it is not quoted as fact.

## How the comparison works

Only studies that measure **output** (tasks, pull requests, issues per hour) are compared with the tool's effect, and
time-on-task results are never converted into output. A 55.8% cut in the time for one task is not 55.8% more output
over a month. The tool's company-wide estimate is expected to sit below volunteer or early-adopter studies, because it
includes light users. The realization share (how much extra output counts as money) applies after this comparison and
does not change it.

## Reproduce

Open each link and read the abstract. The unit tests (`tests/test_ledger.py`, "published evidence") fail if a figure
here drifts from the one recorded in the code.
