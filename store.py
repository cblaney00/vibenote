"""Saving and loading his notes, kept per project, with their whole history. No window code here.

Every note has a status:
  waiting  written in VibeNote, not sent yet
  sent     on the project's to-do list, not finished yet
  done     gone from the to-do list (Claude finished it), or found already finished on import
  review   finished in a game shared with lando, waiting for him to merge it (his ask,
           2026-11-04): no Work tick, skipped by Work and Tick all; done once it is on main
  later    put aside in the Later box (his ask, 2026-11-02): kept off the to-do list, and
           skipped by Send, Work and Tick all, until he brings it back ("Now")
Nothing is ever forgotten unless he deletes a waiting note himself.

Two ticks per note (his ask): "send" (only ticked waiting notes are sent; new notes start
ticked) and "work" (only ticked ones are given to Claude by Work; start unticked).
"""

import json
import os
import re
import uuid
from datetime import date
from pathlib import Path


def data_file() -> Path:
    override = os.environ.get("VIBENOTE_DATA")
    if override:
        return Path(override)
    base = os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
    return Path(base) / "vibenote" / "notes.json"


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def today() -> str:
    return date.today().isoformat()


def bare(text: str) -> str:
    """His words without the *(...)* notes Claude writes under an item about what it did, so
    an item still matches itself after Claude has added one."""
    return " ".join(re.sub(r"\*\(.*?\)\*", " ", text).split()).lower()


def same(a: str, b: str) -> bool:
    return bare(a) == bare(b)


# --- how big a change is: a free rough guess, no Claude (his ask: "Organize") ---
# Words that usually mean a lot of new work for Claude (more reading and writing, so more
# tokens), and words that usually mean a quick tweak. Matched as whole words / phrases,
# each counted once. Tuned on his real notes (2026-10-30): long, detailed notes are not
# always big ones, so length only counts a little.
BIG_WORDS = [
    "new level", "new levels", "new game", "new mode", "new world", "new map", "new app",
    "new page", "new screen", "new feature", "new system", "new attacker", "new operator",
    "new character", "multiplayer", "online", "co-op", "rewrite", "redo", "rework",
    "redesign", "overhaul", "rebuild", "from scratch", "entire", "system", "save", "saving",
    "load game", "story", "quest", "quests", "boss", "bosses", "ai", "inventory", "shop",
    "crafting", "levels", "world", "map", "room", "cutscene", "dialogue", "physics",
    "procedural", "generate", "editor", "achievements", "account", "integrate", "connect",
    "package", "install", "tutorial", "tutorials", "minigame", "game where", "instruments",
    "song",
]
MEDIUM_WORDS = [
    "add", "create", "build", "feature", "mode", "menu", "screen", "page", "animation",
    "animations", "animate", "sound", "sounds", "music", "enemy", "enemies", "weapon",
    "button", "option", "setting", "settings", "fix", "bug", "broken", "crash", "crashes",
    "doesn't work", "doesnt work", "not working", "glitch", "issue", "problem", "score",
    "timer", "health", "list", "window", "panel", "sort", "search", "history", "effect",
    "particles", "camera", "cameras", "aiming", "sensitivity", "balance", "balanced",
    "walk", "walking", "move around",
]
SMALL_WORDS = [
    "typo", "spelling", "rename", "color", "colour", "colors", "colours", "darker",
    "lighter", "brighter", "dimmer", "bigger", "smaller", "larger", "font", "text", "word",
    "wording", "label", "title", "tweak", "slightly", "a bit", "a little", "faster",
    "slower", "louder", "quieter", "speed", "size", "move the", "swap", "change the",
    "remove the", "hide", "icon",
]


def _phrases(words):
    return re.compile(r"\b(" + "|".join(re.escape(w) for w in words) + r")\b")


_BIG, _MEDIUM, _SMALL = _phrases(BIG_WORDS), _phrases(MEDIUM_WORDS), _phrases(SMALL_WORDS)


