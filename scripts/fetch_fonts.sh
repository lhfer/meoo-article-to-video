#!/usr/bin/env bash
# fetch_fonts.sh — download the OFL fonts the template uses (Noto Sans SC Bold/Black, Noto Serif SC Bold,
# Smiley Sans 得意黑 Oblique) into a fonts directory, via a per-user cache.
#
# Usage: fetch_fonts.sh [<dest dir>] [--cache-only] [--help]
#   <dest dir>     default: <skill root>/assets/template/public/fonts
#   --cache-only   only fill the cache, copy nothing (prints the copy command)
#   cache:         ${XDG_CACHE_HOME:-~/.cache}/article-to-vertical-video/fonts/  — only the first run downloads
# Files written (the names theme.ts fontFiles expects):
#   NotoSansSC-Bold.ttf  NotoSansSC-Black.ttf  NotoSerifSC-Bold.ttf  SmileySans-Oblique.ttf  fonts.json
# Sources, tried in order per font:
#   1. google/fonts repo variable TTF (NotoSansSC[wght].ttf, ~17 MB) → cached as NotoSansSC-VF.ttf, then
#      a STATIC instance at the wanted weight is cut with fontTools (`uv run --with fonttools`, ~10 MB);
#      without uv/fontTools the variable file is COPIED to the Bold/Black names (Chrome pins the wght axis
#      from the @font-face weight, so the copy renders the right weight)
#   2. notofonts/noto-cjk SubsetOTF (CFF OpenType) → saved under the .ttf name; Chrome sniffs the real format
#   Smiley Sans: GitHub release zip (atelier-anchor/smiley-sans), only the Oblique .ttf is extracted
#   (Google Fonts' CSS API is NOT used: for CJK families it serves a Latin-only 34 KB subset.)
# Every file is verified with `file` + a size floor (Noto > 1 MB, Smiley > 300 KB).
# A failed download is reported and skipped — fonts are optional at render time (system fallback).
# Exit 1 only when no font at all could be provided.
set -uo pipefail

usage() { sed -n '2,/^set -uo/p' "$0" | grep '^#' | sed 's/^# \{0,1\}//'; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
DEST="${ROOT}/assets/template/public/fonts"
CACHE_ONLY=0
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --cache-only) CACHE_ONLY=1 ;;
    -*) echo "unknown argument: $1" >&2; usage >&2; exit 2 ;;
    *) DEST="$1" ;;
  esac
  shift
done
CACHE="${XDG_CACHE_HOME:-${HOME}/.cache}/article-to-vertical-video/fonts"
mkdir -p "${CACHE}" || { echo "FAIL: cannot create cache ${CACHE}" >&2; exit 1; }
if [ "${CACHE_ONLY}" = 0 ]; then mkdir -p "${DEST}" && DEST="$(cd "${DEST}" && pwd)"; fi
command -v curl >/dev/null 2>&1 || { echo "FAIL: curl not found" >&2; exit 1; }

fsize() { stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo 0; }
mb() { python3 -c "print('%.2f' % ($1/1048576))" 2>/dev/null || echo "$(( $1 / 1048576 ))"; }
is_font() {  # is_font <file> <min bytes>: real TrueType/OpenType and big enough (error pages are tiny HTML)
  local f="$1" min="$2" magic
  [ -s "${f}" ] || return 1
  [ "$(fsize "${f}")" -ge "${min}" ] || return 1
  magic="$(head -c 4 "${f}" | od -An -tx1 | tr -d ' \n')"
  case "${magic}" in 00010000|4f54544f|74727565) return 0 ;; esac   # TrueType / OTTO / 'true'
  command -v file >/dev/null 2>&1 && file -b "${f}" | grep -qiE 'truetype|opentype|font' && return 0
  return 1
}
is_variable() {  # has an fvar table → variable font
  command -v file >/dev/null 2>&1 && file -b "$1" | grep -qi 'variable' && return 0
  python3 - "$1" <<'PY' 2>/dev/null
import struct, sys
f = open(sys.argv[1], "rb"); f.read(4); n = struct.unpack(">H", f.read(2))[0]; f.read(6)
tags = {f.read(16)[:4] for _ in range(n)}
sys.exit(0 if b"fvar" in tags else 1)
PY
}
dl() {  # dl <url> <dst>: quiet download with retries, non-zero on HTTP errors
  curl -sSL -f --retry 2 --connect-timeout 30 --max-time 600 -A "Mozilla/5.0" -o "$2" "$1"
}

