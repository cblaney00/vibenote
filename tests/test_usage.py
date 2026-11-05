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



class TipsTest(unittest.TestCase):
    def test_tips_from_his_chats_and_general_ones(self):
        usage = {"batches": [{"items": ["a"], "tokens": 20000}] * 3
                 + [{"items": ["a", "b", "c", "d"], "tokens": 20000}] * 3,
                 "chats": {"x": {"project": "r62d", "context": 900_000}},
                 "hits": [{"type": "five_hour", "at": "2026-11-03T01:00:00Z"}]}
        tips = sender.token_tips(usage, sender.TokenGuess(usage), lambda s: s.upper())
        self.assertIn("several items at once", tips[0])
        self.assertIn("R62D", tips[1])
        self.assertIn("5-hour limit 1 times", tips[2])
        self.assertTrue(any("Send is free" in t for t in tips))
        self.assertTrue(sender.token_tips(None, sender.TokenGuess(None)))  # nothing learned yet

    def test_an_empty_collection_never_wipes_the_saved_one(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "usage.json"
            good = {"hours": {"3": [5, 100.0]}}
            self.assertTrue(sender.save_if_better(good, None, path))
            self.assertFalse(sender.save_if_better({"hours": {"3": [0, 0.0]}}, good, path))
            self.assertEqual(sender.load_saved_usage(path), good)


class FreshChatTest(unittest.TestCase):
    NOW = datetime(2026, 11, 2, 20, 0, tzinfo=ZoneInfo("UTC"))

    def chat(self, size, minutes_ago):
        at = self.NOW.timestamp() - minutes_ago * 60
        return {"context": size, "at": datetime.fromtimestamp(at, ZoneInfo("UTC")).isoformat()}

    def test_short_recent_chat_carries_on(self):
        self.assertIsNone(sender.fresh_reason(self.chat(90_000, 10), self.NOW))
        self.assertIsNone(sender.fresh_reason(self.chat(150_000, 30), self.NOW))
        self.assertIsNone(sender.fresh_reason(None, self.NOW))

    def test_long_chat_starts_fresh(self):
        self.assertIn("long", sender.fresh_reason(self.chat(400_000, 5), self.NOW))

    def test_fairly_long_idle_chat_starts_fresh(self):
        self.assertIn("idle", sender.fresh_reason(self.chat(150_000, 90), self.NOW))
        self.assertIsNone(sender.fresh_reason(self.chat(80_000, 300), self.NOW))

if __name__ == "__main__":
    unittest.main()
