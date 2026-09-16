#!/usr/bin/env bash
# contact_sheet.sh — 8-frame contact sheet per clip so you can pick highlight windows without watching everything.
#
# Usage: contact_sheet.sh <workdir> [--clips DIR] [--help]
#   clips     default <workdir>/project/public/clips/NN.mp4 (falls back to <workdir>/assets/raw/*.mp4); *.bg.mp4 ignored
#   writes    <workdir>/assets/frames/NN.jpg   4×2 tiles, 480 px wide each, sampled at k·d/8 (k = 0…7)
#             <workdir>/assets/frames/all.jpg  the first 6 sheets stacked vertically (quick overview)
#   prints    one line per sheet with the sampled timestamps (column → second)
set -euo pipefail

usage() { sed -n '2,/^set -euo/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; }

W=""; DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --clips) DIR="${2:?--clips needs a directory}"; shift ;;
    -*) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    *) if [ -z "$W" ]; then W="$1"; else echo "unexpected argument: $1" >&2; exit 2; fi ;;
  esac
  shift
done
[ -n "$W" ] || { usage >&2; exit 2; }
[ -d "$W" ] || { echo "FAIL: workdir not found: $W" >&2; exit 2; }
command -v ffmpeg >/dev/null 2>&1 || { echo "FAIL: ffmpeg not found" >&2; exit 1; }

if [ -z "$DIR" ]; then
  if ls "$W"/project/public/clips/*.mp4 >/dev/null 2>&1; then DIR="$W/project/public/clips"; else DIR="$W/assets/raw"; fi
fi
[ -d "$DIR" ] || { echo "FAIL: clips dir not found: $DIR" >&2; exit 2; }
OUT="$W/assets/frames"; mkdir -p "$OUT"

SHEETS=()
for f in "$DIR"/*.mp4 "$DIR"/*.mov "$DIR"/*.webm; do
  [ -f "$f" ] || continue
  case "$f" in *.bg.mp4) continue ;; esac
  n="$(basename "$f")"; n="${n%.*}"
  d="$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" 2>/dev/null || echo 0)"
  if [ -z "$d" ] || [ "$d" = "N/A" ] || [ "$(python3 -c "print(1 if float('$d') > 0 else 0)")" != 1 ]; then
    echo "skip ${n}: cannot read duration" >&2; continue
  fi
  ffmpeg -v error -y -i "$f" -vf "fps=8/${d},scale=480:-2,tile=4x2" -frames:v 1 "$OUT/${n}.jpg" </dev/null
  SHEETS+=("$OUT/${n}.jpg")
  times="$(python3 -c "d=float('$d'); print(' '.join(f'{k*d/8:.1f}' for k in range(8)))")"
  printf '%s.jpg  %6.1fs  cols→s: %s\n' "$n" "$d" "$times"
done
[ "${#SHEETS[@]}" -gt 0 ] || { echo "FAIL: no clips found in $DIR" >&2; exit 1; }

# overview: first 6 sheets stacked (same width → vstack is safe)
N="${#SHEETS[@]}"; [ "$N" -gt 6 ] && N=6
if [ "$N" = 1 ]; then
  cp "${SHEETS[0]}" "$OUT/all.jpg"
else
  ARGS=(); FILTER=""
  for ((i = 0; i < N; i++)); do ARGS+=(-i "${SHEETS[$i]}"); FILTER="${FILTER}[$i:v]scale=1920:-2[s$i];"; done
  for ((i = 0; i < N; i++)); do FILTER="${FILTER}[s$i]"; done
  FILTER="${FILTER}vstack=inputs=${N}"
  ffmpeg -v error -y "${ARGS[@]}" -filter_complex "$FILTER" -frames:v 1 "$OUT/all.jpg" </dev/null
fi
echo "all.jpg  (${N} of ${#SHEETS[@]} sheets)"
ls "$OUT"
