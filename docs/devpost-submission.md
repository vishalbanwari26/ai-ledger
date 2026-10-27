# Devpost submission text

Copy each section into the matching Devpost field. Edit anything that does not match what you saw.
Placeholders in [square brackets] need your own input. Numbers are from the default demo company on 27 October 2026.

## Project name
AI Ledger

## Tagline
Is your AI spend paying off? It finds the unused seats and shows its working.

## Track
Best Apps and Agents

## Inspiration
Companies now pay for AI seats and tokens for thousands of people. Almost nobody can say if it pays off. The usual answers are
a survey ("it saves me 20%") or a before-and-after chart. Both are easy to get wrong. In a randomized trial, experienced
developers believed AI made them 20% faster while the measurement showed 19% slower. And output rises in a busy season for
people who never used AI at all.

## What it does
AI Ledger audits what a company spends on AI. It joins cost (seats, tokens) with output data, and it does four things.

- **Finds money that can be recovered.** In the demo company, 454 seats are not in use: $16,080 a month. Another 201 seats have
  high spend without matching output, worth up to $4,760 more. It never names or ranks a person. It reports groups, and it
  suggests asking the team and trying training before any change.
- **Estimates the real effect of AI.** People who did not adopt are the control group. In the demo, output rose 15.0% for
  people using AI and 5.9% for people who never did, so the AI effect is 8.6%, with a 95% range. It also checks that adopters
  were not already pulling ahead before rollout.
- **Says what it cannot tell.** Return is $1.32 per dollar, but the range is $0.99 to $1.67, so the page says not proven.
  Only three of six departments are clearly positive.
- **Simulates four budget policies** and ranks them by net dollars and bill risk. Pay per use nets the most but only wins below
  a list price of 2.4 times the seat rate. The break-even price is shown, because that one assumption can change the winner.

You can define what a unit of output is worth, name the unit, count several metrics towards output, measure speed (time to
finish a task) instead of volume, and change the tool's rules of thumb. Every value has a source or is labelled an assumption.
A Nemotron analyst answers questions in plain English, and every answer lists the tool calls behind it. The whole app runs in the browser, with no server.

## How we built it
- **NVIDIA Nemotron 3 Ultra (550B) on Nebius Token Factory** is the analyst. It is a tool-calling agent with eleven tools
  (summary, waste, actions, policies, evidence, value definition and others). The tools run the same maths as the dashboard.
  The model never sees raw rows, so it cannot invent a figure that is not in a tool result.
- **NVIDIA Nemotron 3.5 Lightning** writes the plain-English summary. A smaller model is enough for a routine task, and the
  tool applies the same advice to its users: route routine work to a cheaper model.
- **Nebius Token Factory** serves both models through its OpenAI-compatible API, so the standard `openai` client is all the
  app needs. The app lists the models at start-up and picks the largest and smallest Nemotron by name.
- **No server.** The demo is a static site on GitHub Pages. The analysis is plain Python, compiled to WebAssembly (Pyodide) and run
  in a Web Worker in the browser. Live questions call Token Factory directly from the page with the visitor's own key, which
  stays in their browser. Without a key, visitors read real answers recorded from Nemotron 3 Ultra, clearly labelled.
  A server build (FastAPI) is included and runs the same code; it can be deployed to a Nebius Serverless Endpoint with
  `deploy/wizard.sh`, but the hosted demo does not use one.
- Python (shared between a FastAPI server and the browser), Pyodide, plain SVG for the charts, no front-end framework.

In a test on 27 October, a tool-calling answer from Ultra took about 5 seconds, and the summary from Lightning took about 8.

## Challenges
- **A Python app with no server.** The analysis is about 3,000 lines of pure Python. We split the server code from the logic, then ran the
  logic in the browser with Pyodide in a Web Worker, so the page never freezes. A test checks that the browser engine gives exactly the
  same answers as the server, route by route, and that it imports with no server libraries.
