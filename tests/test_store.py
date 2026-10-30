import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from store import Store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "notes.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_notes_survive_a_restart(self):
        s = Store(self.path)
        s.add("r62d", "  smaller   bullets ")
        s.add("r62d", "desert map")
        s.add("sub-of-seas", "torpedo sound")
        again = Store(self.path)
        self.assertEqual([n["text"] for n in again.get("r62d")], ["smaller bullets", "desert map"])
        self.assertEqual(len(again.get("sub-of-seas")), 1)
        self.assertEqual(again.get("glade"), [])

    def test_blank_note_is_ignored(self):
        self.assertIsNone(Store(self.path).add("r62d", "   "))

    def test_edit_move_delete(self):
        s = Store(self.path)
        a = s.add("r62d", "a")
        b = s.add("r62d", "b")
        s.edit("r62d", a["id"], "a2")
        s.move("r62d", b["id"], "glade")
        self.assertEqual([n["text"] for n in s.get("r62d")], ["a2"])
        self.assertEqual([n["text"] for n in s.get("glade")], ["b"])
        s.edit("r62d", a["id"], "  ")  # emptied = deleted
        self.assertEqual(s.get("r62d"), [])

    def test_first_look_imports_the_whole_list(self):
        s = Store(self.path)
        self.assertTrue(s.sync("r62d", ["Small bullets", "Desert map"], ["Headshots", "Barricades"]))
        self.assertEqual([n["text"] for n in s.get("r62d", "sent")], ["Small bullets", "Desert map"])
        self.assertEqual([n["text"] for n in s.get("r62d", "done")], ["Headshots", "Barricades"])
        self.assertNotIn("sent", s.get("r62d", "sent")[0])  # no made-up date
        # Looking again changes nothing, and finished items are not brought in twice
        self.assertFalse(Store(self.path).sync("r62d", ["Small bullets", "Desert map"],
                                               ["Headshots", "Barricades"]))

    def test_sent_then_finished(self):
        s = Store(self.path)
        s.sync("r62d", [], [])
        a = s.add("r62d", "Louder stairs")
        s.mark_sent("r62d", [a["id"]])
        self.assertFalse(s.sync("r62d", ["louder  stairs"], []))  # still on the list
        self.assertTrue(s.sync("r62d", [], []))                   # Claude finished it
        self.assertEqual(s.get("r62d", "done")[0]["text"], "Louder stairs")
        self.assertIn("done", s.get("r62d", "done")[0])

    def test_added_in_a_chat_counts_as_sent(self):
        s = Store(self.path)
        s.sync("glade", [], [])
        s.sync("glade", ["Squid hats"], [])
        self.assertEqual(s.get("glade", "sent")[0]["text"], "Squid hats")
        self.assertIn("sent", s.get("glade", "sent")[0])

    def test_missing_list_finishes_nothing(self):
        s = Store(self.path)
        s.sync("sub-of-seas", ["Sonar"], [])
        self.assertFalse(s.sync("sub-of-seas", None, []))
        self.assertEqual(len(s.get("sub-of-seas", "sent")), 1)

    def test_ticks(self):
        s = Store(self.path)
        a = s.add("r62d", "a")
        b = s.add("r62d", "b")
        self.assertTrue(a["send"])
        self.assertFalse(a["work"])
        s.tick("r62d", [b["id"]], "send", False)
        s.tick("r62d", [a["id"], b["id"]], "work", True)
        again = Store(self.path)
        self.assertEqual([n["send"] for n in again.get("r62d")], [True, False])
        again.mark_worked("r62d", [a["id"]])
        self.assertEqual([n["work"] for n in again.get("r62d")], [False, True])
        self.assertIn("worked", again.get("r62d")[0])


if __name__ == "__main__":
    unittest.main()
