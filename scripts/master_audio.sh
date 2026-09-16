#!/usr/bin/env bash
# master_audio.sh — two-pass EBU R128 loudness normalisation of a rendered video (video stream copied).
#
# Usage: master_audio.sh <in.mp4> <out.mp4> [target LUFS, default -15] [--help]
#   pass 1  ffmpeg -af loudnorm=I=T:TP=-1.5:LRA=9:print_format=json  → measured_I / TP / LRA / thresh / offset
#   pass 2  loudnorm with the measured values and linear=true (no pumping), video -c:v copy, AAC 192k 48 kHz
#   prints  integrated loudness before → after (LUFS), true peak, and the gain applied
# Targets: 小红书 / 抖音 sit happily at -15…-14 LUFS; -16 for a quieter, more “podcast” feel.
# Exit 1 when the input has no audio stream or ffmpeg fails. macOS has no `timeout`; nothing here needs one.
set -uo pipefail

usage() { sed -n '2,/^set -uo/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; }

IN=""; OUT=""; TARGET="-15"
for a in "$@"; do
  case "$a" in
    -h|--help) usage; exit 0 ;;
    -[0-9]*|[0-9]*) TARGET="$a" ;;
    -*) echo "unknown argument: $a" >&2; usage >&2; exit 2 ;;
    *) if [ -z "$IN" ]; then IN="$a"; elif [ -z "$OUT" ]; then OUT="$a"; else echo "unexpected argument: $a" >&2; exit 2; fi ;;
  esac
done
[ -n "$IN" ] && [ -n "$OUT" ] || { usage >&2; exit 2; }
[ -f "$IN" ] || { echo "FAIL: input not found: $IN" >&2; exit 1; }
for t in ffmpeg ffprobe python3; do command -v "$t" >/dev/null 2>&1 || { echo "FAIL: $t not found" >&2; exit 1; }; done
python3 -c "float('$TARGET')" 2>/dev/null || { echo "FAIL: target LUFS must be a number (got $TARGET)" >&2; exit 2; }
if ! ffprobe -v error -select_streams a:0 -show_entries stream=codec_type -of csv=p=0 "$IN" 2>/dev/null | grep -q audio; then
  echo "FAIL: $IN has no audio stream — nothing to master (render with narration/bgm first)" >&2; exit 1
fi
mkdir -p "$(dirname "$OUT")"

FILTER_BASE="loudnorm=I=${TARGET}:TP=-1.5:LRA=9"
echo "pass 1/2: measuring ${IN}" >&2
LOG1="$(ffmpeg -hide_banner -nostats -i "$IN" -vn -af "${FILTER_BASE}:print_format=json" -f null - 2>&1)" || { echo "FAIL: ffmpeg pass 1 failed" >&2; printf '%s\n' "$LOG1" | tail -5 >&2; exit 1; }
MEASURED="$(printf '%s\n' "$LOG1" | python3 -c '
import json, re, sys
txt = sys.stdin.read()
blocks = re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", txt)
if not blocks: sys.exit("no loudnorm json in ffmpeg output")
j = json.loads(blocks[-1])
print(" ".join(str(j[k]) for k in ("input_i", "input_tp", "input_lra", "input_thresh", "target_offset")))
')" || { echo "FAIL: could not parse loudnorm measurements" >&2; exit 1; }
read -r IN_I IN_TP IN_LRA IN_THRESH OFFSET <<< "$MEASURED"
echo "  measured: I=${IN_I} LUFS  TP=${IN_TP} dBTP  LRA=${IN_LRA} LU  thresh=${IN_THRESH}  offset=${OFFSET}" >&2

echo "pass 2/2: writing ${OUT}" >&2
LOG2="$(ffmpeg -hide_banner -nostats -y -i "$IN" -map 0:v? -map 0:a:0 -c:v copy \
  -af "${FILTER_BASE}:measured_I=${IN_I}:measured_TP=${IN_TP}:measured_LRA=${IN_LRA}:measured_thresh=${IN_THRESH}:offset=${OFFSET}:linear=true:print_format=json" \
  -ar 48000 -c:a aac -b:a 192k -movflags +faststart "$OUT" 2>&1)" || { echo "FAIL: ffmpeg pass 2 failed" >&2; printf '%s\n' "$LOG2" | tail -5 >&2; rm -f "$OUT"; exit 1; }
AFTER="$(printf '%s\n' "$LOG2" | python3 -c '
import json, re, sys
txt = sys.stdin.read()
blocks = re.findall(r"\{[^{}]*\"output_i\"[^{}]*\}", txt)
j = json.loads(blocks[-1]) if blocks else {}
print(j.get("output_i", "?"), j.get("output_tp", "?"), j.get("normalization_type", "?"))
')"
read -r OUT_I OUT_TP NTYPE <<< "$AFTER"
# independent check of the written file (the loudnorm output_i is the filter's own estimate)
CHECK="$(ffmpeg -hide_banner -nostats -i "$OUT" -vn -af ebur128=peak=true -f null - 2>&1 | python3 -c '
import re, sys
txt = sys.stdin.read()
m = re.findall(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", txt)
p = re.findall(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", txt)
print(m[-1] if m else "?", p[-1] if p else "?")
')"
read -r FILE_I FILE_TP <<< "$CHECK"
GAIN="$(python3 -c "
try: print('%+.1f dB' % (float('$FILE_I') - float('$IN_I')))
except Exception: print('?')")"
echo "loudness: ${IN_I} LUFS → ${FILE_I} LUFS (target ${TARGET}, ${NTYPE}, gain ${GAIN})  true peak ${FILE_TP} dBTP  → ${OUT}"
