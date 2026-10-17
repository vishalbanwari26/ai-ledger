"""Published evidence on AI and productivity, and a plain comparison with this tool's own estimate.

Every number below was read from the source named in `verified` on 2026-10-18. Where a number could not be
confirmed from a primary source it is marked, and some figures people often quote are deliberately left out.
This is context for the tool's assumptions, not a calibration: the studies measure different things in
different settings (volunteers, one task, one firm, early tools), so a match proves little and a gap proves
less. Nothing here changes the tool's estimate.
"""
from __future__ import annotations

import statistics as st

VERIFIED_ON = "2026-10-18"

# metric: "output" = more work done (percent change, higher is better)
#         "time"   = change in time to finish a task (percent, negative means faster)
#         "sd"     = effect in standard deviations (not comparable on a percent axis)
#         "null"   = a precise zero on a different outcome
STUDIES: list[dict] = [
    dict(id="murphy-hill-2026", short="Microsoft rollout", authors="Murphy-Hill, Butler, Savelieva", year=2026,
         title="Adoption and Impact of Command-Line AI Coding Agents: A Study of Microsoft's Early 2026 Rollout of "
               "Claude Code and GitHub Copilot CLI",
         status="arXiv preprint, July 2026", url="https://arxiv.org/abs/2607.01418",
         design="Observational: adopters compared with an estimated counterfactual, one company, four months",
         setting="Software engineers, tens of thousands, at Microsoft", n="tens of thousands",
         measure="Merged pull requests", metric="output", value=24.0, lo=None, hi=None, ci_derived=False,
         reported="Adopters merged roughly 24% more pull requests than they would have otherwise; the lift persisted "
                  "across the four-month window.",
         caveats="A merged pull request is not the same as the value it delivers (the authors say so). One company, "
                 "four months. The closest match to this tool: a real rollout, staggered adoption.",
         verified="Abstract read on arXiv. Method and interval not read."),
    dict(id="cui-2025", short="Three field experiments", authors="Cui, Demirer, Jaffe, Musolff, Peng, Salz", year=2025,
         title="The Effects of Generative AI on High-Skilled Work: Evidence from Three Field Experiments with "
               "Software Developers",
         status="Management Science (accepted); SSRN working paper", url="https://papers.ssrn.com/abstract=4945566",
         design="Three randomized field experiments run inside Microsoft, Accenture and an anonymous Fortune 100 firm",
         setting="Software developers given or denied an AI code assistant", n="4,867 developers",
         measure="Completed tasks", metric="output", value=26.08, lo=26.08 - 1.96 * 10.3, hi=26.08 + 1.96 * 10.3,
         ci_derived=True,
         reported="26.08% increase in completed tasks, standard error 10.3%. Less experienced developers adopted more "
                  "and gained more.",
         caveats="Noisy: the standard error is large and results differ across the three experiments. The range shown "
                 "is our own estimate (point +/- 1.96 standard errors), not a figure printed in the abstract.",
         verified="Abstract read on SSRN and Microsoft Research pages. Range derived by us."),
    dict(id="brynjolfsson-2023", short="Customer support", authors="Brynjolfsson, Li, Raymond", year=2023,
         title="Generative AI at Work", status="NBER Working Paper 31161", url="https://www.nber.org/papers/w31161",
         design="Staggered rollout of an AI assistant to customer-support agents", setting="Customer support agents",
         n="5,179 agents", measure="Issues resolved per hour", metric="output", value=14.0, lo=None, hi=None,
         ci_derived=False,
         reported="Average productivity up 14%. Novice and low-skilled workers up 34%. Experienced workers saw minimal "
                  "impact.",
         caveats="Customer support, not software. Gains concentrated in less experienced workers.",
         verified="Abstract read on NBER."),
    dict(id="dellacqua-2023", short="Consultants (inside the frontier)", authors="Dell'Acqua et al.", year=2023,
         title="Navigating the Jagged Technological Frontier: Field Experimental Evidence of the Effects of AI on "
               "Knowledge Worker Productivity and Quality",
         status="Working paper; later published in Organization Science",
         url="https://www.bcg.com/publications/2023/how-people-create-and-destroy-value-with-gen-ai",
         design="Preregistered randomized experiment", setting="Consultants at Boston Consulting Group, GPT-4",
         n="758 consultants", measure="Share of the task completed", metric="output", value=12.2, lo=None, hi=None,
         ci_derived=False,
         reported="Inside the AI frontier: 12.2% more of the task completed, 25.1% faster, higher quality (BCG's write-up "
                  "says 40% higher). Outside the frontier, performance was 23% lower than the control group (BCG).",
         caveats="Designed tasks, not ongoing work. Large gains on tasks AI suits; worse results on a task it does not. "
                 "The size of the outside-the-frontier effect differs between sources, so only BCG's figure is shown.",
         verified="12.2% and 25.1% from the paper's abstract as quoted by a search result; 40% and 23% from BCG's own "
                  "article. The primary paper could not be opened (access blocked)."),
    dict(id="peng-2023", short="Copilot, one task", authors="Peng, Kalliamvakou, Cihon, Demirer", year=2023,
         title="The Impact of AI on Developer Productivity: Evidence from GitHub Copilot",
         status="arXiv preprint", url="https://arxiv.org/abs/2302.06590",
         design="Controlled experiment, one task (write an HTTP server in JavaScript)", setting="Recruited developers",
         n="95 accepted (45 treated, 50 control); 35 per group finished", measure="Time to finish the task",
         metric="time", value=-55.8, lo=-89.0, hi=-21.0, ci_derived=False,
         reported="Average 71.17 minutes with Copilot vs 160.89 without: 55.8% less time. 95% interval for the "
                  "improvement: 21% to 89%. p = 0.0017.",
         caveats="One narrow, well-defined task. A task-time result does not translate into output per month.",
         verified="Full text read (ar5iv version of the paper)."),
    dict(id="paradis-2024", short="Google engineers", authors="Paradis et al.", year=2024,
         title="How much does AI impact development speed? An enterprise-based randomized controlled trial",
         status="arXiv preprint", url="https://arxiv.org/abs/2410.12944",
         design="Randomized controlled trial inside Google", setting="Full-time software engineers", n="96 engineers",
         measure="Time on a task", metric="time", value=-21.0, lo=None, hi=None, ci_derived=False,
         reported="AI significantly shortened the time on task. Best estimate about 21%, 'although our confidence "
                  "interval is large'.",
         caveats="The bounds of the interval are not given in the abstract.",
         verified="Abstract read on arXiv."),
    dict(id="becker-2025", short="METR, experienced developers", authors="Becker, Rush, Barnes, Rein", year=2025,
         title="Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity",
         status="arXiv preprint, July 2025", url="https://arxiv.org/abs/2507.09089",
         design="Randomized controlled trial, each task randomly allowed or disallowed AI",
         setting="Experienced open-source developers on their own mature repositories",
         n="16 developers, 246 tasks", measure="Time to finish a task", metric="time", value=19.0, lo=None, hi=None,
         ci_derived=False,
         reported="Allowing AI increased completion time by 19%. Developers had predicted a 24% speedup and, afterwards, "
                  "believed they had been 20% faster.",
         caveats="Early-2025 tools (February to June 2025). Secondary reports say METR later called this result out of "
                 "date and published follow-up work in 2026; I could not open METR's own page to confirm, so treat "
                 "that as unverified. The perception gap is the lasting lesson: people's own estimates were wrong.",
         verified="Abstract read on arXiv. The 2026 follow-up was not verified from a primary source."),
    dict(id="noy-zhang-2023", short="Writing tasks", authors="Noy, Zhang", year=2023,
         title="Experimental Evidence on the Productivity Effects of Generative Artificial Intelligence",
         status="MIT working paper (March 2023, not peer reviewed in that version)",
         url="https://economics.mit.edu/sites/default/files/inline-files/Noy_Zhang_1.pdf",
         design="Preregistered online experiment, occupation-specific writing tasks", setting="College-educated professionals, ChatGPT",
         n="444 professionals", measure="Time taken; output quality", metric="sd", value=None, lo=None, hi=None,
         ci_derived=False,
         reported="Time taken fell by 0.8 standard deviations and quality rose by 0.4 standard deviations. Gains were "
                  "larger for lower-ability workers.",
         caveats="Reported in standard deviations, so it cannot be shown on a percent axis. Writing, not software.",
         verified="Abstract read in the paper's PDF."),
    dict(id="humlum-2025", short="Danish labor market", authors="Humlum, Vestergaard", year=2025,
         title="Still Waters, Rapid Currents: Early Labor Market Transformation under Generative AI",
         status="NBER Working Paper 33777 (May 2025, revised March 2026)", url="https://www.nber.org/papers/w33777",
         design="Difference-in-differences around ChatGPT's launch; adoption surveys linked to administrative records",
         setting="Workers and workplaces in exposed occupations, Denmark", n="large national samples",
         measure="Earnings and recorded hours", metric="null", value=0.0, lo=-2.0, hi=2.0, ci_derived=False,
         reported="Precise null effects on earnings and recorded hours; effects larger than 2% ruled out two years "
                  "after ChatGPT's launch. Employers shifted people toward new tasks such as AI oversight.",
         caveats="Not a measure of output. It shows that time saved does not automatically become pay or fewer hours, "
                 "which is why this tool counts only part of the extra output as bankable value.",
         verified="Abstract read on NBER. No time-savings figure appears in the abstract, so none is quoted."),
]

