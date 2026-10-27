# Final checklist: deploy and submit

**Done:** the demo is live at https://vishalbanwari.tech/ai-ledger/ (static site on GitHub Pages, no server). To change it: edit,
run the tests, then `./tools/publish_site.sh`. Sections A to E below are for the optional server build on a Nebius Serverless Endpoint.

Nothing here has been run against a real Nebius account yet. Items marked CHECK are the ones most likely to need a tweak.

## A. Before deploying (5 minutes, all on your laptop)
- [ ] `cd ai-ledger && .venv/bin/pytest -q` shows all tests passing.
- [ ] `docker build -t ai-ledger:test .` succeeds.
- [ ] Start locally with the key set, click **Generate with Nemotron**, then ask one question. Both work.
- [ ] Repo is public and `LICENSE` (MIT) shows at the top of https://github.com/vishalbanwari26/ai-ledger.

## B. Accounts and keys
- [ ] Install and configure the Nebius CLI (`nebius profile create`).
- [ ] Create a new Token Factory key used only for the demo. Do not reuse the clusterdoctor key.
- [ ] Create a GitHub token with `write:packages`, log in: `echo "$GITHUB_PAT" | docker login ghcr.io -u vishalbanwari26 --password-stdin`.

## C. Deploy
```bash
cd /Users/vishalbanwari/Documents/GitHub/ai-ledger
IMAGE=ghcr.io/vishalbanwari26/ai-ledger:latest NEBIUS_API_KEY="paste-demo-key" ./deploy/deploy.sh
```
- [ ] After the first push, set the package `ai-ledger` to **public** in GitHub (Package settings), or Nebius cannot pull it.
- [ ] CHECK: if `--preset 2vcpu-8gb` is rejected, list valid presets for `cpu-d3` in the Nebius docs and edit `deploy/deploy.sh`.
- [ ] CHECK: if `--env` with a comma list fails, create the endpoint in the web console and add the two variables there.
- [ ] The script prints an HTTPS URL. Open it.

## D. Verify the deployed app (do all four)
- [ ] The dashboard loads and Overview shows `$16,080 a month` and `$1.32 back per $1`, and the Waste and actions tab shows `454` unused seats.
- [ ] **Generate with Nemotron** returns a brief.
- [ ] Ask "Who are the worst overspenders?" and confirm the answer starts "This tool does not identify or rank individuals".
- [ ] Open the URL in a private window. It works without any login (judges need this).

## E. Safety while it is public
- [ ] `LEDGER_LLM_PER_HOUR` caps model calls (120 by default). Lower it if you are worried about credits.
- [ ] Watch your Token Factory usage page once a day.
- [ ] After judging: `nebius ai endpoint delete --id <endpoint_ID>` and delete the demo key.

## F. Record and submit (Devpost)
- [ ] Record with `docs/demo-script.md`. Under 3:00. Upload to YouTube as **public**.
- [ ] Track: **Best Apps and Agents**.
- [ ] Project description: what it is, why (nobody can say if AI spend pays off), how it works (control group, tool-calling analyst).
- [ ] Say where Nemotron is used (large model answers, small model writes the brief) and that Token Factory serves both.
- [ ] Say what else on Nebius: Serverless Endpoint for the app.
- [ ] Demo URL, repo URL, video URL.
- [ ] Feedback on Nebius Token Factory, AI Cloud and NVIDIA models: write real notes.
- [ ] The repo is new for this hackathon, so no "existed before" note is needed. Check the rules page to be sure.
- [ ] Check the submission deadline on Devpost. It was not shown on the page I read.
- [ ] Submit at least a few hours early.
