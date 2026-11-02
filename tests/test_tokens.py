import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import sender  # noqa: E402
from store import size_score  # noqa: E402

BUSY = datetime(2026, 11, 2, 10, 0, tzinfo=ZoneInfo("America/New_York"))   # Monday 10am
QUIET = datetime(2026, 11, 2, 22, 0, tzinfo=ZoneInfo("America/New_York"))  # Monday 10pm


def reply(ts, out, msg_id):
    return {"type": "assistant", "timestamp": ts, "requestId": "r" + msg_id,
            "message": {"id": msg_id, "usage": {"input_tokens": 0, "output_tokens": out,
                                                "cache_read_input_tokens": 10_000}}}


class TokenTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        chat = Path(self.dir.name) / "-home-x-projects-r62d" / "a.jsonl"
        chat.parent.mkdir()
        lines = [
            reply("2026-10-31T01:00:00Z", 500, "m0"),  # before Work: not in the batch
            {"type": "user", "timestamp": "2026-10-31T01:01:00Z", "message": {
                "content": sender.WORK_START + " for R62D.\n\nThe items:\n1. fix the typo\n"
                                               "2. add a new level with a boss"}},
            reply("2026-10-31T01:02:00Z", 1000, "m1"),
            reply("2026-10-31T01:02:00Z", 1000, "m1"),  # the same reply written twice
            reply("2026-10-31T01:03:00Z", 2000, "m2"),
        ]
        chat.write_text("\n".join(json.dumps(x) for x in lines))
        self.usage = sender.collect_usage(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    def test_work_batch_is_measured(self):
        [batch] = self.usage["batches"]
        self.assertEqual(batch["items"], ["fix the typo", "add a new level with a boss"])
        self.assertEqual(batch["tokens"], 1000 + 2000)  # only what Claude wrote, once each

    def test_guess_learns_from_batches(self):
        guess = sender.TokenGuess(self.usage)
        points = size_score("fix the typo") + size_score("add a new level with a boss")
        self.assertAlmostEqual(guess.per_point, 3000 / points)
        self.assertEqual(guess.learned, 1)
        # learned for that project; another project uses the overall rate
        self.assertEqual(guess.per_project, {"r62d": 3000 / points})
        self.assertEqual(guess.tokens(2, QUIET, "r62d"), round(2 * 3000 / points))

    def test_guess_without_data(self):
        guess = sender.TokenGuess(None)
        self.assertEqual(guess.tokens(2, QUIET), 2 * sender.TokenGuess.PER_POINT)

    def test_busy_hours_cost_more(self):
        guess = sender.TokenGuess(None)
        self.assertEqual(guess.tokens(2, BUSY), round(2 * sender.TokenGuess.PER_POINT
                                                      * sender.TokenGuess.BUSY_GUESS))
        # learned: 5-hour limits hit in busy hours held half as much
        fills = [{"at": "2026-11-02T18:00:00Z", "tokens": 100},   # Mon, window 8am-1pm NY
                 {"at": "2026-11-03T18:00:00Z", "tokens": 100},
                 {"at": "2026-11-01T03:00:00Z", "tokens": 200},   # Sat night
                 {"at": "2026-11-04T04:00:00Z", "tokens": 200}]   # Tue night
        guess = sender.TokenGuess({"five_hour_fills": fills})
        self.assertTrue(guess.busy_learned)
        self.assertEqual(guess.busy_factor, 2.0)
        self.assertEqual(guess.factor(QUIET), 1.0)

    def test_short_tokens(self):
        self.assertEqual(sender.short_tokens(59_400), "~59k")
        self.assertEqual(sender.short_tokens(1_250_000), "~1.2M")

    def test_sign(self):
        guess = sender.TokenGuess(None)
        busy = datetime(2026, 11, 2, 7, 0, tzinfo=ZoneInfo("America/Los_Angeles"))  # Monday
        night = datetime(2026, 11, 2, 23, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        weekend = datetime(2026, 11, 1, 7, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        self.assertEqual(sender.good_time(guess, busy)[0], "bad")
        self.assertEqual(sender.good_time(guess, night)[0], "good")
        self.assertEqual(sender.good_time(guess, weekend)[0], "good")


if __name__ == "__main__":
    unittest.main()
