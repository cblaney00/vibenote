#!/usr/bin/env bash
# Start the Silk VibeNote (the new graphics-card window; docs/silk-rebuild.md) through the
# dev shell, like run.sh does for the Tk one.
cd "$(dirname "$0")"
exec nix develop /home/insideabush/nixos-config#vibe-python --command python silk/app.py "$@"
