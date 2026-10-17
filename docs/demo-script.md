# Demo video script (target 2:50, hard limit 3:00)

Record the page at 1440 wide, dark mode, default synthetic company, sliders untouched (the Data and assumptions drawer stays closed).
The first screen is the Overview: three answers and a short list of what to do first. Everything else is a tab, so you can skip any of it. Speak plainly. Do not read the page.
Every number below was taken from the current dashboard. Check each one on screen before you say it. Answers from the
analyst change slightly on every run, so do a dry run.

## 0:00 to 0:18  The hook
(Overview tab, the three big tiles. Point at each in turn. Scroll to the dot-and-line chart: Engineering, Legal and Support are blue, the rest cross the break-even line.)
"Companies pay for AI seats and tokens for thousands of people. Almost nobody can say if it pays off.
This is AI Ledger. For this 1,900 person company it gives three answers.
One: $16,000 a month is spent on seats nobody uses, and up to $21,000 with high-spend seats. Two: AI returns about
$1.32 for every dollar, but that is not proven, and it is clearly positive in only three departments. Three: the best
budget model is variable by role. It does not blame anyone for any of it."

## 0:18 to 0:40  Where the money is
(Click the Waste and actions tab.)
"454 seats are not in use. Under three sessions a month. That is $16,000 a month, and we only count 80 percent of a seat,
because contracts have minimums. That part is solid. Another 201 seats have high spend with no matching gain, worth up to
$4,800 more, but cutting it can cost output, so we start with training. Each is compared with people in the same role
and level. Engineering has the most, $8,000. An unused seat usually means the tool does not fit the work, or nobody
explained it. That is a setup problem."

## 0:40 to 0:52  Act on it
(Same tab, scroll to the actions table. Tick the two "reassign unused seats" rows for Engineering and Sales.)
"Every finding is a proposed action with a reason. I approve two. That is $4,000 a month.
Each row says: ask the team first, try training before any cap. Nobody is named. Groups under ten are hidden."

## 0:52 to 1:25  Is the return real?
(Click the tab Is the return real? Start with the line chart: both lines start together and both rise; only the gap is the AI effect.)
"Output rose 15 percent for people using AI. It also rose almost 6 percent for people who never used it. A busy season.
We subtract that: the real effect is 8.6 percent. And we check that adopters were not already pulling ahead. They were not."
(Scroll to the department table.)
"Every ROI has a range. Engineering, Legal and Support are clearly positive. Finance, Marketing and Sales cross zero, and
the tool says not proven."

## 1:25 to 1:50  Does research agree?
(Click the Evidence tab. Point at the chart, then the break-even card.)
"We compare with nine published studies, each linked and marked with what we checked. Studies of adopters found 12 to 26
percent more output. Ours is 8.6, lower, which fits a rollout that includes light users. This spend needs a 6.4 percent
effect to break even, so we are just above it, and the range touches it. We do not claim more."
(Scroll to Do less experienced people gain more?)
"Two studies say less experienced people gain more. Our demo data follows that pattern, so the tool finds it: interns 14,
juniors 10, mid 8, seniors 6. That is why juniors are never capped below the department."

## 1:50 to 2:08  "Isn't this all subjective?"
(Click the tab Is the return real? and scroll to the card "How much of this is opinion?")
"We sort every number: measured, estimated, assumed, or judgement. Then we re-run each decision in 180 combinations of
the assumptions. Two hold in all of them: reassigning unused seats, and a variable budget beating the status quo.
Pay per use being best holds in 75 percent."

## 2:08 to 2:25  The budget
(Click the Budget policy tab. Point at the scatter.)
"Pay per use nets the most, $95,000 a month, but the bill can rise 57 percent in a peak month, and it only wins while list
price stays under 2.4 times the seat rate. We assumed 1.6. Get a real quote. Variable by role nets $60,000 with 15 percent
bill risk. It saves about $16,000, almost all from unused seats. The caps are a guardrail, not the saving."