def size_score(text: str) -> float:
    """A rough guess at how many tokens a change will take: higher is bigger."""
    t = " ".join(text.lower().split())
    score = 1.0
    score += 2.5 * len(set(_BIG.findall(t)))
    score += 1.0 * len(set(_MEDIUM.findall(t)))
    score -= 0.8 * len(set(_SMALL.findall(t)))
    score += len(t.split()) / 40  # a longer note often asks for a bit more
    asks = len(re.findall(r"\band\b|,|;|\balso\b|\bplus\b", t))  # several asks in one
    score += min(0.4 * asks, 1.5)
    return round(max(score, 0.0), 2)


def size_label(score: float) -> str:
    return "Small" if score < 2.2 else "Medium" if score < 5 else "Big"


# --- grouping notes Claude would work on together (his ask: Organize groups them) ---
# Themes that use different words for the same part of a project. Anything else is grouped
# by a telling word two notes share (a character's name, "planks", "shield"...).
THEMES = {
    "Sound": ["sound", "sounds", "audio", "music", "song", "noise", "footsteps", "volume",
              "loud", "louder", "quieter", "voice", "instruments"],
    "Tutorial": ["tutorial", "tutorials", "walkthrough", "training", "teach"],
    "Maps and levels": ["map", "maps", "level", "levels", "layout", "terrain",
                        "room", "rooms", "world"],
    "Weapons and shooting": ["gun", "guns", "shoot", "shooting", "bullet", "bullets",
                             "weapon", "weapons", "aim", "aiming", "reticle", "ads",
                             "launcher", "melee", "damage", "scope", "recoil"],
    "Bots and enemies": ["bot", "bots", "enemy", "enemies", "ai", "creature", "creatures"],
    "Menus and buttons": ["menu", "menus", "button", "buttons", "settings", "options",
                          "lobby", "screen", "hud"],
    "Look": ["color", "colour", "colors", "colours", "darker", "lighter", "brighter",
             "texture", "textures", "theme", "font", "icon", "graphics", "picture"],
    "Movement": ["walk", "walking", "run", "running", "jump", "crouch", "movement",
                 "speed", "sensitivity", "camera", "cameras"],
    "Speed and lag": ["lag", "lags", "laggy", "performance", "intensive", "fps", "choppy",
                      "smooth", "smoother", "quicker", "startup", "loading", "stutter"],
    "Claude and tokens": ["claude", "token", "tokens"],
}
_THEME_OF = {w: theme for theme, words in THEMES.items() for w in words}
STOP_WORDS = set("""
the and for that this with when then than there their they them these those should would
could will make made makes making have having been being able also just very more less
much some each every only even still really maybe which about after before other into
from over under while where what like same sure dont doesnt cant isnt wont thing things
time times need want wants work works working game games player players project app able
first second third last next most least it's its your you yours ours our here away ever
again always never because instead without within between around through until both
whole fine good better best bad worse little bit way ways part parts kind lot lots get
gets getting put puts give gives take takes keep keeps use uses used show shows look looks
feel feels think know right left back down done yes add adding new can into onto upon
mode modes version versions feature features cannot could would should
""".split())


def _keywords(text: str) -> set[str]:
    """The words that say what a note is about: themes, and telling words (crude plural
    stripping, so "plank" and "planks" match)."""
    words = re.findall(r"[a-z][a-z']+", text.lower())
    found = set()
    for w in words:
        w = w.replace("'", "")
        if w in _THEME_OF:
            found.add(_THEME_OF[w])
        if len(w) >= 4 and w not in STOP_WORDS:
            found.add("~" + (w[:-1] if w.endswith("s") and not w.endswith("ss") else w))
    return found


def group_notes(notes: list[dict]) -> list[tuple[str, list[dict]]]:
    """Put notes Claude would work on together side by side: [(heading, notes)]. Each round
    takes the theme or word shared by the most notes not yet grouped (themes win ties);
    notes that share nothing go together under "On their own", last."""
    keys = {id(n): _keywords(n["text"]) for n in notes}
    left = list(notes)
    groups = []
    while True:
        counts = {}
        for n in left:
            for k in keys[id(n)]:
                counts[k] = counts.get(k, 0) + 1
        best = max(counts.items(), key=lambda kv: (kv[1], not kv[0].startswith("~"), kv[0]),
                   default=(None, 0))
        if best[1] < 2:
            break
        key = best[0]
        members = [n for n in left if key in keys[id(n)]]
        left = [n for n in left if key not in keys[id(n)]]
        groups.append((key[1:].capitalize() if key.startswith("~") else key, members))
    if left:
        groups.append(("On their own", left))
    return groups


