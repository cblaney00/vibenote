import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from store import Store  # noqa: E402


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "lists.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_starts_with_one_list(self):
        s = Store(self.path)
        self.assertEqual([lst["name"] for lst in s.lists], ["My list"])

    def test_tasks_survive_a_restart(self):
        s = Store(self.path)
        lid = s.lists[0]["id"]
        a = s.add_task(lid, "  Buy milk ")
        s.add_task(lid, "Walk dog")
        s.toggle_task(lid, a["id"])
        again = Store(self.path)
        tasks = again.get_list(lid)["tasks"]
        self.assertEqual([t["text"] for t in tasks], ["Buy milk", "Walk dog"])
        self.assertEqual([t["done"] for t in tasks], [True, False])

    def test_blank_task_is_ignored(self):
        s = Store(self.path)
        self.assertIsNone(s.add_task(s.lists[0]["id"], "   "))

    def test_clear_done_and_delete(self):
        s = Store(self.path)
        lid = s.lists[0]["id"]
        a = s.add_task(lid, "a")
        b = s.add_task(lid, "b")
        s.add_task(lid, "c")
        s.toggle_task(lid, a["id"])
        s.clear_done(lid)
        s.delete_task(lid, b["id"])
        self.assertEqual([t["text"] for t in s.get_list(lid)["tasks"]], ["c"])

    def test_lists(self):
        s = Store(self.path)
        new = s.add_list("Shopping")
        s.rename_list(new["id"], "Groceries")
        s.rename_list(new["id"], "  ")
        self.assertEqual(s.get_list(new["id"])["name"], "Groceries")
        s.delete_list(s.lists[0]["id"])
        s.delete_list(new["id"])
        self.assertEqual(len(s.lists), 1)  # never left with no list at all


if __name__ == "__main__":
    unittest.main()
