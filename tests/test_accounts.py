import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sender  # noqa: E402

ONE = {"name": "Account 1", "email": "one@x", "weekday": 0, "hour": 11, "minute": 0,
       "guess": False}
TWO = {"name": "Account 2", "email": "two@x", "weekday": 3, "hour": 14, "minute": 0,
       "guess": False, "earlier": True}


class SyncAccountsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "accounts.json"
        self.path.write_text(json.dumps([ONE, TWO]))
        patch = mock.patch.object(sender, "HIS", True)
        patch.start()
        self.addCleanup(patch.stop)
        self.addCleanup(self.dir.cleanup)

    def names(self):
        return [(a["name"], a["email"]) for a in json.loads(self.path.read_text())]

    def test_new_logins_become_the_next_accounts_in_order(self):
        usage = {"logins": [["2026-11-02T17", "one@x"], ["2026-11-04T22", "three@x"],
                            ["2026-11-06T00", "two@x"], ["2026-11-10T23", "four@x"],
                            ["2026-11-11T03", "three@x"]]}
        self.assertTrue(sender.sync_accounts(usage, None, self.path))
        self.assertEqual(self.names(), [("Account 1", "one@x"), ("Account 2", "two@x"),
                                        ("Account 3", "three@x"), ("Account 4", "four@x")])
        self.assertFalse(sender.sync_accounts(usage, None, self.path))  # nothing new

    def test_logged_in_account_takes_claudes_reset_time(self):
        resets = datetime(2026, 11, 14, 4, 0).astimezone()
        live = {"email": "two@x", "week": {"percent": 85.0, "resets": resets.isoformat()}}
        self.assertTrue(sender.sync_accounts({}, live, self.path))
        two = json.loads(self.path.read_text())[1]
        self.assertEqual((two["weekday"], two["hour"], two["minute"], two["guess"]),
                         (resets.weekday(), resets.hour, resets.minute, False))
        self.assertTrue(two["earlier"])
        self.assertFalse(sender.sync_accounts({}, live, self.path))

    def test_expired_or_unknown_live_numbers_change_nothing(self):
        before = self.path.read_text()
        self.assertFalse(sender.sync_accounts({}, {"email": "one@x", "week": {"resets": None}},
                                              self.path))
        self.assertFalse(sender.sync_accounts({}, {"email": "x@y", "week": {}}, self.path))
        self.assertEqual(self.path.read_text(), before)

    def test_lando_never_gets_an_accounts_file(self):
        with mock.patch.object(sender, "HIS", False):
            self.assertFalse(sender.sync_accounts({"logins": [["t", "new@x"]]}, None, self.path))


if __name__ == "__main__":
    unittest.main()
