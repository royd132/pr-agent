import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class WebUiTests(unittest.TestCase):
    def test_diffprism_navigation_and_workspace_exist(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("DiffPrism", html)
        self.assertIn('data-view="inbox"', html)
        self.assertIn('id="review-workspace"', html)
        self.assertIn('id="benchmark-summary"', html)

    def test_structured_renderer_replaces_raw_task_json(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn("function renderReviewWorkspace", script)
        self.assertIn("function findingCard", script)
        self.assertNotIn('$("#task-report").textContent = formatJson(task)', script)

    def test_diagnostic_json_is_collapsed_and_ui_is_dependency_free(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<details id="diagnostic-json"', html)
        self.assertNotIn("<script src=\"http", html)


if __name__ == "__main__":
    unittest.main()
