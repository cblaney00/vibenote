import sys
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sender  # noqa: E402
from store import condense  # noqa: E402

NY = ZoneInfo("America/New_York")
ONE = {"name": "Account 1", "email": "one@x", "weekday": 0, "hour": 11, "minute": 0}
TWO = {"name": "Account 2", "email": "two@x", "weekday": 3, "hour": 23, "minute": 0,
       "earlier": True}


class UsageTest(unittest.TestCase):
    def test_refresh_times(self):
        self.assertEqual(sender.parse_refresh("Thu 11pm"), {"weekday": 3, "hour": 23, "minute": 0})
        self.assertEqual(sender.parse_refresh("monday 9:30am"),
                         {"weekday": 0, "hour": 9, "minute": 30})
        self.assertIsNone(sender.parse_refresh("someday"))
        self.assertEqual(sender.refresh_text(ONE), "Mon 11am")

    def test_week_is_counted_per_account_since_its_refresh(self):
        now = datetime(2026, 11, 2, 13, 0, tzinfo=NY)  # Monday 1pm
        usage = {
            "buckets": {"2026-11-02T15": {"r62d": 1000},   # Mon 10am NY: before acct 1's refresh
                        "2026-11-02T17": {"r62d": 2000},   # Mon 12pm NY: after it
                        "2026-10-31T15": {"glade": 500}},  # Sat: account 2's week
            "logins": [["2026-11-02T16:30:00+00:00", "one@x"]],
        }
        r = sender.usage_report(usage, [ONE, TWO], now=now)
        one, two = r["accounts"]
        self.assertEqual(one["used"], 2000)
        self.assertEqual(one["projects"], {"r62d": 2000})
        # before the first login seen, chats count as the "earlier" account
        self.assertEqual(r["accounts"][1]["used"], 1500)
        # account 2's week ends first (Thu), so use it first
        self.assertEqual(r["use_now"], "Account 2")
        # a request about to be made counts on the account logged in now
        self.assertEqual(sender.usage_report(usage, [ONE, TWO], now=now, extra=500)
                         ["accounts"][0]["used"], 2500)

    def test_condense_keeps_meaning_drops_filler(self):
        self.assertEqual(condense("i think the footsteps should just be really quiet, dont make them clanky"),
                         "The footsteps should be quiet, don't make them clanky")
        self.assertEqual(condense("there should be a minimap"), "Add a minimap")
        self.assertEqual(condense("make sure the sheild works"), "Ensure the shield works")

    def test_snapshot_line(self):
        line = sender.snapshot_line({"at": "2026-11-02T11:24-05:00", "branch": "main",
                                     "commit": "a1b2c3d", "subject": "Fix shield walk",
                                     "changed": 3, "claude": {"now": "Ranked mode", "title": "x",
                                                              "said": "", "working": True}})
        self.assertEqual(line, "2 Nov 11:24 · main a1b2c3d “Fix shield walk” · "
                               "3 files changed since · Claude: Ranked mode")


if __name__ == "__main__":
    unittest.main()
