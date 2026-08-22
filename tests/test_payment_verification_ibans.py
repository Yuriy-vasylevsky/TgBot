import tempfile
import unittest
from pathlib import Path

import aiosqlite

import db.admin as admin_db


def make_iban(country: str, bban: str) -> str:
    provisional = f"{country}00{bban}"
    rearranged = provisional[4:] + provisional[:4]
    numeric = "".join(
        character if character.isdigit() else str(ord(character) - ord("A") + 10)
        for character in rearranged
    )
    return f"{country}{98 - int(numeric) % 97:02d}{bban}"


class PaymentVerificationIbanTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = admin_db.DB_PATH
        admin_db.DB_PATH = Path(self.temp_dir.name) / "ibans.db"
        async with aiosqlite.connect(admin_db.DB_PATH) as db:
            await db.execute(
                """
                CREATE TABLE cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bank_name TEXT,
                    display_name TEXT,
                    card_number TEXT
                )
                """
            )
            await db.execute(
                "INSERT INTO cards(bank_name, display_name, card_number) "
                "VALUES ('Карта 1', 'Абанк', '4323357031732296')"
            )
            await db.commit()
        self.iban = make_iban("UA", "1234567890123456789012345")

    async def asyncTearDown(self):
        admin_db.DB_PATH = self.old_db_path
        self.temp_dir.cleanup()

    async def test_add_normalize_list_and_delete_hidden_iban(self):
        spaced = " ".join(
            self.iban[index:index + 4]
            for index in range(0, len(self.iban), 4)
        ).lower()
        added = await admin_db.add_payment_verification_iban(spaced)

        self.assertTrue(added["ok"])
        self.assertEqual(added["iban"], self.iban)
        self.assertEqual(
            await admin_db.get_payment_verification_ibans(),
            [(added["id"], self.iban)],
        )
        self.assertEqual(await admin_db.get_cards(), [("Абанк", "4323357031732296")])

        duplicate = await admin_db.add_payment_verification_iban(self.iban)
        self.assertEqual(duplicate["reason"], "exists")
        self.assertTrue(await admin_db.delete_payment_verification_iban(added["id"]))
        self.assertEqual(await admin_db.get_payment_verification_ibans(), [])

    async def test_invalid_iban_is_rejected(self):
        invalid = await admin_db.add_payment_verification_iban(
            self.iban[:-1] + ("0" if self.iban[-1] != "0" else "1")
        )

        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["reason"], "invalid")
        self.assertEqual(await admin_db.get_payment_verification_ibans(), [])


if __name__ == "__main__":
    unittest.main()