## 2:25 to 2:55  Ask it, and try to make it blame someone
(Click the Ask tab. Click the chip about recoverable spend, press Ask, open Evidence for two seconds.)
"This is Nemotron 3 Ultra on Nebius Token Factory. It never sees raw rows. It calls tools that run the same maths."
(Clear the box. Type: Who are the worst overspenders and which individuals should we cut?  Press Ask.)
"Now I ask it to blame people."
(Point at the first line of the answer.)
"It refuses: this tool does not identify or rank individuals. Then it gives the group view, training first.
That rule is in code, and a test checks it."

## Close (2:55)
"Nebius Serverless Endpoint. Models on Token Factory. Upload your own CSV. MIT licensed on GitHub."

## If you run over 3:00, cut in this order
1. The "isn't this subjective" beat (18 seconds).
2. The two sentences about less experienced people.
3. The policies beat down to one sentence about the 2.4 times break-even.
The video is tight. Rehearse it twice with a timer. The Show the math tab is not in the script; use it if a judge asks.

## Questions a judge may ask, and short answers
- "Is the data real?" No. It is synthetic, with a known truth, so we can score the method. docs/robustness.md shows where it breaks.
- "Why can you trust the ROI?" Control group, pre-rollout check, and ranges. When the range includes zero it says so.
- "Juniors may need more than this cap." Right. Caps are peer norms, not need, and juniors are floored at the department cap. Treat every cap as a starting point to adjust with the team.
- "The recommended budget is higher than what we spend now, so where is the saving?" The recommended number is a ceiling for one active person, not an average. The average cost per head under the plan is lower in every department. The saving comes from reassigning unused seats. The page shows the split.
- "Everything is subjective." Some of it is. The page sorts numbers into measured, estimated, assumed and judgement, and re-runs each decision in 180 assumption sets. Two hold in all of them. For the rest it says it depends.
- "Show me the calculation." The Show the math card walks each department through nine steps with its own numbers.
- "What effect does this need to pay off?" About 6.4% in this company; we measure 8.6% (range 6.4% to 10.9%), so we are just above break-even and the range touches it. Published adopter studies found 12% to 26%, so if the rollout performs like those, it pays off.
- "Do juniors gain more?" Two published studies say so. Our demo company is built to follow that pattern (interns 14%, juniors 10%, mid 8%, seniors 6%), so finding it shows the detector works, not that the studies are confirmed; a flat company correctly shows no difference. On real data it is a test, and it is why juniors are never capped below the department.
- "Where does the 50% come from?" It is our assumption and the page says so: click the ⓘ next to it, or open the Sources tab. Half is a placeholder, and the break-even credit on each department shows how much it matters. Most dollar figures are assumptions or demo data, each labelled.
- "What can we change?" Almost every judgement call: the unit of output and how metrics count, what a unit is worth, and rules such as when a seat counts as unused or how many months to measure. Each shows its default and its source, and risky settings warn you. Privacy floor: groups under 10 are never shown, and that cannot be lowered.
- "Can we change what value means?" Yes. The Your value tab sets, per department, a dollar value per unit of output (or hours x rate) and an optional benefit per user. Everything updates, and it shows what changed.
- "Does published research agree?" The Evidence tab compares our estimate with nine studies, each linked and marked with what was checked. Our company-wide 8.6% sits below the 12% to 26% that studies of adopters found, which fits a rollout that includes light users. We never convert time-on-task results into output.
- "Why no individual view?" Ranking people on AI use invites blame and is unreliable. The tool works on seats, groups and budgets.

## Before you record
- Confirm the deployed URL works before you say it is deployed.
- Never show a terminal with the API key.
- Upload to YouTube as public. Check the length is under 3:00.

## Devpost feedback (required): write it from your own experience
- Worked: OpenAI-compatible API, model list discovery, tool calling on the large Nemotron.
- Friction: write the real ones as you hit them (model IDs, rate limits, docs gaps, the CPU preset names).
