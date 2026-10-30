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


if __name__ == "__main__":
    unittest.main()
