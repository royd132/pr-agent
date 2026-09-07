import os
import tempfile
import unittest
from unittest.mock import patch

from evoagent.config import Settings, load_dotenv


class DotenvTests(unittest.TestCase):
    def test_diffprism_environment_takes_precedence(self):
        values = {
            "DIFFPRISM_PORT": "9001",
            "EVOAGENT_PORT": "9002",
            "DIFFPRISM_LLM_PROVIDER": "local",
        }
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(9001, Settings.from_env().port)

    def test_legacy_environment_remains_supported(self):
        with patch.dict(os.environ, {"EVOAGENT_PORT": "9003"}, clear=True):
            self.assertEqual(9003, Settings.from_env().port)

    def test_empty_preferred_value_falls_back_to_legacy(self):
        values = {"DIFFPRISM_PORT": "", "EVOAGENT_PORT": "9004"}
        with patch.dict(os.environ, values, clear=True):
            self.assertEqual(9004, Settings.from_env().port)

    def test_loads_valid_assignments_and_quoted_values(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("# comment\n")
            handle.write("export EVOAGENT_LLM_PROVIDER=deepseek\n")
            handle.write('EVOAGENT_DEEPSEEK_API_KEY="test-key"\n')
            handle.write("invalid line\n")
            path = handle.name
        try:
            with patch.dict(os.environ, {}, clear=True):
                load_dotenv([path])
                self.assertEqual("deepseek", os.environ["EVOAGENT_LLM_PROVIDER"])
                self.assertEqual("test-key", os.environ["EVOAGENT_DEEPSEEK_API_KEY"])
        finally:
            os.unlink(path)

    def test_process_environment_has_priority(self):
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
            handle.write("EVOAGENT_LLM_PROVIDER=deepseek\n")
            path = handle.name
        try:
            with patch.dict(os.environ, {"EVOAGENT_LLM_PROVIDER": "custom"}, clear=True):
                load_dotenv([path])
                self.assertEqual("custom", os.environ["EVOAGENT_LLM_PROVIDER"])
        finally:
            os.unlink(path)
