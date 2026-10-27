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
from dataclasses import dataclass, field

from openai import OpenAI

from . import agent
from . import analysis as an
from .agent import (INDIVIDUALS_PREFIX, REPAIR_PROMPT, SYSTEM, TOOLS, _size_hint, asks_about_individuals,  # noqa: F401  (re-exported)
                    blames, reframe, strip_think)
from .data import Dataset

BASE_URL = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")

_CLIENT: OpenAI | None = None   # shared across visitors: one connection pool, one model lookup
_MODELS: dict[str, str] | None = None
_strip_think = strip_think      # the old private name, kept for the tests


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
            picked = agent.pick_models([m.id for m in self.client().models.list().data])
            reason, fast = reason or picked["reason"], fast or picked["fast"]
        _MODELS = {"fast": fast, "reason": reason}
        return _MODELS

    def run_tool(self, name: str, args: dict) -> dict | list:
        return agent.run_tool(self.ds, self.assumptions, name, args)

    def safe_summary(self) -> str:
        return agent.safe_summary(self.ds, self.assumptions)

    # ----------------------------------------------------------- calls
    def _loop(self, msgs: list[dict], max_steps: int = 6) -> tuple[str, list[dict]]:
        m = self.models()["reason"]
        evidence: list[dict] = []
        for _ in range(max_steps):
            r = self.client().chat.completions.create(model=m, messages=msgs, tools=TOOLS, temperature=0.2)
            msg = r.choices[0].message
            if not msg.tool_calls:
                return strip_think(msg.content or ""), evidence
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
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": REPAIR_PROMPT + answer}]
            answer = strip_think(self.client().chat.completions.create(model=m, messages=msgs, temperature=0.1)
                                 .choices[0].message.content or "")
            if blames(answer):
                answer = self.safe_summary()
        if targeted:
            answer = INDIVIDUALS_PREFIX + answer
        return dict(answer=answer, evidence=evidence, model=m, reframed=targeted, repaired=repaired)

    def brief(self) -> dict:
        """One cheap call: executive summary of the current numbers using the fast model."""
        m = self.models()["fast"]
        r = self.client().chat.completions.create(model=m, temperature=0.2, messages=agent.brief_messages(self.ds, self.assumptions))
        return dict(brief=strip_think(r.choices[0].message.content or ""), model=m)
