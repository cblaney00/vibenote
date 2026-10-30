import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import projects  # noqa: E402

R62D_STYLE = """# r6-todo — ideas

Intro text.

## To do
- [ ] First idea
- [ ] Second idea


## Done

- [x] Old thing
"""

GLADE_STYLE = """# Glade things to do

Intro.

## To do

(nothing waiting: ask him what's next)

## Done

- 2026-10-30: something
"""


class ProjectsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    def make(self, slug, marker, todo=None, todo_name="docs/todo.md"):
        d = self.base / slug
        (d / "docs").mkdir(parents=True)
        (d / ".vibe-project").write_text(marker)
        if todo is not None:
            (d / todo_name).write_text(todo)
        return d

    def test_finds_projects_but_not_itself(self):
        self.make("r62d", "title=R62D\nshell=vibe-web\n")
        self.make("sub-of-seas", "title=sub-of-seas (the co-op WWII submarine game)\nkind=game\n"
                  "shared=landonreekstin/sub-of-seas\n")
        self.make("vibenote", "title=VibeNote\n")
        found = projects.find_projects(self.base)
        self.assertEqual([(p.slug, p.title, p.kind) for p in found],
                         [("r62d", "R62D", "app"), ("sub-of-seas", "Sub of Seas", "game")])
        self.assertEqual(found[1].shared, "landonreekstin/sub-of-seas")

    def test_adds_to_existing_list_under_to_do(self):
        self.make("r62d", "title=R62D\n", R62D_STYLE, "r6-todo.md")
        p = projects.find_projects(self.base)[0]
        self.assertEqual(p.todo_items(), ["First idea", "Second idea"])
        f = p.add_to_todo(["Third idea", "Fourth idea"])
        self.assertEqual(f.name, "r6-todo.md")
        self.assertEqual(p.todo_items(), ["First idea", "Second idea", "Third idea", "Fourth idea"])
        text = f.read_text()
        self.assertIn("- [ ] Fourth idea\n\n## Done", text)
        self.assertIn("- [x] Old thing", text)

    def test_placeholder_is_replaced(self):
        self.make("glade", "title=Glade\n", GLADE_STYLE)
        p = projects.find_projects(self.base)[0]
        p.add_to_todo(["Squid hats"])
        text = p.todo_file().read_text()
        self.assertNotIn("nothing waiting", text)
        self.assertIn("## To do\n\n- [ ] Squid hats\n\n## Done", text)

    def test_makes_a_list_when_there_is_none(self):
        self.make("sub-of-seas", "title=sub-of-seas\nkind=game\n")
        p = projects.find_projects(self.base)[0]
        self.assertIsNone(p.todo_file())
        p.add_to_todo(["Louder sonar"])
        self.assertEqual(p.todo_file(), self.base / "sub-of-seas" / "docs" / "todo.md")
        self.assertEqual(p.todo_items(), ["Louder sonar"])


if __name__ == "__main__":
    unittest.main()
