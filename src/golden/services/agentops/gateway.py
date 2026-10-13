"""Agent operations service — LLM gateway, safe agent runs, cost report, guardrails (incl. Envoy
ext_authz), red-team gate, evals and grounded RAG Q&A."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Any

from fastapi import HTTPException, Request, Response
from pydantic import BaseModel, Field

from golden.agentops import (
    SAMPLE_TASKS,
    LLMGateway,
    RunLedger,
    SafeAgentRunner,
    SimulatedTaskAgent,
    check_input,
    evaluate,
    load_identity,
    registered_agents,
    run_redteam,
    scan_output,
    unit_economics,
)
from golden.agentops.evals import CHECKS
from golden.agentops.runner import state_dir_default
from golden.ai.rag import RAGPipeline, sample_corpus
from golden.services.common import create_app, run

SERVICE = "agent-ops"
app = create_app(SERVICE, "Run AI agents in production: cost control, guardrails, evals, red-teaming, RAG.")
GATEWAY = LLMGateway(daily_tokens_per_caller=int(os.getenv("GOLDEN_LLM_DAILY_TOKENS", "50000")))
RAG = RAGPipeline()
RAG.ingest(sample_corpus(), "sample_kb")
MAX_PROMPT = 32_000


class LLMIn(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=MAX_PROMPT)
    caller: str = Field("anonymous", max_length=128)
    system: str = Field("", max_length=8_000)
    max_tokens: int = Field(512, ge=1, le=16_000)


class RunIn(BaseModel):
    agent: str = Field("invoice-reader", max_length=64)
    sample: str | None = Field("good", description="good | malformed | stuck | drifting")
    task: dict[str, Any] | None = None
    resume: bool = False
    per_run_usd: float | None = Field(None, gt=0, le=100)
    step_ceiling: int | None = Field(None, ge=1, le=500)


class TextIn(BaseModel):
    text: str = Field(..., max_length=200_000)


class ToolIn(BaseModel):
    agent: str
    tool: str


class EvalIn(BaseModel):
    output: str = Field(..., max_length=200_000)
    checks: list[str] = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    agent: str = "unknown"


class AskIn(BaseModel):
    question: str = Field(..., min_length=1, max_length=4_000)


@app.post("/api/v1/agentops/llm")
def llm(body: LLMIn) -> dict:
    result = GATEWAY.complete(body.prompt, caller=body.caller, system=body.system, max_tokens=body.max_tokens)
    if result.status == "blocked":
        raise HTTPException(status_code=422, detail=result.to_dict())
    if result.status == "budget_exceeded":
        raise HTTPException(status_code=429, detail=result.to_dict())
    if result.status == "error":
        raise HTTPException(status_code=503, detail=result.to_dict())
    return result.to_dict()


@app.get("/api/v1/agentops/agents")
def agents() -> dict:
    return {"agents": {name: load_identity(name).__dict__ for name in registered_agents()}}


@app.post("/api/v1/agentops/runs")
def run_agent(body: RunIn) -> dict:
    try:
        ident = load_identity(body.agent)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if body.per_run_usd is not None:
        ident = replace(ident, per_run_usd=body.per_run_usd)
    if body.step_ceiling is not None:
        ident = replace(ident, step_ceiling=body.step_ceiling)
    task = body.task or SAMPLE_TASKS.get(body.sample or "", None)
    if task is None:
        raise HTTPException(status_code=422, detail=f"unknown sample; choose from {sorted(SAMPLE_TASKS)}")
    return SafeAgentRunner(ident).run(SimulatedTaskAgent(ident.model), task, resume=body.resume).to_dict()


@app.get("/api/v1/agentops/report")
def report() -> dict:
    return unit_economics(RunLedger(state_dir_default()).records())


@app.post("/api/v1/agentops/guard/input")
def guard_input(body: TextIn) -> dict:
    return check_input(body.text).to_dict()


@app.post("/api/v1/agentops/guard/output")
def guard_output(body: TextIn) -> dict:
    return scan_output(body.text).to_dict()


@app.post("/api/v1/agentops/guard/tool")
def guard_tool(body: ToolIn) -> dict:
    from golden.agentops import check_tool

    try:
        allowed = load_identity(body.agent).allowed_tools
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return check_tool(body.tool, allowed).to_dict()


@app.post("/ext_authz/{path:path}", include_in_schema=False)
async def ext_authz(path: str, request: Request) -> Response:
    """Envoy ext_authz (HTTP mode): 200 lets the request through to the model server, 403 denies it.

    Infrastructure-level enforcement — a client that skips the SDK still passes through the proxy.
    """
    raw = (await request.body())[: MAX_PROMPT * 2].decode("utf-8", errors="replace")
    try:
        payload = json.loads(raw)
        text = (
            "\n".join(
                m.get("content", "") if isinstance(m.get("content"), str) else json.dumps(m.get("content"))
                for m in payload.get("messages", [])
            )
            or payload.get("prompt", "")
            or raw
        )
    except (ValueError, AttributeError):
        text = raw
    result = check_input(text)
    headers = {"x-golden-guard": "allow" if result.allowed else "deny"}
    if result.allowed:
        return Response(status_code=200, headers=headers)
    headers["x-golden-guard-categories"] = ",".join(result.categories)
    return Response(
        json.dumps({"denied": result.categories, "owasp": result.owasp}),
        status_code=403,
        headers=headers,
        media_type="application/json",
    )


@app.post("/api/v1/agentops/redteam")
def redteam() -> dict:
    return run_redteam(GATEWAY).to_dict()


@app.post("/api/v1/agentops/evals")
def evals(body: EvalIn) -> dict:
    unknown = set(body.checks) - set(CHECKS)
    if unknown:
        raise HTTPException(status_code=422, detail=f"unknown checks {sorted(unknown)}")
    return evaluate(body.output, body.checks, body.context, agent=body.agent).to_dict()


@app.post("/api/v1/agentops/rag/ask")
def ask(body: AskIn) -> dict:
    result = RAG.ask(body.question)
    if result["status"] == "blocked":
        raise HTTPException(status_code=422, detail=result)
    return result


def main() -> None:
    run(app, int(os.getenv("PORT", "8099")))


if __name__ == "__main__":
    main()
