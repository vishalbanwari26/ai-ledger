# Demo video script (target 2:50, hard limit 3:00)

Record the page at 1440 wide, dark mode, default synthetic company, sliders untouched. Speak plainly. Do not read the page.
Every number below was taken from the current dashboard. Check each one on screen before you say it. Answers from the
analyst change slightly on every run, so do a dry run.

## 0:00 to 0:20  The hook
(Top of the page, the red number.)
"Companies pay for AI seats and tokens for thousands of people. Almost nobody can say if it pays off.
This is AI Ledger. For this 1,900 person company it finds $22,000 a month that can be recovered. $265,000 a year.
It does not blame anyone for that. I will show you how."

## 0:20 to 0:50  Where the money is
(Scroll to the waste table.)
"454 seats are not in use. Under three sessions a month. That is $16,000 a month, and we only count 80 percent of a
seat, because contracts have minimums. Another 245 seats have high spend with no matching gain in output. We compare
each one with people in the same role and level, so an intern is never measured against a senior.
Engineering has the most, $9,000 a month. An unused seat usually means the tool does not fit the work, or nobody
explained it. That is a setup problem, not a people problem."

## 0:50 to 1:10  Act on it
(Scroll to the actions table. Tick the first two rows.)
"Every finding is a proposed action with a reason. I approve two. That is $4,000 a month.
Each row says: ask the team first, try training before any cap. Nobody is named anywhere. Groups under ten people are hidden.
I can download the list as a CSV."

## 1:10 to 1:50  Is the return real?
(Scroll to the control group card.)
"Now the harder question. Output rose 13 percent for people using AI. But it also rose almost 6 percent for people who
never used it. A busy season. We subtract that and the real effect is 7 percent.
We also check that adopters were not already pulling ahead before rollout. They were not. The gap is under half a percent."
(Scroll to the department table.)
"Every ROI has a range. Only Legal is clearly positive. For the other departments the range includes zero, and the tool
says uncertain. It does not guess. It also shows break-even credit: Engineering pays for itself if 43 percent of the
estimated gain is real."

## 1:50 to 2:25  The budget fix
(Scroll to the policies table.)
"Four budget policies on this data, ranked by net dollars and bill risk, not by the ROI ratio, which goes up whenever
you spend less. Pay per use has the highest net, $75,000 a month. But the bill can rise 57 percent in a peak month.
And it only wins while list price stays under 2.4 times the seat rate. We assumed 1.6. Get a real quote.
Variable by role nets $39,000 with 12 percent bill risk."
(Scroll to the routing card.)
"Moving routine work to a smaller open model saves about $20,000 a month, after a quality penalty."

## 2:25 to 2:55  Ask it, and try to make it blame someone
(Click the chip about recoverable spend, press Ask, then open Evidence.)
"I can ask in plain English. This is Nemotron 3 Ultra on Nebius Token Factory. It never sees raw rows. It calls tools that
run the same maths, and here are the calls."
(Clear the box. Type: Who are the worst overspenders and which individuals should we cut?  Press Ask.)
"Now I ask it to blame people."
(Wait for the answer. Point at the first line.)
"It refuses. It says this tool does not identify or rank individuals, and gives the group view with training first.
The refusal is in code, not just in the prompt, and a test checks it."

## Close (2:55)
"Runs on a Nebius Serverless Endpoint. Models on Token Factory. Upload your own CSV. MIT licensed on GitHub."

## If you run over 3:00, cut in this order
1. The routing card (about 8 seconds).
2. The break-even credit sentence.
3. The "I can download the list" sentence.

## Questions a judge may ask, and short answers
- "Is the data real?" No. It is synthetic, with a known truth, so we can score the method. docs/robustness.md shows where it breaks.
- "Why can you trust the ROI?" Control group, pre-rollout check, and ranges. When the range includes zero it says so.
- "Why no individual view?" Ranking people on AI use invites blame and is unreliable. The tool works on seats, groups and budgets.

## Before you record
- Confirm the deployed URL works before you say it is deployed.
- Never show a terminal with the API key.
- Upload to YouTube as public. Check the length is under 3:00.

## Devpost feedback (required): write it from your own experience
- Worked: OpenAI-compatible API, model list discovery, tool calling on the large Nemotron.
- Friction: write the real ones as you hit them (model IDs, rate limits, docs gaps, the CPU preset names).
