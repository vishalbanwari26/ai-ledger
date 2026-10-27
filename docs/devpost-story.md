## Inspiration

Companies now pay for AI seats and tokens for thousands of people. Almost nobody can say whether that money pays off.
The usual answers are a survey ("it saves me 20%") or a before-and-after chart. Both are easy to get wrong.

In a randomized trial, experienced developers believed AI made them about 20% faster. The measured result was 19% slower.
Output also rises in a busy season for people who never used AI at all, so a simple before-and-after comparison credits AI
with growth it did not cause.

I wanted a tool that asks one question with a fair comparison: did the people who used AI gain more than the people who did not?

## What it does

AI Ledger joins what a company spends on AI (seats and tokens) with output data, and does four things:

- **Finds money that can be recovered.** In the demo company, 454 seats are unused, worth about \$16,080 a month. Another
  201 seats carry high spend without matching output. The tool reports groups, never individuals.
- **Estimates the real effect of AI.** People who did not adopt act as the control group. The effect is a ratio, not a
  difference:

  $$
  \hat{e} = \frac{1 + g_{\text{users}}}{1 + g_{\text{control}}} - 1
  $$

  In the demo, output rose 15.0% for users and 5.9% for non-users, so $\hat{e} = 1.150 / 1.059 - 1 \approx 8.6\%$. A pre-rollout
  check looks for adopters who were already pulling ahead before they started.
- **Says what it cannot tell.** Return is $\text{return} = \text{value} / \text{cost}$. In the demo it is \$1.32 per dollar,
  but the 95% range is \$0.99 to \$1.67, so the page says *not proven*. A range that crosses break-even is reported as
  uncertain, not as a win.
- **Compares budget policies.** It simulates four policies (fixed seats, pay per use, variable by role and a hybrid) and
  ranks them by net dollars and bill risk. Pay per use wins only below a list price of about 2.4 times the seat rate. That
  price is shown, because one assumption can change the winner.

Users can define what one unit of output is worth, name the unit, weight several metrics, measure speed (time to finish a
task) instead of volume, and edit the tool's rules of thumb. Every value either has a source or is labelled an assumption.
A Nemotron analyst answers questions in plain English, and each answer lists the tool calls behind it.

## How we built it

**The analyst.** NVIDIA Nemotron 3 Ultra (550B) runs on Nebius Token Factory as a tool-calling agent with eleven tools:
summary, waste, actions, policies, evidence and others. The tools run the same code as the dashboard. The model never sees
raw rows, so every figure it quotes comes from a tool result. NVIDIA Nemotron 3.5 Lightning writes the plain-English
summary. The app lists the models at start-up and picks the largest and smallest Nemotron by name.

**The core.** About 2,900 lines of plain Python hold the analysis. A shared service layer is used by two front ends: a
FastAPI server, and the browser itself.

**No server.** The demo is a static site on GitHub Pages. The Python is compiled to WebAssembly with Pyodide and runs in a
Web Worker, so the page never freezes. Live questions call Token Factory from the page with the visitor's own key, which
stays in their browser. Without a key, visitors see real answers recorded from Nemotron 3 Ultra, labelled as such.

**Checks.** 126 automated tests cover the engine, the server, the browser build, the blame guard and the sources.

## Challenges we ran into

**Running Python with no server.** The logic had to behave the same in both places. We split the server code from the
analysis, then ran the analysis in Pyodide. A test checks that the browser engine gives the same answers as the server,
route by route, and that it imports with no server libraries.

**A method that overstated the effect.** The first version subtracted the control group's growth. A stress test on
companies with a known true effect showed it overstated the effect by 29% when the whole company was growing fast. Changing
to the ratio above, and adding the pre-rollout check, brought the bias close to zero.

**A model that invented figures.** On one loaded question, "who are the worst overspenders?", the model called a tool that
does not exist, then quoted numbers that were in no result. Prompt rules did not fix it. Now questions about people are
rewritten as questions about groups before the model sees them. Answers are scanned for blaming language, repaired once if
needed, and replaced by a fixed summary if the repair fails.

**Honest sources.** Many dollar figures are assumptions. The tool says so. A test fails if an assumption is added without a
source note. We read nine published studies and left out any figure we could not confirm from a primary source.

## Accomplishments that we're proud of

- Nothing in the tool names or ranks an individual, and a test guards that rule.
- Across synthetic companies with a known true effect, 94% to 100% of the stated ranges contain the true value. We keep a
  list of where it still breaks: very noisy data and small companies.
- The whole analysis runs in the browser, with no server, and the same engine powers the server build.
- Every number on the page links to its working, and a Sources tab lists where each value comes from.

## What we learned

A control group makes measurement much cheaper than it looks. Asking people is much more expensive than it looks. The hardest
part was not the model. It was stating plainly how sure the numbers are, and making the page show that without burying the
answer.

## What's next for AI Ledger

Rollout dates by team instead of one shared baseline. Exclusions for contractors and new hires. Extra cost lines such as
training. Adapters for real vendor usage exports. The demo company is synthetic, so the tool needs real data before anyone
should trust it on a real company.
