import subprocess
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

ROADMAP = """# Roadmap

## M1 — First dive
- [x] Greybox interior
- [ ] Played by hand

## M8 — Blaney's list (2026-10-29)
Added by Blaney after playing.
- [x] **Pause menu**: Esc brings up
      a menu.
- [ ] **Portholes**: windows to look out of.

## M9 — Lando's list
- [ ] Lando's thing
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

    def test_finds_projects_including_itself(self):
        self.make("r62d", "title=R62D\nshell=vibe-web\n")
        self.make("sub-of-seas", "title=sub-of-seas (the co-op WWII submarine game)\nkind=game\n"
                  "shared=landonreekstin/sub-of-seas\n")
        self.make("vibenote", "title=VibeNote\n")
        found = projects.find_projects(self.base)
        self.assertEqual([(p.slug, p.title, p.kind) for p in found],
                         [("r62d", "R62D", "app"), ("sub-of-seas", "Sub of Seas", "game"),
                          ("vibenote", "VibeNote", "app")])
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

    def test_remove_from_list_for_later(self):
        todo = R62D_STYLE.replace("- [ ] Second idea\n",
                                  "- [ ] Long one\n      carried on here.\n- [ ] Second idea\n")
        self.make("r62d", "title=R62D\n", todo, "r6-todo.md")
        p = projects.find_projects(self.base)[0]
        self.assertTrue(p.remove_from_todo("Long one carried on here."))
        self.assertTrue(p.remove_from_todo("first idea"))
        self.assertFalse(p.remove_from_todo("Old thing"))  # finished: left alone
        self.assertEqual(p.todo_items(), ["Second idea"])
        self.assertIn("- [x] Old thing", p.todo_file().read_text())

    def test_reads_finished_items(self):
        self.make("r62d", "title=R62D\n", R62D_STYLE + "- [x] Long one\n      carried on here.\n",
                  "r6-todo.md")
        self.make("glade", "title=Glade\n", GLADE_STYLE)
        r, g = sorted(projects.find_projects(self.base), key=lambda p: p.slug, reverse=True)
        self.assertEqual(r.done_items(), ["Old thing", "Long one carried on here."])
        self.assertEqual(g.done_items(), ["something"])
        self.assertEqual(g.todo_items(), [])

    def test_no_list_reads_as_none(self):
        self.make("prin-rpg", "title=prin-rpg\n")
        self.assertIsNone(projects.find_projects(self.base)[0].todo_items())

    def test_his_section_of_a_roadmap(self):
        self.make("sub-of-seas", "title=sub-of-seas\nkind=game\n", ROADMAP, "docs/roadmap.md")
        p = projects.find_projects(self.base)[0]
        self.assertEqual(p.todo_file().name, "roadmap.md")
        self.assertEqual(p.todo_items(), ["Portholes: windows to look out of."])
        self.assertEqual(p.done_items(), ["Pause menu: Esc brings up a menu."])
        p.add_to_todo(["Coral reef"])
        text = p.todo_file().read_text()
        self.assertIn("- [ ] Coral reef\n\n## M9", text)
        self.assertIn("- [ ] Lando's thing", text)
        self.assertNotIn("Lando's thing", p.todo_items())

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

    def test_finished_ticks_it(self):
        self.make("r62d", "title=R62D\n", R62D_STYLE, "r6-todo.md")
        p = projects.find_projects(self.base)[0]
        self.assertTrue(p.finish_in_todo("second idea"))
        self.assertFalse(p.finish_in_todo("Old thing"))
        self.assertEqual(p.todo_items(), ["First idea"])
        self.assertIn("Second idea", p.done_items())

    def test_claudes_notes_under_an_item_still_match(self):
        todo = R62D_STYLE.replace("- [ ] Second idea\n",
                                  "- [ ] Second idea\n      *(Redone: quieter. Left open.)*\n")
        self.make("r62d", "title=R62D\n", todo, "r6-todo.md")
        p = projects.find_projects(self.base)[0]
        self.assertTrue(p.finish_in_todo("Second idea"))

    def test_shared_game_finished_on_a_branch_is_up_for_review(self):
        d = self.make("sub-of-seas", "title=sub-of-seas\nkind=game\nshared=lando/sub\n",
                      ROADMAP, "docs/roadmap.md")

        def git(*args):
            subprocess.run(["git", "-C", str(d), "-c", "user.name=t", "-c", "user.email=t@t",
                            *args], check=True, capture_output=True)
        git("init", "-b", "main")
        git("add", ".")
        git("commit", "-m", "list")
        git("checkout", "-b", "blaney/portholes")
        roadmap = d / "docs" / "roadmap.md"
        roadmap.write_text(roadmap.read_text().replace(
            "- [ ] **Portholes**: windows to look out of.",
            "- [x] **Portholes**: windows to look out of.\n      *(Done: three of them.)*"))
        git("commit", "-am", "portholes")
        git("checkout", "main")
        p = projects.find_projects(self.base)[0]
        open_items, done, review = p.read()
        self.assertEqual(open_items, [])
        self.assertEqual(done, ["Pause menu: Esc brings up a menu."])
        self.assertEqual(len(review), 1)
        self.assertTrue(review[0].startswith("Portholes"))
        git("merge", "blaney/portholes")  # lando merged it
        self.assertEqual(p.read()[2], [])
        self.assertEqual(len(p.read()[1]), 2)

    def test_not_shared_has_no_review(self):
        self.make("r62d", "title=R62D\n", R62D_STYLE, "r6-todo.md")
        self.assertEqual(projects.find_projects(self.base)[0].read()[2], [])


if __name__ == "__main__":
    unittest.main()
