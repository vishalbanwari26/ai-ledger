"""Nemotron on Nebius Token Factory: a tool-calling analyst with two model tiers.

Tier routing (this is the cost-efficiency story applied to ourselves):
  fast   - small Nemotron: tags, one-line summaries, cheap routine calls
  reason - largest Nemotron: multi-step questions that need tool calls and judgement
The model never sees raw rows. It calls tools that run the same maths the dashboard
shows, and every answer lists the tool calls it used as evidence.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from openai import OpenAI

from . import analysis as an
from . import bench
from . import evidence as ev
from .data import Dataset

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")

SYSTEM = """You are AI Ledger, a finance analyst who audits whether a company's AI spending pays off.
Rules:
- Get every number from the tools. Never invent figures. If a tool cannot answer, say so.
- Quote exact dollar amounts and ROI values from tool output. ROI = (value - cost) / cost.
- Value is estimated: output above each person's own baseline, times hours per unit and hourly rate,
  times a realization factor. Say this once if the user asks how value is computed.
- Never rank budget policies by ROI alone. ROI is a ratio and rises when spend falls. Compare policies on net
  monthly dollars (value minus cost) first, then on bill_risk. Rows are pre-flagged highest_net and
  lowest_bill_risk: use those flags and mention every flagged policy. bill_risk is (how much worse the bill gets if everyone spends
  at their own peak month; lower is more predictable). State both and name the trade-off.
- Each department has a confidence flag. If it is 'uncertain', the ROI range includes zero: say the data cannot
  separate that department from break-even, and quote roi_low and roi_high.
- Differences between levels (intern vs senior) mostly reflect hourly rate, because value is time saved times rate.
  Never recommend cutting access for a level on ROI alone; say what else matters (learning, ramp-up).
- Never blame, name, rank or characterise individual people, and never use words like lazy, wasteful, offender
  or abuser. Findings are about how seats, training, tools and budgets are set up. Say 'seats not in use' and
  'high spend without matching gain'. For each issue suggest the system fix first (training, workflow fit, asking the
  team, a team budget) and treat changing a seat or cap as the last step.
- Only recommend seat or cap changes that appear in get_actions, with its numbers. A low-ROI group is a reason to
  check tool fit and training, never by itself a reason to remove seats, and never for interns or juniors.
- If asked who to cut, or for the worst people, say once that this tool does not identify or rank individuals, then
  answer at group level. Say 'lowest-return groups', never 'worst', and say 'seat changes', never 'cutting people'.
- Definitions: an unused seat averages under 3 sessions a month; a high-spend seat spends above the 75th percentile of
  ROI-positive peers of the same department and level while its ROI is negative.
- Pay per use depends on an assumed list-price multiplier and ration rate. Whenever you mention it, state the
  assumed multiplier and the break-even multiplier from pay_per_use_breakeven. Tell the user to get a real quote.
- If summary.company.selection.significant is true, warn that adopters were already pulling ahead before rollout,
  that this was removed, and that the effect estimate is less certain.
- If asked how subjective or reliable the results are, call get_robustness. Say which parts are measured, which are
  estimated with a range, which are assumptions, and which decisions hold in what share of scenarios. Do not claim
  more certainty than a 'depends on assumptions' verdict allows.
- Token caps are peer norms, not a statement of need. Interns and juniors are floored at the department cap because
  they iterate more while learning. Say this if asked about caps by level.
- Per-head numbers: current_per_head is the average over everyone; expected_per_head is what the plan costs per head;
  ceiling_per_head is the most one active person may use (seat plus cap). Never compare the ceiling with the average.
- Separate solid savings (unused seats) from potential savings (high spend). The plan saves almost only through
  seats; above-norm spend is recovered only through training or hard caps, and hard caps cost output (get_plan_savings).
- If asked about published research or whether the estimate is believable, call get_evidence. Quote only numbers it
  returns, name the study, and say what it measured (time on a task, tasks completed, issues per hour). Never convert
  between those measures, and say the comparison is context, not proof.
- The AI effect on output (for example 8%) is measured before the realization share. Realization only turns that effect
  into dollars. Never use it to explain a difference from published output effects.
- The break-even effect is the AI effect on output the spend needs in order to pay for itself at the current realization
  share. Quote it with the measured effect and its range. Scenarios apply a published effect to the people counted as users;
  they are what-ifs, not forecasts.
