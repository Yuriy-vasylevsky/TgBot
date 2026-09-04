import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from handlers.casino_api import champion_yesterday_period


class ChampionPeriodTests(unittest.TestCase):
    def test_yesterday_operational_day_runs_from_seven_to_seven(self):
        now = datetime(2026, 9, 4, 15, 30, tzinfo=ZoneInfo("Europe/Kyiv"))

        start, end = champion_yesterday_period(now)

        self.assertEqual(start.strftime("%Y%m%d%H%M%S"), "20260903070000")
        self.assertEqual(end.strftime("%Y%m%d%H%M%S"), "20260904070000")


if __name__ == "__main__":
    unittest.main()
