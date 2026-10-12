import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from db import check


class MaticCheckQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_matic_and_superomatic_but_not_champion(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            path = Path(directory) / "checks.db"
            with sqlite3.connect(path) as db:
                db.executescript(
                    "CREATE TABLE users(user_id INTEGER, full_name TEXT, username TEXT);"
                    "CREATE TABLE issued_checks(id INTEGER PRIMARY KEY, user_id INTEGER, "
                    "code TEXT, check_type TEXT);"
                    "INSERT INTO issued_checks VALUES(1,1,'11111111111111','Matic 100');"
                    "INSERT INTO issued_checks VALUES(2,2,'22222222222222','Superomatic 100');"
                    "INSERT INTO issued_checks VALUES(3,3,'33333333333333','Champion 100');"
                )
            with patch.object(check, "DB_PATH", path):
                rows = await check.get_issued_checks_with_owners("Matic")
            self.assertEqual([row["code"] for row in rows],
                             ["22222222222222", "11111111111111"])
