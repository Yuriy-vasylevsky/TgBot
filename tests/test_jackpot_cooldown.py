import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

from db import jackpot_cooldown


class JackpotCooldownTests(unittest.IsolatedAsyncioTestCase):
    async def test_cooldown_is_persisted_for_12_hours(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "jackpot.sqlite3"
            now = datetime(2026, 8, 18, 12, 0, tzinfo=ZoneInfo("Europe/Kyiv"))

            with (
                patch.object(jackpot_cooldown, "DB_PATH", str(db_path)),
                patch.object(jackpot_cooldown, "_now_kyiv", return_value=now),
            ):
                await jackpot_cooldown.set_jackpot_cooldown(101)
                remaining = await jackpot_cooldown.get_jackpot_cooldown_remaining(101)
                active = await jackpot_cooldown.is_jackpot_on_cooldown(101)

            self.assertEqual(remaining, (12, 0))
            self.assertTrue(active)


if __name__ == "__main__":
    unittest.main()
