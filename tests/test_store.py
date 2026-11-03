import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from store import Store, size_label, size_score  # noqa: E402


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

    def test_later_and_back(self):
        s = Store(self.path)
        s.sync("r62d", [], [])
        a = s.add("r62d", "Big new map")
        b = s.add("r62d", "Louder stairs")
        s.mark_sent("r62d", [b["id"]])
        s.tick("r62d", [b["id"]], "work", True)
        s.later("r62d", a["id"])
        s.later("r62d", b["id"])
        self.assertEqual(s.get("r62d"), [])
        self.assertEqual(s.get("r62d", "sent"), [])
        self.assertFalse(s.get("r62d", "later")[1]["work"])
        # still listed on another branch: not brought back as sent, and not finished
        self.assertFalse(s.sync("r62d", ["Louder stairs"], []))
        s.organize("r62d")
        self.assertEqual(len(s.get("r62d", "later")), 2)  # Organize keeps them
        s.now("r62d", a["id"])
        self.assertEqual(s.get("r62d")[0]["text"], "Big new map")
        self.assertTrue(s.get("r62d")[0]["send"])

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

    def test_size_guess(self):
        self.assertEqual(size_label(size_score("fix the typo in the title")), "Small")
        self.assertEqual(size_label(size_score("make the trees a bit darker")), "Small")
        self.assertEqual(size_label(size_score("add a pause menu")), "Medium")
        self.assertEqual(size_label(size_score("add a new level with a boss")), "Big")
        self.assertEqual(size_label(size_score(
            "redo the whole save system and add multiplayer")), "Big")

    def test_organize_sorts_smallest_first_and_keeps_done_alone(self):
        s = Store(self.path)
        s.sync("r62d", ["add a new level with a boss", "typo in title"], ["old thing"])
        s.add("r62d", "redo the whole save system")
        s.add("r62d", "darker trees")
        s.add("r62d", "add a pause menu")
        s.organize("r62d")
        again = Store(self.path)
        self.assertEqual([n["text"] for n in again.get("r62d")],
                         ["darker trees", "add a pause menu", "redo the whole save system"])
        self.assertEqual([n["text"] for n in again.get("r62d", "sent")],
                         ["typo in title", "add a new level with a boss"])
        done = again.get("r62d", "done")
        self.assertEqual([n["text"] for n in done], ["old thing"])
        self.assertNotIn("size", done[0])

    def test_organize_groups_related_notes(self):
        s = Store(self.path)
        for text in ["footsteps are too loud", "wraith's scanner should be toggle",
                     "add a sea shanty song", "fix the tutorial", "wraith needs a buff",
                     "the tutorial is too long"]:
            s.add("sub", text)
        s.organize("sub")
        groups = {}
        for n in s.get("sub"):
            groups.setdefault(n["group"], []).append(n["text"])
        self.assertEqual(sorted(groups["Sound"]), ["add a sea shanty song",
                                                   "footsteps are too loud"])
        self.assertEqual(sorted(groups["Tutorial"]), ["fix the tutorial",
                                                      "the tutorial is too long"])
        self.assertEqual(sorted(groups["Wraith"]), ["wraith needs a buff",
                                                    "wraith's scanner should be toggle"])
        # each group's notes sit together in the list
        order = [n["group"] for n in s.get("sub")]
        changes = sum(a != b for a, b in zip(order, order[1:]))
        self.assertEqual(changes, len(set(order)) - 1)

    def test_notes_sharing_nothing_go_last(self):
        s = Store(self.path)
        for text in ["glint cannot sonar pulse up stairs", "footsteps too loud",
                     "music is too quiet"]:
            s.add("x", text)
        s.organize("x")
        self.assertEqual([n["group"] for n in s.get("x")], ["Sound", "Sound", "On their own"])

    def test_editing_an_organized_note_updates_its_size(self):
        s = Store(self.path)
        n = s.add("r62d", "typo")
        s.organize("r62d")
        s.edit("r62d", n["id"], "add a new level with a boss")
        self.assertEqual(size_label(s.get("r62d")[0]["size"]), "Big")


if __name__ == "__main__":
    unittest.main()
