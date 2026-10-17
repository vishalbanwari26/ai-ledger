# Demo video script (target 2:50, limit 3:00)

Record the browser at 1440 wide, dark mode, default synthetic company, privacy mode (no LEDGER_ADMIN).
Speak plainly, no reading from the page. Check every number on screen right before recording; moving a slider changes them.

## 0:00 to 0:20  The problem
(Screen: top of the dashboard, the red number.)
"Companies pay for AI seats and tokens for thousands of people, and almost nobody can say whether it pays off.
This is AI Ledger. For this 1,900 person company it found $21,800 a month of spend that returns nothing.
That is $262,000 a year."

## 0:20 to 0:50  Where the money goes
(Scroll to the waste table.)
"454 seats are idle. Under three sessions a month. We only count the share of a seat you can really cancel,
because contracts have minimums. 244 more people spend far above peers of the same role and level, with negative return.
Same level matters: an intern working on a small feature is not compared with a senior.
Engineering carries the most, $8,800 a month."

## 0:50 to 1:15  Act on it
(Scroll to the actions table. Tick two actions.)
"Every finding becomes an action with a reason. I approve two, it shows $4,000 a month, and I download the list.
In privacy mode, groups under ten people are hidden and nobody is named."

## 1:15 to 1:50  Is the return real?
(Scroll to the control group card.)
"Here is why you can trust the return. Output rose 13 percent for people using AI, but it also rose 6 percent for people
who never touched it, a busy season. A plain before and after would credit AI with all 13. We subtract the control group
and get 7 percent."
(Scroll to the department table.)
"Every ROI has a range. Marketing and Sales say uncertain: the range includes zero, so we say review, not cut."

## 1:50 to 2:20  The budget fix
(Scroll to the policies table.)
"Four budget policies on this data, ranked on net dollars and bill risk, not the ROI ratio, which rises whenever you
spend less. Pay per use has the highest net, but its bill can rise 57 percent if everyone spends at their peak month.
Variable by role keeps the risk near 13 percent. That depends on stated assumptions, and each policy lists them."
(Show the routing card.)
"Routing routine work to a smaller open model saves another $20,000 a month net of the quality risk."

## 2:20 to 2:50  Ask it, with proof
(Click the chip about departments that cannot be told apart from break-even, Ask, then open Evidence.)
"I can ask in plain English. This is Nemotron 3 Ultra on Nebius Token Factory. It never sees raw rows. It calls tools that
run the same maths, and here are the calls. The numbers in the answer are exactly what the tools returned."
(Scroll to the validation card for two seconds.)
"Because this company is synthetic, we know the truth, and the app scores itself: it finds every unused seat."

## Closing line (2:50)
"Two Nemotron sizes keep our own cost down. It runs on a Nebius Serverless Endpoint, models on Token Factory.
Upload your own CSV. MIT licensed on GitHub."

## Before you record
- Confirm the deployed URL works before saying it is deployed.
- Do one dry run of the Ask step; answers vary, so re-ask if thin.
- Do not show a terminal with the API key.

## Devpost feedback section (required): write from real experience
- What worked: OpenAI-compatible API, model list discovery, tool calling on the large Nemotron.
- Friction found: note real ones as you hit them (model IDs, rate limits, docs gaps).
