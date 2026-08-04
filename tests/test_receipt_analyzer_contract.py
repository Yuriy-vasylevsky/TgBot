import ast
import inspect
import unittest
from pathlib import Path

from services.receipt_analyzer import analyze_receipt_with_openai


class ReceiptAnalyzerContractTests(unittest.TestCase):
    def test_wallet_call_matches_analyzer_signature(self):
        project_root = Path(__file__).resolve().parents[1]
        wallet_tree = ast.parse(
            (project_root / "handlers" / "wallet.py").read_text(encoding="utf-8")
        )
        calls = [
            node
            for node in ast.walk(wallet_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "analyze_receipt_with_openai"
        ]
        self.assertEqual(len(calls), 1)

        passed_keywords = {keyword.arg for keyword in calls[0].keywords if keyword.arg}
        signature = inspect.signature(analyze_receipt_with_openai)
        accepted_keywords = set(signature.parameters)
        required_keywords = {
            name
            for name, parameter in signature.parameters.items()
            if parameter.default is inspect.Parameter.empty
        }

        self.assertEqual(passed_keywords, required_keywords)
        self.assertLessEqual(passed_keywords, accepted_keywords)


if __name__ == "__main__":
    unittest.main()
