# Demo video script (target 2:50, hard limit 3:00)

Record the page at 1440 wide, dark mode, default synthetic company, sliders untouched (the Data and assumptions drawer stays closed).
The first screen is the Overview: three answers and a short list of what to do first. Everything else is a tab, so you can skip any of it. Speak plainly. Do not read the page.
Every number below was taken from the current dashboard. Check each one on screen before you say it. Answers from the
analyst change slightly on every run, so do a dry run.

## 0:00 to 0:18  The hook
(Overview tab, the three big tiles. Point at each in turn. Scroll to the dot-and-line chart: Legal is the only blue one, the rest cross the break-even line.)
"Companies pay for AI seats and tokens for thousands of people. Almost nobody can say if it pays off.
This is AI Ledger. For this 1,900 person company it gives three answers.
One: $16,000 a month is spent on seats nobody uses, and up to $21,000 with high-spend seats. Two: AI returns about $1.17 for every dollar, but that is not proven,
and only Legal is clearly positive. Three: the best budget model is variable by role.
It does not blame anyone for any of it. I will show how."

## 0:18 to 0:42  Where the money is
(Click the Waste and actions tab.)
"454 seats are not in use. Under three sessions a month. That is $16,000 a month, and we only count 80 percent of a
seat, because contracts have minimums. That part is solid. Another 245 seats have high spend with no matching gain,
worth up to $5,000 more, but cutting it can cost output, so we start with training. Each is compared with
people in the same role and level, so an intern is never measured against a senior. Engineering has the most, $8,000.
An unused seat usually means the tool does not fit the work, or nobody explained it. That is a setup problem."

## 0:42 to 0:55  Act on it
(Same tab, scroll to the actions table. Tick the first two rows.)
"Every finding is a proposed action with a reason. I approve two. That is $4,000 a month.
Each row says: ask the team first, try training before any cap. Nobody is named. Groups under ten are hidden."

## 0:55 to 1:30  Is the return real?
(Click the tab Is the return real? Start with the line chart: both lines start together and both rise; only the gap is the AI effect.)
"Output rose 13 percent for people using AI. It also rose almost 6 percent for people who never used it. A busy season.
We subtract that: the real effect is 7 percent. And we check that adopters were not already pulling ahead. They were not."
(Scroll to the department table.)
"Every ROI has a range. Only Legal is clearly positive. For the others the range includes zero, and the tool says uncertain."

## 1:30 to 1:58  "Isn't this all subjective?"
(Scroll to the card "How much of this is opinion?" in the same tab.)
"Fair question. So we sort every number: measured, estimated, assumed, or judgement.
Then we re-run each decision in 180 combinations of the assumptions. Two conclusions hold in all of them:
reassigning unused seats, and a variable budget beating the status quo. Pay per use being the best holds in 75 percent.
Most department returns depend on the assumptions, and the page says so."

## 1:58 to 2:18  The budget
(Click the Budget policy tab. Point at the scatter: pay per use is high but far to the right; variable by role is the recommended trade-off.)
"Pay per use nets the most, $75,000 a month, but the bill can rise 57 percent in a peak month,
and it only wins while list price stays under 2.4 times the seat rate. We assumed 1.6. Get a real quote.
Variable by role nets $39,000 with 17 percent bill risk. It saves about $16,000 a month, almost all from unused seats.
The caps are a guardrail, not the saving. Caps by level are peer norms, not need.
Juniors and interns are never set below the department cap, because they iterate more while learning."

## 2:18 to 2:32  Show the math
(Click the Show the math tab. Pick Engineering. Point at steps 3 and 4.)
"Every number is built from these steps. Engineering users grew 14.4 percent, the others 5.3. After removing the gap
that existed before rollout, the effect is 9.2 percent. Same formula, real numbers, no individuals."

## 2:32 to 2:58  Ask it, and try to make it blame someone
(Click the Ask tab. Click the chip about recoverable spend, press Ask, open Evidence for two seconds.)
"This is Nemotron 3 Ultra on Nebius Token Factory. It never sees raw rows. It calls tools that run the same maths."
(Clear the box. Type: Who are the worst overspenders and which individuals should we cut?  Press Ask.)
"Now I ask it to blame people."
(Point at the first line of the answer.)
"It refuses: this tool does not identify or rank individuals. Then it gives the group view, training first.
That rule is in code, and a test checks it."

## Close (2:58)
"Nebius Serverless Endpoint. Models on Token Factory. Upload your own CSV. MIT licensed on GitHub."

## If you run over 3:00, cut in this order
1. The "Show the math" beat (14 seconds).
2. The Evidence panel and the juniors-and-interns sentence.
3. The policies beat down to one sentence about the 2.4 times break-even.
The video is tight. Rehearse it twice with a timer.

## Questions a judge may ask, and short answers
- "Is the data real?" No. It is synthetic, with a known truth, so we can score the method. docs/robustness.md shows where it breaks.
- "Why can you trust the ROI?" Control group, pre-rollout check, and ranges. When the range includes zero it says so.
- "Juniors may need more than this cap." Right. Caps are peer norms, not need, and juniors are floored at the department cap. Treat every cap as a starting point to adjust with the team.
- "The recommended budget is higher than what we spend now, so where is the saving?" The recommended number is a ceiling for one active person, not an average. The average cost per head under the plan is lower in every department. The saving comes from reassigning unused seats. The page shows the split.
- "Everything is subjective." Some of it is. The page sorts numbers into measured, estimated, assumed and judgement, and re-runs each decision in 180 assumption sets. Two hold in all of them. For the rest it says it depends.
- "Show me the calculation." The Show the math card walks each department through nine steps with its own numbers.
- "What effect does this need to pay off?" About 6.4% in this company; we measure 7.1%, with a range that crosses it, so we say not proven. Published adopter studies found 12% to 26%, so if the rollout performs like those, it pays off.
- "Do juniors gain more?" Two published studies say so. Our demo data was built flat, so it shows no difference; on real data it is a test, and it is why juniors are never capped below the department.
- "Does published research agree?" The Evidence tab compares our estimate with nine studies, each linked and marked with what was checked. Our company-wide 7% sits below the 12% to 26% that studies of adopters found, which fits a rollout that includes light users. We never convert time-on-task results into output.
- "Why no individual view?" Ranking people on AI use invites blame and is unreliable. The tool works on seats, groups and budgets.

## Before you record
- Confirm the deployed URL works before you say it is deployed.
- Never show a terminal with the API key.
- Upload to YouTube as public. Check the length is under 3:00.

## Devpost feedback (required): write it from your own experience
- Worked: OpenAI-compatible API, model list discovery, tool calling on the large Nemotron.
- Friction: write the real ones as you hit them (model IDs, rate limits, docs gaps, the CPU preset names).
