import os
import tempfile
import unittest

from evoagent.evolution_proof import (
    generate_prompt_evolution_cases,
    run_prompt_evolution_proof,
    write_jsonl,
)


class PromptEvolutionProofTests(unittest.TestCase):
    def test_feedback_evolution_improves_repository_disjoint_holdout(self):
        source = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "evaluation_data", "prompt_evolution_130.jsonl"
        ))
        if not os.path.exists(source):
            self.skipTest("optional prompt_evolution_130.jsonl was not supplied")
        cases = generate_prompt_evolution_cases(source)
        self.assertEqual(130, len(cases))
        validation_repositories = {
            case["repository"] for case in cases if case["split"] == "validation"
        }
        holdout_repositories = {
            case["repository"] for case in cases if case["split"] == "holdout"
        }
        self.assertEqual(8, len(validation_repositories))
        self.assertEqual(2, len(holdout_repositories))
        self.assertFalse(validation_repositories & holdout_repositories)

        with tempfile.TemporaryDirectory() as directory:
            dataset_path = os.path.join(directory, "cases.jsonl")
            database_path = os.path.join(directory, "proof.db")
            write_jsonl(cases, dataset_path)
            report = run_prompt_evolution_proof(dataset_path, database_path)

        self.assertEqual("awaiting_approval", report["evolution_run"]["decision"])
        self.assertEqual(32, report["feedback"]["missed_findings"])
        self.assertGreater(
            report["validation"]["candidate"]["f1"],
            report["validation"]["baseline"]["f1"],
        )
        self.assertGreater(
            report["holdout"]["candidate"]["f1"],
            report["holdout"]["baseline"]["f1"],
        )
        self.assertTrue(report["release_gate"]["quantitative_passed"])
        self.assertTrue(report["release_gate"]["human_approval_required"])
        self.assertFalse(report["release_gate"]["production_activation_allowed"])


if __name__ == "__main__":
    unittest.main()
