# Demo video script (target 2:45, limit 3:00)

Record the browser at 1440 wide, dark mode, default synthetic company. Speak plainly, no reading from the page.
Check every number against the screen right before recording; they change if the sliders move.

## 0:00 to 0:20  The problem
(Screen: top of the dashboard, the red number.)
"Companies now pay for AI seats and tokens for thousands of people, and almost nobody can say whether it pays off.
This is AI Ledger. For this 1,900 person company it found $21,000 a month in spend that returns nothing.
That is $256,000 a year."

## 0:20 to 0:55  Where the money goes
(Scroll to the waste table.)
"316 seats are idle. Under three sessions a month. That is $13,900 of seat fees.
212 more people spend far above what colleagues in the same department spend, and their return is negative.
Engineering carries the most, $8,600 a month. Sales has 95 idle seats.
Idle and overspend are defined at the bottom of the card, so you can check the rule."

## 0:55 to 1:35  The fix: which budget model
(Scroll to the policies table.)
"The question managers ask is whether budgets should be fixed or variable. We simulate four policies on this data.
Pay per use has the highest net value, $124,000 a month, but if everyone spends at their peak month the bill
rises 27 percent. A fixed budget moves it by 4 percent, but gives up $41,000 of net value.
We rank on net dollars and bill risk, not on ROI, because ROI is a ratio and goes up whenever you simply spend less."
(Scroll to the per-department table.)
"By department: Engineering gets a fixed budget, Sales and Finance get a variable one with a cap."

## 1:35 to 2:20  Ask it, with proof
(Click the chip "Where is most of the waste, and what is the fastest fix?" and Ask.)
"Now I can ask in plain English. This runs Nemotron 3 Ultra on Nebius Token Factory.
The model never sees raw rows. It calls tools that run the same maths as the dashboard."
(Open the Evidence panel.)
"Here are the tool calls. The $1,950 and the department split in the answer are exactly what the tool returned.
That is how I know it did not make them up."
(Drag the realization slider to 20 percent, ask again.)
"Value is an estimate, so it is a slider. At 20 percent, the answer changes and the model follows."

## 2:20 to 2:45  How it is built
"Two Nemotron sizes. The large one answers questions with tool calls. A small one writes the executive brief,
so routine calls stay cheap. That is the same cost discipline the product tells customers to use.
The app runs on a Nebius Serverless Endpoint, models on Token Factory. Upload your own CSV and it works on your data.
The code is MIT licensed on GitHub."

## Before you record
- Confirm the deployed URL works and say it only if it does.
- Do one dry run of the Ask step; model answers vary, so re-ask if the answer is thin.
- Do not show the terminal with the API key.

## Devpost feedback section (required): notes to fill in from experience
- What worked: OpenAI-compatible API, model list discovery, tool calling on the large Nemotron.
- Friction found while building: write down real ones as you hit them (model IDs, rate limits, docs gaps).
