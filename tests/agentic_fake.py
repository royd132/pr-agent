import json


class FakeAgenticClient:
    provider = "fake"
    model = "fake-model"

    def complete_json(self, role, _system, user, ledger=None, max_tokens=None):
        if ledger:
            ledger.record_model(
                role, self.provider, self.model,
                {"prompt_tokens": 10, "completion_tokens": 5}, 1,
            )
        managed = json.loads(user)
        task = json.loads(managed["task"])
        if role == "prism-lead":
            if task["phase"] == "delegate":
                skills = [
                    item["name"] for item in task.get("available_agent_skills") or []
                ]
                return {
                    "action": "final",
                    "delegations": [
                        {
                            "assignment_id": "security-1", "worker": "scope-mapper",
                            "objective": "Review security",
                            "skills": skills,
                        },
                        {
                            "assignment_id": "reliability-1",
                            "worker": "failure-hunter",
                            "objective": "Review correctness and reliability",
                            "skills": skills,
                        },
                    ], "risk_level": "normal",
                }
            if task["phase"] == "assess-workers":
                return {
                    "action": "final", "revision_requests": [],
                    "examiner_objective": "Verify every candidate against changed lines.",
                }
            if task["phase"] == "finalize":
                return {
                    "action": "final",
                    "accepted_finding_indices": list(
                        range(len(task["candidate_findings"]))
                    ),
                    "confidence_adjustments": [],
                    "resolution_summary": "Only examiner-verified findings are published.",
                }
            raise AssertionError(task["phase"])
        if role == "failure-hunter":
            instructions = "\n".join(
                item.get("instructions", "")
                for item in task.get("active_agent_skills") or []
            )
            rendered_diff = json.dumps(task.get("diff"), ensure_ascii=False)
            if "TODO" in instructions and "TODO" in rendered_diff:
                return {"action": "final", "findings": [{
                    "rule_id": "QUALITY-UNFINISHED", "severity": "low",
                    "title": "Unfinished production behavior",
                    "explanation": "The added TODO marks unfinished production behavior.",
                    "path": "a.py", "line": 2,
                    "evidence": "# TODO finish validation",
                    "fix": "Complete the behavior before merge.",
                    "test": "Add a regression test for the unfinished path.",
                    "confidence": 0.8,
                    "trigger": "The changed TODO path reaches production behavior.",
                    "impact": "Validation can remain incomplete at runtime.",
                }]}
            return {"action": "final", "findings": []}
        if role == "scope-mapper":
            return {
                "action": "final",
                "change_map": {
                    "intent": "Change application behavior",
                    "surfaces": ["runtime"],
                    "affected_files": ["a.py"],
                    "test_gaps": ["changed path"],
                    "unknowns": [],
                },
                "findings": [],
            }
        if role == "evidence-examiner":
            return {
                "action": "final",
                "decisions": [
                    {
                        "finding_index": index,
                        "decision": "verified",
                        "reason": "The finding cites a changed line and a concrete trigger.",
                        "confidence_adjustment": 0.0,
                        "supporting_evidence_ids": [],
                    }
                    for index, _item in enumerate(task["candidates"])
                ],
            }
        raise AssertionError(role)


def enable_agentic_service(service):
    service.chat_client = FakeAgenticClient()
    service.reviewer = service._build_agentic_reviewer()
    service.harness.reviewer = service.reviewer
    return service
