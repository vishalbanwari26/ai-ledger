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
- Be direct. Lead with the answer, then the two or three numbers that support it. No filler."""

TOOLS = [
    {"type": "function", "function": {
        "name": "get_summary", "description": "Company and per-department cost, value, ROI, idle seats, overspenders.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "get_waste", "description": "Recoverable monthly spend: idle seats plus overspend above what "
        "ROI-positive peers spend, company-wide and per department, with annual total.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "list_employees", "description": "Employees ranked by ROI, optionally filtered by department and segment "
        "(idle, overspender, low-return, break-even, high-return).",
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
        if name == "list_employees":
            return an.employees_in(ds, a, args.get("department"), args.get("segment"),
                                   min(int(args.get("limit", 10)), 25), args.get("worst_first", True))
        if name == "compare_policies":
            return an.compare_policies(ds, a)
        if name == "budget_recommendations":
            return an.budget_recommendations(ds, a)
        return {"error": f"unknown tool {name}"}

    # ----------------------------------------------------------- calls
    def ask(self, question: str, max_steps: int = 6) -> dict:
        m = self.models()["reason"]
        msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
        evidence = []
        for _ in range(max_steps):
            r = self.client().chat.completions.create(model=m, messages=msgs, tools=TOOLS, temperature=0.2)
            msg = r.choices[0].message
            if not msg.tool_calls:
                return dict(answer=_strip_think(msg.content or ""), evidence=evidence, model=m)
            msgs.append(msg.model_dump(exclude_none=True))
            for tc in msg.tool_calls:
                args = json.loads(tc.function.arguments or "{}")
                result = self.run_tool(tc.function.name, args)
                evidence.append(dict(tool=tc.function.name, args=args, result=result))
                msgs.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(result)})
        return dict(answer="I ran out of steps before reaching an answer.", evidence=evidence, model=m)

    def brief(self) -> dict:
        """One cheap call: executive summary of the current numbers using the fast model."""
        m = self.models()["fast"]
        data = {"summary": an.summary(self.ds, self.assumptions), "waste": an.waste(self.ds, self.assumptions),
                "policies": an.compare_policies(self.ds, self.assumptions)}
        r = self.client().chat.completions.create(
            model=m, temperature=0.2,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": "Write a 4 sentence executive brief for the CFO from this data. "
                       "Open with the total recoverable waste (idle seats plus overspend, monthly and annual) and the department "
                       "with the most. Then name the best and worst department by ROI. For policies, "
                       "recommend by net monthly dollars and bill_risk, not by ROI ratio alone, and name the "
                       "trade-off. Use exact figures.\n" + json.dumps(data)}])
        return dict(brief=_strip_think(r.choices[0].message.content or ""), model=m)


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
