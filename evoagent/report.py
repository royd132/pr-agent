from typing import Any, Dict, Iterable


def _text(value: Any, fallback: str = "Not established") -> str:
    rendered = str(value or "").strip()
    return rendered or fallback


def _items(values: Iterable[Any]) -> list:
    return [str(value).strip() for value in (values or []) if str(value).strip()]


def _bullets(values: Iterable[Any], fallback: str = "None recorded") -> list:
    items = _items(values)
    return ["- %s" % value for value in items] if items else ["- %s" % fallback]


def to_markdown(report: Dict[str, Any]) -> str:
    title = "# DiffPrism PR Review"
    if report.get("pull_request") is not None:
        title += " — #%s" % report["pull_request"]
    verdict = report.get("verdict") or {}
    change_map = report.get("change_map") or {}
    findings = report.get("findings") or []
    collaboration = report.get("collaboration") or {}
    run_mode = report.get("run_mode") or {}
    execution = report.get("execution") or {}

    lines = [
        title, "",
        "**Repository:** `%s`  " % report.get("repository", ""),
        "**Risk:** `%s`  " % report.get("risk", "unknown"),
        "**Reviewer:** `%s`" % report.get("reviewer", "unknown"),
        "", _text(report.get("summary"), "No summary provided."), "",
        "## Merge verdict", "",
        "**%s** — %s" % (
            _text(verdict.get("decision"), "unknown").upper(),
            _text(verdict.get("reason"), "No decision rationale recorded."),
        ), "",
        "## Change map", "",
        "**Intent:** %s" % _text(change_map.get("intent")), "",
        "**Affected surfaces**", *_bullets(change_map.get("surfaces")), "",
        "**Affected files**", *_bullets(change_map.get("affected_files")), "",
        "**Test gaps**", *_bullets(change_map.get("test_gaps")), "",
        "## Verified findings", "",
    ]

    icons = {"critical": "🚨", "high": "🔴", "medium": "🟠", "low": "🟡"}
    if not findings:
        lines.extend(["✅ No verified actionable issue detected in the added lines.", ""])
    for index, item in enumerate(findings, 1):
        severity = str(item.get("severity") or "medium").lower()
        lines.extend([
            "### %d. %s %s" % (
                index, icons.get(severity, "•"), _text(item.get("title"), "Finding")
            ), "",
            "`%s:%s` · **%s** · `%s` · confidence `%s`" % (
                item.get("path", ""), item.get("line", 0), severity.upper(),
                item.get("rule_id", ""), item.get("confidence", "unknown"),
            ), "",
            "**Trigger:** %s" % _text(item.get("trigger")), "",
            "**Evidence**", "", "```text", _text(item.get("evidence")), "```", "",
            "**Impact:** %s" % _text(item.get("impact"), _text(item.get("explanation"))), "",
            "**Examiner:** `%s` — %s" % (
                _text(item.get("verification"), "unverified"),
                _text(item.get("examiner_reason"), "No examiner rationale recorded."),
            ), "",
            "**Suggested fix:** %s" % _text(item.get("fix"), "Not provided"), "",
            "**Suggested verification:** %s" % _text(item.get("test"), "Not provided"), "",
        ])

    lines.extend(["## Required actions", ""])
    lines.extend(_bullets(verdict.get("required_actions"), "No required action"))
    lines.extend(["", "## Review trail and execution facts", ""])
    lines.extend([
        "- Protocol: `%s`" % _text(collaboration.get("protocol"), "unknown"),
        "- Roles: `%s`" % ", ".join(_items(collaboration.get("roles")) or ["none recorded"]),
        "- Verified findings: `%s`; rejected findings: `%s`" % (
            verdict.get("verified_findings", len(findings)), verdict.get("rejected_findings", 0),
        ),
        "- Mode: requested `%s`, effective `%s`" % (
            run_mode.get("requested", "unknown"), run_mode.get("effective", "unknown"),
        ),
        "- Model calls: `%s`; tool calls: `%s`" % (
            execution.get("llm_calls", 0), execution.get("tool_calls", 0),
        ),
        "- Tokens: input `%s`, output `%s`, total `%s`" % (
            execution.get("input_tokens", 0), execution.get("output_tokens", 0),
            execution.get("total_tokens", 0),
        ),
        "- Token cost: `$%.8f`; latency: `%s ms`" % (
            float(execution.get("cost_usd", 0) or 0), execution.get("duration_ms", 0),
        ),
    ])
    if run_mode.get("fallback_reason"):
        lines.extend(["", "> %s" % run_mode["fallback_reason"]])
    context = execution.get("context_management") or {}
    if context:
        memory = context.get("memory_recall") or {}
        lines.append(
            "- Context compression: `%s` view(s), estimated reduction `%.1f%%`; "
            "recalled memories `%s`" % (
                context.get("compression_calls", 0),
                max(0.0, float(context.get("estimated_reduction_ratio", 0) or 0) * 100),
                memory.get("recalled", 0),
            )
        )

    lines.extend(["", "## Explicit unknowns", ""])
    lines.extend(_bullets(change_map.get("unknowns"), "No unknown recorded"))
    return "\n".join(lines) + "\n"
