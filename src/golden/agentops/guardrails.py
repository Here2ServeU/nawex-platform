"""LLM guardrails — enforced in code (and at the proxy via Envoy ext_authz), not in the system prompt.

A prompt-level instruction ("never reveal secrets") can be talked around; a check that runs on every
request and response cannot. Three stages:

* **input**  — prompt injection / jailbreak / system-prompt extraction heuristics, sensitive data in
               the prompt, size cap                                    (OWASP LLM01, LLM02, LLM07, LLM10)
* **tool**   — per-agent tool allowlist; unknown tools are denied                       (LLM06 excessive agency)
* **output** — PII and secret scanning with redaction before anything leaves           (LLM02, LLM05)

``classifier`` is a hook for a model-based guard (Llama Guard via ext_authz, or a commercial AI firewall —
Prisma AIRS, Lakera, …): it receives the text and returns a category or ``None``. The heuristics below run
first, are deterministic and cost nothing.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass, field
from typing import Any

from golden.agentops.metrics import GUARD_DECISIONS
from golden.security.redaction import REDACTED, redact_text

MAX_PROMPT_CHARS = 32_000

INJECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "prompt_injection": (
        r"\bignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
        r"\bdisregard (all |the )?(previous|prior|above|system) ",
        r"\bforget (everything|all|your) (you|instructions|rules)",
        r"\bnew instructions?:",
        r"\byou are now (in )?(developer|dan|jailbreak|god) mode",
        r"<\s*/?\s*(system|im_start|im_end)\s*>",
        r"\[\s*(system|inst)\s*\]",
    ),
    "system_prompt_extraction": (
        r"\b(reveal|print|show|repeat|output|leak) (me )?(your|the) (system|hidden|initial) (prompt|instructions)",
        r"\bwhat (is|are) your (system )?(prompt|instructions)\b",
    ),
    "jailbreak": (
        r"\bpretend (you are|to be) .{0,40}(no|without) (rules|restrictions|filters)",
        r"\bdo anything now\b",
        r"\bhypothetically,? (how|explain) (would|to) .{0,40}(bypass|disable|evade)",
    ),
    "data_exfiltration": (
        r"\b(send|post|upload|exfiltrate) .{0,40}(to|at) https?://",
        r"!\[[^\]]*\]\(https?://[^)]*\?(q|data|d)=",  # markdown image beacon
    ),
}

SECRET_PATTERNS: dict[str, str] = {
    "aws_access_key": r"\b(AKIA|ASIA)[0-9A-Z]{16}\b",
    "private_key": r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "github_token": r"\bgh[pousr]_[A-Za-z0-9]{36,}\b",
    "slack_token": r"\bxox[abpors]-[A-Za-z0-9-]{10,}\b",
    "anthropic_key": r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",
    "openai_key": r"\bsk-(proj-)?[A-Za-z0-9]{32,}\b",
    "jwt": r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    "generic_secret": r"(?i)\b(api[_-]?key|secret|password|passwd|token)\s*[:=]\s*['\"]?[^\s'\"]{8,}",
}

OWASP_LLM_TOP_10 = {
    "LLM01": "Prompt Injection",
    "LLM02": "Sensitive Information Disclosure",
    "LLM03": "Supply Chain",
    "LLM04": "Data and Model Poisoning",
    "LLM05": "Improper Output Handling",
    "LLM06": "Excessive Agency",
    "LLM07": "System Prompt Leakage",
    "LLM08": "Vector and Embedding Weaknesses",
    "LLM09": "Misinformation",
    "LLM10": "Unbounded Consumption",
}

CATEGORY_OWASP = {
    "prompt_injection": "LLM01",
    "jailbreak": "LLM01",
    "data_exfiltration": "LLM02",
    "system_prompt_extraction": "LLM07",
    "sensitive_input": "LLM02",
    "secret": "LLM02",
    "pii": "LLM02",
    "tool_not_allowed": "LLM06",
    "oversized": "LLM10",
    "classifier": "LLM01",
}

_COMPILED = {cat: [re.compile(p, re.IGNORECASE) for p in pats] for cat, pats in INJECTION_PATTERNS.items()}
_SECRETS = {name: re.compile(p) for name, p in SECRET_PATTERNS.items()}

Classifier = Callable[[str], str | None]


@dataclass
class GuardResult:
    allowed: bool
    stage: str
    categories: list[str] = field(default_factory=list)
    owasp: list[str] = field(default_factory=list)
    text: str = ""  # sanitized text (output stage) or the original (input stage)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _result(stage: str, text: str, hits: list[tuple[str, str]], *, block: bool) -> GuardResult:
    cats = sorted({c for c, _ in hits})
    allowed = not (block and cats)
    for cat in cats or ["none"]:
        GUARD_DECISIONS.labels(stage=stage, decision="allow" if allowed else "block", category=cat).inc()
    return GuardResult(
        allowed=allowed,
        stage=stage,
        categories=cats,
        owasp=sorted({CATEGORY_OWASP.get(c, "LLM01") for c in cats}),
        text=text,
        reasons=[r for _, r in hits],
    )


def find_secrets(text: str) -> list[str]:
    return [name for name, rx in _SECRETS.items() if rx.search(text)]


def check_input(
    text: str, *, classifier: Classifier | None = None, max_chars: int = MAX_PROMPT_CHARS
) -> GuardResult:
    hits: list[tuple[str, str]] = []
    if len(text) > max_chars:
        hits.append(("oversized", f"prompt is {len(text)} chars (max {max_chars})"))
    for cat, patterns in _COMPILED.items():
        for rx in patterns:
            if m := rx.search(text):
                hits.append((cat, f"{cat}: '{m.group(0)[:60]}'"))
                break
    secrets = find_secrets(text)
    if secrets:
        hits.append(("secret", f"credential in prompt: {', '.join(secrets)}"))
    if redact_text(text) != text:
        hits.append(("sensitive_input", "regulated identifier (SSN/card/PHI field) in prompt"))
    if classifier is not None and not hits and (category := classifier(text)):
        hits.append(("classifier", f"classifier flagged: {category}"))
    return _result("input", text, hits, block=True)


def check_tool(tool: str, allowed_tools: Iterable[str]) -> GuardResult:
    allowed = set(allowed_tools)
    hits = (
        [] if tool in allowed or "*" in allowed else [("tool_not_allowed", f"tool {tool!r} not in allowlist")]
    )
    return _result("tool", tool, hits, block=True)


def scan_output(text: str, *, block_on_secret: bool = True) -> GuardResult:
    """Redact PII and secrets; block outright when a credential is about to leave."""
    hits: list[tuple[str, str]] = []
    sanitized = text
    secrets = find_secrets(text)
    for name in secrets:
        sanitized = _SECRETS[name].sub(REDACTED, sanitized)
    if secrets:
        hits.append(("secret", f"credential in output: {', '.join(secrets)}"))
    redacted = redact_text(sanitized)
    if redacted != sanitized:
        hits.append(("pii", "PII/PHI redacted from output"))
    sanitized = redacted
    result = _result("output", sanitized, hits, block=block_on_secret and bool(secrets))
    return result
