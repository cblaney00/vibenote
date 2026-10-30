#!/usr/bin/env bash
# Starts VibeNote with no Claude needed (the menu entry runs this).
cd "$(dirname "$(readlink -f "$0")")" || exit 1
exec nix develop /home/insideabush/nixos-config#vibe-python --command python main.py