# --- his words, said shorter for Claude (his ask, 2026-11-02: "summarizes everything i said
# into a language that claude can easily understand and simplify to save on tokens") ---
# Plain rules, no Claude: drop filler, say common phrasings shorter, fix common slips.
# Meaning is never dropped: only words that add nothing for Claude go.
FILLER = [
    r"i think (that )?", r"i feel like ", r"i guess ", r"i want (you )?to ", r"can you ",
    r"could you ", r"please ", r"maybe ", r"kind of ", r"sort of ", r"basically ",
    r"just ", r"really ", r"actually ", r"literally ", r"pretty much ", r"you know,? ",
    r"like,? ", r"\bso,? ", r"\bum+,? ", r"\buh+,? ", r"or something( like that)?",
]
SHORTER = [
    (r"make sure (that )?", "ensure "), (r"it should be possible to ", "allow players to "),
    (r"there should be ", "add "), (r"should be able to ", "can "), (r"in order to ", "to "),
    (r"a lot of ", "many "), (r"at the moment", "now"), (r"right now", "now"),
    (r"as well as ", "and "), (r"the fact that ", ""), (r"all of the ", "all "),
    (r"is going to ", "will "), (r"are going to ", "will "), (r"\bgonna\b", "will"),
    (r"\bwanna\b", "want to"),
]
SLIPS = {
    "dont": "don't", "doesnt": "doesn't", "cant": "can't", "wont": "won't", "isnt": "isn't",
    "shouldnt": "shouldn't", "didnt": "didn't", "theyre": "they're", "youre": "you're",
    "im": "I'm", "ive": "I've", "id": "I'd", "i": "I", "u": "you", "ur": "your",
    "teh": "the", "recieve": "receive", "seperate": "separate", "definately": "definitely",
    "wierd": "weird", "untill": "until", "alot": "a lot", "thier": "their",
    "sheild": "shield", "gadjets": "gadgets", "ernestly": "earnestly",
    "theives": "thieves", "refesh": "refresh", "refeshes": "refreshes", "ableto": "able to",
    "thru": "through", "becuase": "because", "becasue": "because",
}


def condense(text: str) -> str:
    """His note, said shorter and clearer for Claude."""
    t = " " + " ".join(text.split()) + " "
    for pattern in FILLER:
        t = re.sub(r"(?i)(?<=[\s,(])" + pattern, "", t)
    for pattern, new in SHORTER:
        t = re.sub(r"(?i)(?<=[\s,(])" + pattern, new, t)
    t = re.sub(r"[A-Za-z']+", lambda m: SLIPS.get(m.group(0).lower(), m.group(0)), t)
    t = re.sub(r"\s+([,.!?])", r"\1", " ".join(t.split()))
    t = re.sub(r"([,.!?])\1+", r"\1", t)
    return (t[:1].upper() + t[1:]) if t else text


def tokens_in(text: str) -> int:
    """About how many tokens Claude reads for a text (roughly 4 letters per token)."""
    return max(1, round(len(text) / 4))