# ---- source 1: google/fonts variable TTF → static instance (fontTools) or copy --------------------------
make_static() {  # make_static <variable ttf> <weight> <out>: cut a static instance with fontTools via uv
  command -v uv >/dev/null 2>&1 || return 1
  uv run --quiet --with fonttools python3 - "$1" "$2" "$3" <<'PY' 2>/dev/null
import sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
src, weight, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
font = TTFont(src)
static = instancer.instantiateVariableFont(font, {"wght": weight}, inplace=False, updateFontNames=True)
static.save(out)
PY
}
fetch_variable() {  # fetch_variable <name> <vf cache name> <repo path> <weight> <min>
  local tmp="${CACHE}/.$2.part"
  if ! is_font "${CACHE}/$2" "$5"; then
    dl "https://raw.githubusercontent.com/google/fonts/main/$3" "${tmp}" && is_font "${tmp}" "$5" && mv "${tmp}" "${CACHE}/$2"
    rm -f "${tmp}"
  fi
  is_font "${CACHE}/$2" "$5" || return 1
  tmp="${CACHE}/.$1.part"
  if make_static "${CACHE}/$2" "$4" "${tmp}" && is_font "${tmp}" "$5" && ! is_variable "${tmp}"; then
    mv "${tmp}" "${CACHE}/$1"; NOTE="static instance of $2 at wght $4 (fontTools)"; return 0
  fi
  rm -f "${tmp}"
  cp "${CACHE}/$2" "${CACHE}/$1"; NOTE="copy of variable font $2 (no uv/fontTools; wght axis covers this weight)"; return 0
}

# ---- source 2: notofonts SubsetOTF -------------------------------------------------------------------
fetch_otf() {  # fetch_otf <name> <repo path> <min>
  local tmp="${CACHE}/.$1.part"
  if dl "https://github.com/notofonts/noto-cjk/raw/main/$2" "${tmp}" && is_font "${tmp}" "$3"; then
    mv "${tmp}" "${CACHE}/$1"; NOTE="CFF OpenType from notofonts/noto-cjk saved under the .ttf name (Chrome sniffs the format)"; return 0
  fi
  rm -f "${tmp}"; return 1
}