LEFT_OUT = [
    "Commonly quoted figures that could not be confirmed from a primary source here were left out: '40% less time' and "
    "'18% higher quality' for Noy and Zhang (the abstract reports standard deviations), a '19 percentage points' figure "
    "for the consultants study, and a '3% time saved' figure for Denmark.",
    "METR's 2026 follow-up. Secondary sources describe it; METR's own page could not be found.",
]


def _output() -> list[dict]:
    return [s for s in STUDIES if s["metric"] == "output"]


def published_output_range() -> dict:
    vals = [s["value"] for s in _output()]
    return dict(min=min(vals), max=max(vals), median=round(st.median(vals), 1), n=len(vals))


def compare(company: dict) -> dict:
    """Where this tool's company-wide AI effect sits against the published output effects. Context only."""
    est = company["did_lift"] * 100
    lo = company.get("did_ci_low", company["did_lift"]) * 100
    hi = company.get("did_ci_high", company["did_lift"]) * 100
    pr = published_output_range()
    if est > pr["max"]:
        verdict = "above" if lo > pr["max"] else "above_overlapping"
        text = (f"Your estimate ({est:.1f}%) is higher than every published output study (up to {pr['max']:.1f}%). "
                + ("Even the low end of your range is higher, so check for a measurement or selection problem."
                   if verdict == "above" else "Your range reaches down into the published results, so it is not clearly out of line."))
    elif est >= pr["min"]:
        verdict = "within"
        text = (f"Your estimate ({est:.1f}%) sits inside the range of published output effects "
                f"({pr['min']:.1f}% to {pr['max']:.1f}%, median {pr['median']:.1f}%).")
    elif hi >= pr["min"]:
        verdict = "below_overlapping"
        text = (f"Your estimate ({est:.1f}%) is below the published output effects ({pr['min']:.1f}% to {pr['max']:.1f}%), "
                f"but your range ({lo:.1f}% to {hi:.1f}%) reaches into them.")
    else:
        verdict = "below"
        text = (f"Your estimate ({est:.1f}%, range {lo:.1f}% to {hi:.1f}%) is below every published output effect "
                f"(lowest {pr['min']:.1f}%).")
    if est <= 0:
        verdict = "none"
        text = (f"Your estimate ({est:.1f}%) shows no gain. Published output studies mostly find gains, but METR's trial "
                "found experienced developers slower, so a zero is possible.")
    context = [
        "Most published studies follow volunteers or early adopters; a company-wide estimate includes light users, "
        "so a lower figure is expected.",
        "The studies measure different things (tasks, pull requests, issues per hour), so the match is rough.",
        "People's own estimates of their speedup were wrong in METR's trial (they believed 20% faster; measured 19% "
        "slower), which is why this tool measures output instead of asking.",
        "Humlum and Vestergaard found no effect on earnings or hours, so extra output is not automatically extra money. "
        "That is why the dollar figures count only part of it (the realization slider). It does not change the output "
        "effect compared above, which is measured before that step.",
    ]
    return dict(your_effect=round(est, 2), your_low=round(lo, 2), your_high=round(hi, 2), published=pr,
                verdict=verdict, text=text, context=context)


def payload(company: dict) -> dict:
    return dict(studies=STUDIES, comparison=compare(company), left_out=LEFT_OUT, verified_on=VERIFIED_ON)
