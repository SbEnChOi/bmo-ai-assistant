import os
import types
import unittest
from unittest.mock import patch

from bmo.config import api_key


class PublicConfigTests(unittest.TestCase):
    def test_missing_local_file_uses_environment(self):
        missing = ModuleNotFoundError("No local configuration", name="bmo.private_config")
        with patch.dict(os.environ, {"BMO_CONFIG_TEST_KEY": " environment-test "}):
            with patch("importlib.import_module", side_effect=missing):
                self.assertEqual(api_key("BMO_CONFIG_TEST_KEY"), "environment-test")

    def test_local_value_precedes_environment_and_empty_falls_back(self):
        local = types.SimpleNamespace(BMO_CONFIG_TEST_KEY=" local-test ")
        with patch.dict(os.environ, {"BMO_CONFIG_TEST_KEY": "environment-test"}):
            with patch("importlib.import_module", return_value=local):
                self.assertEqual(api_key("BMO_CONFIG_TEST_KEY"), "local-test")
                local.BMO_CONFIG_TEST_KEY = ""
                self.assertEqual(api_key("BMO_CONFIG_TEST_KEY"), "environment-test")

    def test_broken_local_dependency_is_not_hidden(self):
        missing = ModuleNotFoundError("Missing dependency", name="missing_dependency")
        with patch("importlib.import_module", side_effect=missing):
            with self.assertRaises(ModuleNotFoundError):
                api_key("BMO_CONFIG_TEST_KEY")