- **Separating AI from the busy season.** A first version subtracted the control group additively. A stress test on companies
  with a known true effect showed it overstated the effect by 29% when the whole company was growing fast. We changed it to a
  ratio, added a pre-rollout check, and re-ran the tests: bias is now near zero and 94% to 100% of true values sit inside the
  stated ranges. docs/robustness.md lists where it still breaks (very noisy data, small companies).
- **A model that made things up.** On a loaded question ("who are the worst overspenders?") the model once called a tool that
  does not exist and then quoted figures that were not in any result. Prompt rules were not enough. We now rewrite questions
  about people into questions about groups before the model sees them, scan answers for blaming language, repair once, and
  fall back to a fixed summary. Tests cover it.
- **Honest sources.** Many dollar figures are assumptions. The tool says so, and a test fails if an assumption is added without
  a source note. We read nine published studies and left out figures we could not confirm from a primary source.

## Accomplishments
- Nothing in the tool names or ranks an individual, and a test guards it.
- 118 automated tests, including stress tests against companies with a known true effect.
- The page shows the working behind every number, and a Sources tab lists where each value comes from.

## What we learned
Measuring is cheaper than it looks if you keep a control group. Asking people is not. The hardest part was not the model. It was
saying plainly how sure the numbers are.

## What is next
Rollout dates by team instead of one shared baseline. Exclusions (contractors, new hires). Extra cost lines such as training.
Your own budget policies. Adapters for real vendor usage exports. The demo company is synthetic, and the tool needs real data
before it can be trusted on a real company.

## Built with
Python, Pyodide (WebAssembly), FastAPI, NVIDIA Nemotron 3 Ultra, NVIDIA Nemotron 3.5 Lightning, Nebius Token Factory, GitHub Pages

## Links
- Code: https://github.com/vishalbanwari26/ai-ledger (MIT licence)
- Demo: https://vishalbanwari.tech/ai-ledger/ (the Ask tab needs your own Token Factory key for live answers; recorded real answers are shown without one)
- Video: [paste the YouTube link]

## Did the project exist before the submission period?
No. The first commit is 17 October 2026, inside the submission period (26 August to 30 October).

## Feedback on Nebius Token Factory, Nebius AI Cloud and NVIDIA (required field)
Draft from what we observed while building. Delete anything you did not see yourself, and add your own notes after the deploy.

**What worked well**
- The OpenAI-compatible API needed only a base URL and a key. The standard `openai` client worked for chat, tool calling and
  `models.list()` with no custom code.
- Tool calling on Nemotron 3 Ultra was reliable with an eleven-tool schema. A tool-calling answer took about 5 seconds.
- Listing models at start-up meant we did not hard-code IDs. Both Nemotron tiers were found automatically.

**Friction and suggestions**
- Pricing is hard to read in code. Fetching Nebius's own price page without running JavaScript returned only the page title, so
  we could only find per-token prices on third-party listings. A plain page or a JSON price endpoint would help anyone who
  wants to build a cost calculator on Token Factory.
- Model IDs mix naming styles, for example `nvidia/Nemotron-3_5-Lightning` and `nvidia/Nemotron-3-Ultra-550b-a55b`
  (underscore and hyphen). We ranked models by parsing the ID. If the model list included parameter count and context length,
  that would be sturdier.
- When the prompt was loose, Nemotron 3 Ultra once called a tool that was not in the schema and then reported numbers that
  were not in any tool result. Stricter tool-name enforcement on the server side, or a flag to reject unknown tool calls,
  would help agent builders.
- Token Factory allows browser calls (CORS `*`, with the authorization header), which is what let us build a no-server demo where the
  visitor's own key never leaves their browser. Please keep that. A short doc note saying browser calls are supported would help.
- We did not deploy to a Serverless Endpoint for the demo, so we have no feedback on it. [Add if you try `deploy/wizard.sh`.]
- [Add anything else you hit: rate limits, error messages, docs gaps.]

## Teammates
[Add every teammate to the form, and ask them to accept the invitation.]
