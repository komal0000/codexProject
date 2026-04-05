from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tools.env_loader import load_env_file


class EnvLoaderTests(unittest.TestCase):
    def test_load_env_file_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "OPENROUTER_API_KEY=test-key\nOPENROUTER_MODEL='openrouter/free'\n# comment\n",
                encoding="utf-8",
            )
            original_key = os.environ.pop("OPENROUTER_API_KEY", None)
            original_model = os.environ.pop("OPENROUTER_MODEL", None)
            try:
                load_env_file(env_path)
                self.assertEqual(os.environ.get("OPENROUTER_API_KEY"), "test-key")
                self.assertEqual(os.environ.get("OPENROUTER_MODEL"), "openrouter/free")
            finally:
                if original_key is None:
                    os.environ.pop("OPENROUTER_API_KEY", None)
                else:
                    os.environ["OPENROUTER_API_KEY"] = original_key
                if original_model is None:
                    os.environ.pop("OPENROUTER_MODEL", None)
                else:
                    os.environ["OPENROUTER_MODEL"] = original_model
