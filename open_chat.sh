#!/usr/bin/env bash
# open_chat.sh <project dir> <title> <message file> [fresh]
# Run by VibeNote inside a new kitty window: starts Claude on the project exactly the way
# `vibe` does (same launcher, hooks and session rules, read out of the installed vibe so
# they follow every rebuild), picking up the last chat if there is one, and hands it the
# message as its first prompt.
set -uo pipefail
dir="$1" title="$2" msgfile="$3" fresh="${4:-}"
cd "$dir" || exit 1
msg=$(cat "$msgfile")
rm -f "$msgfile"

VIBE=$(readlink -f "$(command -v vibe)")
var() { sed -n "s/^$1=\"\(.*\)\"$/\1/p" "$VIBE" | head -n1; }
RE_LAUNCHER=$(var RE_LAUNCHER)
GD_LAUNCHER=$(var GD_LAUNCHER)
GD_GUARD_HOOKS=$(var GD_GUARD_HOOKS)
SESSION_RULES=$(var SESSION_RULES)
HOOKS=$(grep -o -- '--settings [^ ]*' "$VIBE" | head -n1)
PREPARE=$(grep -o '/nix/store/[^ ]*-vibe-prepare' "$VIBE" | head -n1)

field() { sed -n "s/^$1=//p" .vibe-project 2>/dev/null | head -n1; }
kind=$(field kind)
shared=$(field shared)
[ -n "$shared" ] && [ -n "$GD_GUARD_HOOKS" ] && git config core.hooksPath "$GD_GUARD_HOOKS"

echo "Opening Claude on $title with your notes from VibeNote."
echo "(If it asks for your password, type it and press Enter.)"
echo

sessions=0
if [ -n "$PREPARE" ]; then
  sessions=$(sudo "$PREPARE" "$dir" 2>/dev/null | sed -n 's/^sessions=//p' | head -n1)
fi
case "$sessions" in ""|*[!0-9]*) sessions=0 ;; esac

run() {
  case "$kind" in
    re) exec sudo "$RE_LAUNCHER" "$@" ;;
    game) exec sudo "$GD_LAUNCHER" $HOOKS "$@" ;;
    *) exec sudo claude $HOOKS "$@" ;;
  esac
}

# "fresh": the last chat has grown so long that re-reading it would cost more than starting
# over, so start a new one (VibeNote decides; sender.fresh_reason)
if [ "$sessions" -gt 0 ] && [ "$fresh" != "fresh" ]; then
  run -c "$msg"
fi

case "$kind" in
  re) about="This is a REVERSE-ENGINEERING project (kind=re in .vibe-project). The
\"Reverse-engineering projects\" section of ../CLAUDE.md applies on top of everything
else there." ;;
  game) about="This is a GAME project (kind=game in .vibe-project). The \"Game projects\" section of
../CLAUDE.md applies on top of everything else there." ;;
  *) about="" ;;
esac
team=""
if [ -n "$shared" ]; then
  team="This is a SHARED game: lando's repo github.com/$shared, which he works on too. The
\"Working together: git and PRs\" section of its CLAUDE.md is binding here and replaces
the \"commit to main freely\" and \"Where his app's code is allowed to live\" rules of
../CLAUDE.md: every change goes on a blaney/ branch and into a PR that lando merges.
Follow its \"Every session, before anything else\" steps first, lando's PR comments
included. Read docs/style.md before changing anything he will see, and log every
look-and-feel call he makes in its direction log (its \"Look and feel\" rules)."
fi

prompt="$(cat "$SESSION_RULES")

--- THIS SESSION ---
The project is called: $title
Its folder is: $dir

$about

$team

It already exists. Read its CLAUDE.md and anything in docs/ before you do anything else,
and look at the git log to see where it was left. He opened this chat by sending notes
from his VibeNote app; here they are:

$msg"
run "$prompt"
