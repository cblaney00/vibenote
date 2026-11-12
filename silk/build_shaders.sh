#!/usr/bin/env bash
# Compile silk/shaders/*.frag to .qsb (Qt's shader packs). Run after changing a shader, then
# commit both. Needs Qt's qsb, which is in the Nix store as part of qtshadertools.
set -euo pipefail
cd "$(dirname "$0")/shaders"
QSB=$(command -v qsb || ls -d /nix/store/*-qtshadertools-6*/bin/qsb 2>/dev/null | head -n1)
[ -x "$QSB" ] || { echo "qsb not found"; exit 1; }
for f in *.frag; do
  "$QSB" --glsl "300es,120,150" --hlsl 50 --msl 12 -o "$f.qsb" "$f"
  echo "built $f.qsb"
done
