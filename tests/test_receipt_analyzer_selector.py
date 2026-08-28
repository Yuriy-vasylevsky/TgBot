import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import services.receipt_analyzer as receipt_analyzer


class ReceiptAnalyzerSelectorTests(unittest.TestCase):
    def test_default_is_gpt_and_admin_choice_is_persisted_without_credentials(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            settings_file = Path(temporary_directory) / "receipt_analyzer_settings.json"
            with patch.object(
                receipt_analyzer,
                "_RECEIPT_ANALYZER_SETTINGS_FILE",
                settings_file,
            ):
                self.assertEqual(
                    receipt_analyzer.get_receipt_analyzer(),
                    receipt_analyzer.RECEIPT_ANALYZER_OPENAI,
                )
                receipt_analyzer.set_receipt_analyzer(
                    receipt_analyzer.RECEIPT_ANALYZER_DEEPSEEK
                )
                self.assertEqual(
                    receipt_analyzer.get_receipt_analyzer(),
                    receipt_analyzer.RECEIPT_ANALYZER_DEEPSEEK,
                )
                self.assertEqual(
                    json.loads(settings_file.read_text(encoding="utf-8")),
                    {"receipt_analyzer": receipt_analyzer.RECEIPT_ANALYZER_DEEPSEEK},
                )

    def test_unknown_analyzer_is_rejected(self):
        with self.assertRaises(ValueError):
            receipt_analyzer.set_receipt_analyzer("unsupported")