- Be direct. Lead with the answer, then the two or three numbers that support it. No filler."""

TOOLS = [
    {"type": "function", "function": {
        "name": "get_summary", "description": "Company and per-department cost, value, ROI, unused seats, high-spend seats.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_waste", "description": "Recoverable monthly spend: unused seats plus spend above what "
        "ROI-positive peers spend, company-wide and per department, with annual total.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_robustness", "description": "How subjective the conclusions are: which decisions hold in what share "
        "of 180 assumption scenarios, which departments are positive or depend on assumptions, and which numbers are "
        "measured, estimated, assumed or judgement.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_plan_savings", "description": "What the 'Variable by role' plan actually saves, split into reassigned "
        "unused seats and caps, per department, plus what hard per-person caps would save and cost in output.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_evidence", "description": "Published studies on AI and productivity (with sources, designs, effect sizes, what was verified), how this tool's "
        "company-wide estimate compares with them, the break-even effect this spend needs, what-if scenarios using each published "
        "output effect, and the measured effect by experience level.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_actions", "description": "Proposed changes (reclaim seats, cap token spend) per department and level, "
        "each with monthly saving and reason.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_routing", "description": "Monthly saving from moving routine tokens to a cheaper open model, "
        "the value put at risk, and net gain, per department.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_groups", "description": "Department-and-level groups ranked by ROI, optionally filtered by department and segment "
        "(idle, high-spend, low-return, break-even, high-return). Never returns individuals.",
        "parameters": {"type": "object", "properties": {
            "department": {"type": "string"}, "segment": {"type": "string"},
            "limit": {"type": "integer"}, "worst_first": {"type": "boolean"}}}}},
    {"type": "function", "function": {
        "name": "compare_policies", "description": "Simulated monthly cost, value and ROI for each budget policy: "
        "status quo, fixed budget, pay per use, variable by role.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "budget_recommendations", "description": "Per-department verdict (fixed, variable or restrict) with "
        "recommended per-head monthly budget and the reason.",
        "parameters": {"type": "object", "properties": {}}}},
]


_CLIENT: OpenAI | None = None   # shared across visitors: one connection pool, one model lookup
_MODELS: dict[str, str] | None = None


@dataclass
class Analyst:
    ds: Dataset
    assumptions: an.Assumptions = field(default_factory=an.Assumptions)
    _client: OpenAI | None = None
    _models: dict[str, str] | None = None

    # ----------------------------------------------------------- plumbing
    def client(self) -> OpenAI:
        global _CLIENT
        if self._client is not None:
            return self._client
        if _CLIENT is None:
            key = os.environ.get("NEBIUS_API_KEY")
            if not key:
                raise RuntimeError("NEBIUS_API_KEY is not set. Export it before starting the server.")
            _CLIENT = OpenAI(base_url=BASE_URL, api_key=key)
        return _CLIENT

    def models(self) -> dict[str, str]:
        """Env overrides win; otherwise pick Nemotron models from the live model list."""
        global _MODELS
        if self._models:
            return self._models
        if _MODELS:
            return _MODELS
        fast, reason = os.environ.get("NEBIUS_MODEL_FAST"), os.environ.get("NEBIUS_MODEL_REASON")
        if not (fast and reason):
            ids = [m.id for m in self.client().models.list().data]
            nemo = [i for i in ids if "nemotron" in i.lower()]
            if not nemo:
                raise RuntimeError("No Nemotron model found on this account. Set NEBIUS_MODEL_FAST / "
                                   "NEBIUS_MODEL_REASON explicitly. Available: " + ", ".join(ids[:20]))
            reason = reason or max(nemo, key=_size_hint)
            fast = fast or min(nemo, key=_size_hint)
        _MODELS = {"fast": fast, "reason": reason}
        return _MODELS

    def run_tool(self, name: str, args: dict) -> dict | list:
        a, ds = self.assumptions, self.ds
        if name == "get_summary":
            return an.summary(ds, a)
        if name == "get_waste":
            return an.waste(ds, a)
        if name == "get_robustness":
            return an.robustness(ds, a)
        if name == "get_plan_savings":
            return an.plan_savings(ds, a)
        if name == "get_evidence":
            return bench.bundle(ds, a)
        if name == "get_actions":
            return an.actions(ds, a)
        if name == "get_routing":
            return an.routing(ds, a)
        if name in ("list_groups", "list_employees"):
            return an.list_people(ds, a, args.get("department"), args.get("segment"),
                                  min(int(args.get("limit", 10)), 25), args.get("worst_first", True))
        if name == "compare_policies":
            return dict(policies=an.compare_policies(ds, a), pay_per_use_breakeven=an.pay_per_use_breakeven(ds, a))
        if name == "budget_recommendations":
            return an.budget_recommendations(ds, a)
        return {"error": f"unknown tool {name}"}

    # ----------------------------------------------------------- calls
    def _loop(self, msgs: list[dict], max_steps: int = 6) -> tuple[str, list[dict]]:
        m = self.models()["reason"]
        evidence: list[dict] = []
        for _ in range(max_steps):
            r = self.client().chat.completions.create(model=m, messages=msgs, tools=TOOLS, temperature=0.2)
            msg = r.choices[0].message
            if not msg.tool_calls:
                return _strip_think(msg.content or ""), evidence
            msgs.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = self.run_tool(tc.function.name, args)
                evidence.append(dict(tool=tc.function.name, args=args, result=result))
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        return "I ran out of steps before reaching an answer.", evidence

    def ask(self, question: str) -> dict:
        m = self.models()["reason"]
        targeted = asks_about_individuals(question)
        q = reframe(question) if targeted else question
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": q}]
        answer, evidence = self._loop(msgs)
        repaired = False
        if blames(answer):  # one repair pass, then a deterministic fallback: blame never reaches the user
            repaired = True
            msgs = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": "Rewrite this answer so it never blames, names or ranks people and "
                     "uses only these terms: unused seats, high-spend seats, lowest-return groups, seat changes. "
                     "Keep every number. Do not call any tool.\n\n" + answer}]
            answer = _strip_think(self.client().chat.completions.create(model=m, messages=msgs, temperature=0.1)
                                  .choices[0].message.content or "")
            if blames(answer):
                answer = self.safe_summary()
        if targeted:
            answer = ("This tool does not identify or rank individuals. Here is the group-level view.\n\n" + answer)
        return dict(answer=answer, evidence=evidence, model=m, reframed=targeted, repaired=repaired)

    def safe_summary(self) -> str:
        w = an.waste(self.ds, self.assumptions)
        acts = an.actions(self.ds, self.assumptions)[:5]
        lines = [f"Recoverable spend is ${w['total_monthly']:,.0f} a month (${w['total_annual']:,.0f} a year): "
                 f"{w['idle_seats']} unused seats and {w['over_people']} high-spend seats without matching gain.",
                 "Largest proposed changes, to discuss with each team first:"]
        lines += [f"- {r['kind']}: {r['department']} ({r['level']}), {r['people']} seats, ${r['monthly_saving']:,.0f} a month"
                  for r in acts]
        return "\n".join(lines)

    def brief(self) -> dict:
        """One cheap call: executive summary of the current numbers using the fast model."""
        m = self.models()["fast"]
        data = {"summary": an.summary(self.ds, self.assumptions), "waste": an.waste(self.ds, self.assumptions),
                "routing": an.routing(self.ds, self.assumptions),
                "policies": an.compare_policies(self.ds, self.assumptions),
                "pay_per_use_breakeven": an.pay_per_use_breakeven(self.ds, self.assumptions)}
        r = self.client().chat.completions.create(
            model=m, temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": "Write a 4 sentence executive brief for the CFO from this data. "
                       "Open with the total recoverable spend (unused seats plus above-norm spend, monthly and annual) and the department "
                       "with the most. Then name the best and worst department by ROI. For policies, "
                       "recommend by net monthly dollars and bill_risk, not by ROI ratio alone, and name the "
                       "trade-off. Use exact figures.\n" + json.dumps(data)}])
        return dict(brief=_strip_think(r.choices[0].message.content or ""), model=m)


_BLAME = re.compile(
    r"\b(lazy|wasteful|offenders?|abusers?|overspenders?|slackers?|freeloaders?|over-allocated people)\b"
    r"|\bworst (?:performers?|employees?|people|users?|overspend\w*)\b"
    r"|\b(?:cut|fire|sack|lay off|terminate|remove) (?:individuals?|people|employees?|staff|workers?)\b", re.I)
_TARGETED = re.compile(
    r"\b(who (?:is|are|should|do)\b|which (?:individuals?|people|employees?|persons?|staff)|names?\b|"
    r"individuals?|worst (?:people|employees?|performers?|users?|overspenders?)|top spenders?|"
    r"(?:cut|fire|sack|lay off|terminate) (?:people|employees?|staff))", re.I)


def blames(text: str) -> bool:
    return bool(_BLAME.search(text))


def asks_about_individuals(question: str) -> bool:
    return bool(_TARGETED.search(question))


def reframe(question: str) -> str:
    """Replace a question about people with a standalone one about seats and groups, before the model sees it."""
    return ("Where is the recoverable AI spend by department, which group-level changes should we discuss first "
            "(use get_waste and get_actions), and what should we check with each team before changing any seat "
            "or budget? Answer in under 200 words, group level only.")


def _size_hint(model_id: str) -> float:
    """Rank Nemotron variants by parameter count in the name; 'ultra' > 'super' > 'nano'."""
    s = model_id.lower()
    rank = 0.0
    for word, v in (("nano", 1), ("super", 50), ("ultra", 500)):
        if word in s:
            rank = max(rank, v)
    nums = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)b", s)]
    return rank + (max(nums) if nums else 0)


def _strip_think(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
