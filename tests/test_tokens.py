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
        k = sender.TokenGuess.GROWTH  # too few batches to learn how cost grows
        self.assertAlmostEqual(guess.per_point, 3000 / points ** k)
        self.assertEqual(guess.learned, 1)
        # learned for that project; another project uses the overall rate
        self.assertAlmostEqual(guess.per_project["r62d"], 3000 / points ** k)
        self.assertEqual(guess.batch([size_score("fix the typo"),
                                      size_score("add a new level with a boss")],
                                     QUIET, "r62d"), 3000)  # the same batch again: same cost
        self.assertEqual(guess.tokens(2, QUIET, "r62d"), round(3000 / points ** k * 2 ** k))

    def test_guess_without_data(self):
        guess = sender.TokenGuess(None)
        self.assertEqual(guess.tokens(1, QUIET), sender.TokenGuess.PER_POINT)
        self.assertEqual(guess.batch([], QUIET), 0)

    def test_many_notes_cost_far_less_than_their_sum(self):
        """His catch, 2026-11-26: a job guessed ~17m used ~1.5m, as each note's guess was
        added up. A batch grows with about the square root of its size."""
        guess = sender.TokenGuess(None)
        one = guess.tokens(3, QUIET)
        forty = guess.batch([3] * 40, QUIET)
        self.assertLess(forty, 40 * one / 4)
        self.assertGreater(forty, one)
        shares = guess.shares({"a": 1, "b": 3}, QUIET)
        self.assertAlmostEqual(sum(shares.values()), guess.batch([1, 3], QUIET), delta=1)
        self.assertEqual(shares["b"], 3 * shares["a"])

    def test_growth_and_project_rate_are_learned(self):
        def b(project, n, tokens):
            return {"project": project, "items": ["fix the typo"] * n, "tokens": tokens}
        s = size_score("fix the typo")
        # batches whose cost grows as size^0.7: that is what gets learned
        batches = [b("glade", n, round(1000 * (n * s) ** 0.7)) for n in (1, 2, 4, 8, 16, 32)]
        guess = sender.TokenGuess({"batches": batches})
        self.assertAlmostEqual(guess.growth, 0.7, places=2)
        self.assertAlmostEqual(guess.per_point, 1000, delta=5)
        # one odd batch can't make a project's guesses ten times the rest
        guess = sender.TokenGuess({"batches": batches + [b("vibenote", 1, 10 * round(1000 * s ** 0.7))]})
        self.assertLess(guess.per_project["vibenote"], 2 * 3 * guess.per_point)
        self.assertGreater(guess.per_project["vibenote"], guess.per_point)

    def test_busy_hours_cost_more(self):
        guess = sender.TokenGuess(None)
        self.assertEqual(guess.tokens(1, BUSY), round(sender.TokenGuess.PER_POINT
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


class GuessedUsedTest(unittest.TestCase):
    """Each worked-on note: VibeNote's guess beside what it really used (2026-11-09)."""

    def batch(self, started, items, tokens, plan=False, project="r62d"):
        return {"items": items, "tokens": tokens, "started": started, "project": project,
                "plan": plan}

    def test_plan_mode_is_noted(self):
        with tempfile.TemporaryDirectory() as d:
            chat = Path(d) / "-home-x-projects-r62d" / "a.jsonl"
            chat.parent.mkdir()
            lines = [{"type": "user", "timestamp": "2026-11-09T01:00:00Z",
                      "permissionMode": "plan", "message": {
                          "content": sender.WORK_START + ".\n\nThe items:\n1. fix the typo"}},
                     reply("2026-11-09T01:02:00Z", 1000, "m1")]
            chat.write_text("\n".join(json.dumps(x) for x in lines))
            [b] = sender.collect_usage(Path(d))["batches"]
        self.assertTrue(b["plan"])

    def test_used_is_split_by_size(self):
        items = ["fix the typo", "add a new level with a boss"]
        usage = {"batches": [self.batch("2026-11-09T01:00:01Z", items, 10_000)]}
        small, big = (size_score(i) for i in items)
        note = {"text": "fix the typo", "work_at": "2026-11-09T01:00:00"}
        self.assertEqual(sender.actual_tokens(note, "r62d", usage),
                         round(10_000 * small / (small + big)))
        self.assertIsNone(sender.actual_tokens(note, "glade", usage))  # another project

    def test_used_picks_the_batch_after_work(self):
        usage = {"batches": [self.batch("2026-11-01T01:00:00Z", ["fix the typo"], 500),
                             self.batch("2026-11-09T01:00:01Z", ["fix the typo"], 900),
                             self.batch("2026-11-10T01:00:00Z", ["fix the typo"], 700)]}
        self.assertEqual(sender.actual_tokens(
            {"text": "fix the typo", "work_at": "2026-11-09T01:00:00"}, "r62d", usage), 900)
        # an older note with no time: the latest batch naming it
        self.assertEqual(sender.actual_tokens({"text": "fix the typo"}, "r62d", usage), 700)

    def test_guess_learns_from_plan_mode_once_there_are_enough(self):
        old = [self.batch("2026-11-01T01:00:00Z", ["fix the typo"], 10_000)] * 3
        planned = [self.batch("2026-11-07T01:00:00Z", ["fix the typo"], 2_000, plan=True)] * 2
        points = size_score("fix the typo")
        guess = sender.TokenGuess({"batches": old + planned})
        k = sender.TokenGuess.GROWTH
        self.assertFalse(guess.plan_mode)  # 2 is not enough yet: all batches count
        self.assertGreater(guess.per_point, 2_000 / points ** k)
        guess = sender.TokenGuess({"batches": old + planned * 2})
        self.assertTrue(guess.plan_mode)
        self.assertAlmostEqual(guess.per_point, 2_000 / points ** k)
        self.assertAlmostEqual(guess.per_project["r62d"], 2_000 / points ** k)
