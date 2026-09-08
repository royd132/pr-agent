"""Deterministic PR risk profiling used before LLM delegation.

The profiler deliberately stays small and explainable.  It does not decide that
an issue exists; it only estimates which review domain deserves model budget.
That keeps routing auditable and prevents the multi-agent topology from becoming
an unconditional fan-out.
"""
from dataclasses import asdict, dataclass, field
import re
from typing import Dict, Iterable, List, Set

from .diff_parser import ParsedDiff


SECURITY_PATTERNS = {
    "authorization": re.compile(r"\b(auth|authorize|permission|role|rbac|tenant|scope|acl)\b", re.I),
    "dynamic-execution": re.compile(r"\b(eval|exec|pickle\.loads|yaml\.load|subprocess|os\.system|shell\s*=\s*true)\b", re.I),
    "secret-handling": re.compile(r"\b(password|secret|token|api[_-]?key|credential|private[_-]?key)\b", re.I),
    "injection-boundary": re.compile(r"(\b(sql|query|cursor\.execute|request\.|input\(|path|url|http|template|redirect)\b|user[_-]?path|open\()", re.I),
}

RELIABILITY_PATTERNS = {
    "state-transition": re.compile(r"\b(state|status|transition|commit|rollback|transaction|save\(|update\(|delete\()\b", re.I),
    "failure-handling": re.compile(r"\b(try|except|raise|timeout|retry|cancel|fallback|finally)\b", re.I),
    "concurrency": re.compile(r"\b(thread|async|await|lock|mutex|semaphore|queue|stream|lease|ack|race)\b", re.I),
    "resource-lifecycle": re.compile(r"\b(open\(|close\(|socket|connection|cursor|file|session)\b", re.I),
    "compatibility": re.compile(r"\b(schema|migration|api|endpoint|config|version|serialize|deserialize|json)\b", re.I),
    "quality-regression": re.compile(r"(TODO|FIXME|debug\b|print\()", re.I),
}

SECURITY_PATH = re.compile(r"(^|/)(auth|security|permission|identity|token|oauth|payment|billing)(/|\.|$)", re.I)
RELIABILITY_PATH = re.compile(r"(^|/)(worker|queue|store|db|database|migration|runtime|service|api|config|cache)(/|\.|$)", re.I)
TEST_PATH = re.compile(r"(^|/)(tests?|specs?)(/|\.)|(^|/).*(_test|test_|\.spec\.)", re.I)
DOC_PATH = re.compile(r"(^|/)(docs?|examples?)(/|\.)|\.(md|rst|txt)$", re.I)


@dataclass
class RiskProfile:
    change_types: List[str] = field(default_factory=list)
    risk_domains: List[str] = field(default_factory=list)
    risk_level: str = "normal"
    complexity_score: int = 0
    production_files: int = 0
    test_files: int = 0
    added_lines: int = 0
    requires_security_review: bool = False
    requires_reliability_review: bool = True
    auditor_recommended: bool = False
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return asdict(self)

    @property
    def worker_roles(self) -> List[str]:
        roles = []
        if self.requires_security_review:
            roles.append("boundary-inspector")
        if self.requires_reliability_review:
            roles.append("behavior-inspector")
        return roles


def _added_text(parsed: ParsedDiff) -> str:
    return "\n".join(item.content for item in parsed.added_lines)[:120_000]


def build_risk_profile(diff: str, parsed: ParsedDiff) -> RiskProfile:
    """Build an explainable routing profile from paths and added-line signals."""
    del diff  # the parsed representation is intentionally sufficient for routing.
    files = list(parsed.files)
    text = _added_text(parsed)
    test_files = [path for path in files if TEST_PATH.search(path)]
    production_files = [path for path in files if path not in test_files and not DOC_PATH.search(path)]

    domains: Set[str] = set()
    change_types: Set[str] = set()
    reasons: List[str] = []

    for path in files:
        lowered = path.lower()
        if SECURITY_PATH.search(path):
            domains.add("security-sensitive-path")
        if RELIABILITY_PATH.search(path):
            domains.add("runtime-or-state-path")
        if TEST_PATH.search(path):
            change_types.add("tests")
        elif DOC_PATH.search(path):
            change_types.add("documentation")
        else:
            change_types.add("production-code")
        if "migration" in lowered or lowered.endswith((".sql", ".ddl")):
            change_types.add("schema-change")
        if any(token in lowered for token in ("api", "route", "endpoint", "schema")):
            change_types.add("interface-change")
        if any(token in lowered for token in ("auth", "permission", "security", "token")):
            change_types.add("trust-boundary-change")

    for name, pattern in SECURITY_PATTERNS.items():
        if pattern.search(text):
            domains.add(name)
    for name, pattern in RELIABILITY_PATTERNS.items():
        if pattern.search(text):
            domains.add(name)

    security_domains = {
        "security-sensitive-path", "authorization", "dynamic-execution",
        "secret-handling", "injection-boundary",
    }
    reliability_domains = {
        "runtime-or-state-path", "state-transition", "failure-handling",
        "concurrency", "resource-lifecycle", "compatibility", "quality-regression",
    }
    security = bool(domains.intersection(security_domains))
    reliability = bool(domains.intersection(reliability_domains))

    # Pure documentation/test-only changes do not need an LLM security lane by default.
    if not production_files:
        security = False
        reliability = bool(test_files)
        reasons.append("no production-code files changed")

    added = len(parsed.added_lines)
    score = min(4, len(production_files))
    score += min(4, added // 40)
    score += min(4, len(domains))
    score += 2 if security else 0
    score += 2 if {"concurrency", "state-transition"}.intersection(domains) else 0
    score += 2 if "schema-change" in change_types else 0
    score += 1 if production_files and not test_files else 0

    if score >= 10 or "dynamic-execution" in domains or (
        security and {"authorization", "secret-handling"}.intersection(domains)
    ):
        level = "high"
    elif score <= 2 and not production_files:
        level = "low"
    else:
        level = "normal"

    # Reliability is the safe fallback lane for ordinary production changes.
    if production_files and not security and not reliability:
        reliability = True
        reasons.append("ordinary production change uses reliability fallback")
    if security:
        reasons.append("security-sensitive path or added-line signal detected")
    if reliability:
        reasons.append("state/reliability/compatibility review is relevant")
    if production_files and not test_files:
        reasons.append("production files changed without an accompanying test file")

    auditor = level == "high" or (
        security and reliability and len(production_files) >= 2
    )

    return RiskProfile(
        change_types=sorted(change_types),
        risk_domains=sorted(domains),
        risk_level=level,
        complexity_score=score,
        production_files=len(production_files),
        test_files=len(test_files),
        added_lines=added,
        requires_security_review=security,
        requires_reliability_review=reliability,
        auditor_recommended=auditor,
        reasons=reasons[:12],
    )