class Store:
    """All notes, per project folder name. Every change is saved straight away."""

    def __init__(self, path: Path | None = None):
        self.path = path or data_file()
        self.notes: dict[str, list[dict]] = {}
        self.imported: list[str] = []  # projects whose old to-do lists have been brought in
        self.order: list[str] = []   # the sidebar order he dragged them into (his ask, 2026-11-04)
        self.pinned: list[str] = []  # pinned to the top of the sidebar
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text())
            self.notes = data["notes"]
            self.imported = data.get("imported", [])
            self.order = data.get("order", [])
            self.pinned = data.get("pinned", [])
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            self.notes, self.imported, self.order, self.pinned = {}, [], [], []
        for notes in self.notes.values():
            for n in notes:
                n.setdefault("status", "waiting")
                n.setdefault("send", True)
                n.setdefault("work", False)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"notes": self.notes, "imported": self.imported,
                                   "order": self.order, "pinned": self.pinned}, indent=2))
        tmp.replace(self.path)

    # --- the sidebar's order ------------------------------------------------

    def sidebar_order(self, slugs: list[str]) -> list[str]:
        """Pinned first, then the rest, each in the order he dragged them into. Projects he
        hasn't placed yet go at the bottom, longest lists first (the old order)."""
        placed = {s: i for i, s in enumerate(self.order)}
        return sorted(slugs, key=lambda s: (s not in self.pinned, s not in placed,
                                            placed.get(s, 0), -len(self.all(s)), s))

    def set_order(self, slugs: list[str], pinned: list[str] | None = None):
        """His dragged order; pinned: the ones he dropped in the Pinned box, if he moved one
        in or out of it."""
        self.order = list(slugs)
        if pinned is not None:
            self.pinned = [s for s in slugs if s in pinned]
        self.save()

    def toggle_pin(self, slug: str, order: list[str]):
        """Pin it to the top, or unpin it (it goes back just under the pinned ones)."""
        if slug in self.pinned:
            self.pinned.remove(slug)
        else:
            self.pinned.append(slug)
        self.order = [s for s in order if s != slug]
        rest = [s for s in self.order if s not in self.pinned]
        at = self.order.index(rest[0]) if rest else len(self.order)
        self.order.insert(at if slug not in self.pinned else 0, slug)
        self.save()

    # --- reading ----------------------------------------------------------

    def all(self, slug: str) -> list[dict]:
        return self.notes.get(slug, [])

    def get(self, slug: str, status: str = "waiting") -> list[dict]:
        return [n for n in self.all(slug) if n["status"] == status]

    # --- his waiting notes ------------------------------------------------

    def add(self, slug: str, text: str) -> dict | None:
        if not text.strip():
            return None
        note = {"id": new_id(), "text": " ".join(text.split()), "status": "waiting",
                "added": today(), "send": True, "work": False}
        self.notes.setdefault(slug, []).append(note)
        self.save()
        return note

    def set_snapshot(self, slug: str, note_id: str, snap: dict):
        """What the project was like when he wrote the note (his ask, 2026-11-02)."""
        for note in self.all(slug):
            if note["id"] == note_id:
                note["snap"] = snap
        self.save()

    def edit(self, slug: str, note_id: str, text: str):
        if not text.strip():
            return self.delete(slug, note_id)
        for note in self.all(slug):
            if note["id"] == note_id:
                note["text"] = " ".join(text.split())
                if "size" in note:
                    note["size"] = size_score(note["text"])
        self.save()

    def delete(self, slug: str, note_id: str):
        self.notes[slug] = [n for n in self.all(slug) if n["id"] != note_id]
        self.save()

    def move(self, slug: str, note_id: str, to_slug: str):
        note = next((n for n in self.all(slug) if n["id"] == note_id), None)
        if note and to_slug != slug:
            self.notes[slug] = [n for n in self.all(slug) if n["id"] != note_id]
            self.notes.setdefault(to_slug, []).append(note)
            self.save()

    def tick(self, slug: str, note_ids: list[str], which: str, on: bool):
        """Set the "send" or "work" tick on some notes."""
        for note in self.all(slug):
            if note["id"] in note_ids:
                note[which] = on
        self.save()

    def mark_worked(self, slug: str, note_ids: list[str]):
        """Work started on them: the work tick comes off and the day is kept."""
        for note in self.all(slug):
            if note["id"] in note_ids:
                note["work"] = False
                note["worked"] = today()
        self.save()

    def mark_sent(self, slug: str, note_ids: list[str]):
        for note in self.all(slug):
            if note["id"] in note_ids:
                note["status"] = "sent"
                note["sent"] = today()
        self.save()

    def later(self, slug: str, note_id: str):
        """Into the Later box: off the list, unticked, out of the way."""
        for note in self.all(slug):
            if note["id"] == note_id:
                note.update(status="later", send=False, work=False, later=today())
                note.pop("worked", None)
        self.save()

    def now(self, slug: str, note_id: str):
        """Back out of the Later box: waiting again, ticked to send."""
        for note in self.all(slug):
            if note["id"] == note_id:
                note.update(status="waiting", send=True)
                note.pop("later", None)
        self.save()

    def organize(self, slug: str):
        """Group the waiting notes, and the sent ones, by what Claude would work on together
        (his ask), smallest group first, and smallest note first inside each group. Each
        note keeps its size guess and its group's heading. Done notes keep their place."""
        notes = self.all(slug)
        live = []
        for status in ("waiting", "sent"):
            mine = [n for n in notes if n["status"] == status]
            for n in mine:
                n["size"] = size_score(n["text"])
            groups = group_notes(mine)
            groups.sort(key=lambda g: (g[0] == "On their own", sum(n["size"] for n in g[1])))
            for heading, members in groups:
                for n in sorted(members, key=lambda n: n["size"]):
                    n["group"] = heading
                    live.append(n)
        self.notes[slug] = live + [n for n in notes if n["status"] not in ("waiting", "sent")]
        self.save()

    # --- keeping up with the project's to-do list -------------------------

    def sync(self, slug: str, open_items: list[str] | None, done_items: list[str],
             review_items: list[str] = ()) -> bool:
        """Match the history to what the to-do list says now. Returns whether anything changed.

        open_items is None when the project has no to-do list to read; then nothing is
        marked done (a list that has gone missing, say on another branch, finishes nothing).
        review_items: finished on a branch of a shared game, waiting for lando's review;
        None when that couldn't be told (git didn't answer): what is in review stays there.
        """
        if open_items is None:
            return False
        notes = self.notes.setdefault(slug, [])
        if review_items is None:
            review_items = [n["text"] for n in notes if n["status"] == "review"]
        changed = False

        def listed(n, items):
            return any(same(n["text"], t) for t in items)

        first = slug not in self.imported
        if first:
            # First look at this project: bring in its whole list, finished items too
            for status, items in (("done", done_items), ("review", review_items)):
                for text in items:
                    notes.append({"id": new_id(), "text": text, "status": status,
                                  "imported": True, "send": True, "work": False})
            self.imported.append(slug)
            changed = True

        # Something on the list VibeNote has not seen (added in a chat, or already there
        # on import): it counts as sent. One he put in Later is known (a shared game's other
        # branches may still list it)
        for status, items in (("sent", open_items), ("review", review_items)):
            for text in items:
                if not any(n["status"] in ("sent", "later", "review") and same(n["text"], text)
                           for n in notes):
                    if status == "review" and any(n["status"] == "done" and
                                                  same(n["text"], text) for n in notes):
                        continue  # a done one goes back to review just below
                    note = {"id": new_id(), "text": text, "status": status, "imported": True,
                            "send": True, "work": False}
                    if not first:
                        note["sent"] = today()  # the day VibeNote first saw it there
                    notes.append(note)
                    changed = True

        for n in notes:
            if n["status"] in ("sent", "done") and listed(n, review_items):
                # Finished on Blaney's branch, not merged yet: up for lando's review
                n.update(status="review", work=False, review=n.get("review") or today())
                n.pop("done", None)
                changed = True
            elif n["status"] == "review" and not listed(n, review_items):
                if listed(n, open_items):
                    n["status"] = "sent"  # unticked again
                else:
                    n.update(status="done", done=today())  # lando merged it
                changed = True
            elif n["status"] == "sent" and not listed(n, open_items):
                # Sent, but no longer on the list: Claude finished it
                n.update(status="done", work=False, done=today())
                changed = True

        # The same item twice on the list or in review: from before Claude's *(...)* notes
        # under an item were matched to it, each new note made it look like a new item
        keep = []
        for n in notes:
            twin = next((k for k in keep if k["status"] == n["status"] in ("sent", "review")
                         and same(k["text"], n["text"])), None)
            if twin is None:
                keep.append(n)
                continue
            for key in ("worked", "snap", "size", "group"):
                if key in n and key not in twin:
                    twin[key] = n[key]
            if len(n["text"]) > len(twin["text"]):
                twin["text"] = n["text"]  # the newest, with Claude's latest note
            changed = True
        notes[:] = keep

        if changed:
            self.save()
        return changed