# ---- Smiley Sans (得意黑) --------------------------------------------------------------------------------
fetch_smiley() {  # → SmileySans-Oblique.ttf
  local name="SmileySans-Oblique.ttf" tmpd zip url ttf
  command -v unzip >/dev/null 2>&1 || { echo "FAIL ${name}: 需要 unzip" >&2; return 1; }
  tmpd="$(mktemp -d)"; zip="${tmpd}/smiley.zip"
  url="https://github.com/atelier-anchor/smiley-sans/releases/download/v2.0.1/smiley-sans-v2.0.1.zip"
  if ! dl "${url}" "${zip}"; then  # tag moved? ask the API for the latest zip asset
    url="$(curl -sS --max-time 40 https://api.github.com/repos/atelier-anchor/smiley-sans/releases/latest 2>/dev/null | sed -n 's/.*"browser_download_url": *"\([^"]*\.zip\)".*/\1/p' | head -1)"
    [ -n "${url}" ] && dl "${url}" "${zip}"
  fi
  if [ -s "${zip}" ] && unzip -qo "${zip}" '*.ttf' -d "${tmpd}/x" 2>/dev/null; then
    ttf="$(find "${tmpd}/x" -type f -iname 'SmileySans-Oblique.ttf' | head -1)"
    [ -z "${ttf}" ] && ttf="$(find "${tmpd}/x" -type f -iname 'SmileySans*.ttf' | head -1)"
    if [ -n "${ttf}" ] && is_font "${ttf}" 300000; then cp "${ttf}" "${CACHE}/${name}"; rm -rf "${tmpd}"; NOTE="TTF from the GitHub release zip"; return 0; fi
  fi
  rm -rf "${tmpd}"; return 1
}

# ---- targets: name|family|weight|min bytes|variable cache name|variable repo path|otf repo path -----------
TARGETS=(
  "NotoSansSC-Bold.ttf|Noto+Sans+SC|700|1000000|NotoSansSC-VF.ttf|ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf|Sans/SubsetOTF/SC/NotoSansSC-Bold.otf"
  "NotoSansSC-Black.ttf|Noto+Sans+SC|900|1000000|NotoSansSC-VF.ttf|ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf|Sans/SubsetOTF/SC/NotoSansSC-Black.otf"
  "NotoSerifSC-Bold.ttf|Noto+Serif+SC|700|1000000|NotoSerifSC-VF.ttf|ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf|Serif/SubsetOTF/SC/NotoSerifSC-Bold.otf"
  "SmileySans-Oblique.ttf|Smiley Sans|400|300000|||"
)
OK=0; BAD=0; MANIFEST=""; SUMMARY=""
for t in "${TARGETS[@]}"; do
  IFS='|' read -r name fam weight min vfname vfpath otfpath <<< "${t}"
  NOTE="cache"
  if ! is_font "${CACHE}/${name}" "${min}"; then
    rm -f "${CACHE}/${name}"
    echo "…下载 ${name}" >&2
    if [ "${name}" = "SmileySans-Oblique.ttf" ]; then
      fetch_smiley || { echo "FAIL ${name}: 下载 / 解压 GitHub release 失败" >&2; BAD=$((BAD+1)); continue; }
    else
      fetch_variable "${name}" "${vfname}" "${vfpath}" "${weight}" "${min}" \
        || fetch_otf "${name}" "${otfpath}" "${min}" \
        || { echo "FAIL ${name}: 两个来源都失败（google/fonts 变量字体 / notofonts OTF）— 检查网络或代理" >&2; BAD=$((BAD+1)); continue; }
    fi
  fi
  sz="$(fsize "${CACHE}/${name}")"
  kind="static"; is_variable "${CACHE}/${name}" && kind="variable"
  [ "$(head -c 4 "${CACHE}/${name}" | od -An -tx1 | tr -d ' \n')" = "4f54544f" ] && kind="${kind} otf"
  if [ "${CACHE_ONLY}" = 0 ]; then cp "${CACHE}/${name}" "${DEST}/${name}"; fi
  SUMMARY="${SUMMARY}$(printf 'OK   %-24s %7s MB  %-8s %s' "${name}" "$(mb "${sz}")" "${kind}" "${NOTE}")"$'\n'
  style="normal"; [ "${name}" = "SmileySans-Oblique.ttf" ] && style="oblique"
  family="$(printf '%s' "${fam}" | tr '+' ' ')"
  MANIFEST="${MANIFEST}{\"file\":\"${name}\",\"family\":\"${family}\",\"weight\":${weight},\"style\":\"${style}\",\"bytes\":${sz},\"kind\":\"${kind}\"},"
  OK=$((OK+1))
done

printf '%s' "${SUMMARY}"
if [ "${CACHE_ONLY}" = 0 ]; then
  printf '[%s]\n' "${MANIFEST%,}" > "${DEST}/fonts.json"
  echo "${OK} 个字体就绪 → ${DEST}（缓存: ${CACHE}）" >&2
else
  echo "${OK} 个字体在缓存 ${CACHE}（--cache-only，未复制）" >&2
  echo "复制到项目: cp \"${CACHE}\"/*.ttf <workdir>/project/public/fonts/" >&2
fi
if [ "${BAD}" -gt 0 ]; then echo "${BAD} 个失败（可选：渲染时回退系统字体 PingFang）" >&2; fi
[ "${OK}" -gt 0 ] || { echo "FAIL: 一个字体都没拿到（检查网络 / 代理）" >&2; exit 1; }
exit 0
