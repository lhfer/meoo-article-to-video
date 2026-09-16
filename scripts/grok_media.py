#!/usr/bin/env python3
"""Headless grok CLI wrapper for the Imagine tools (any host that has the grok CLI logged in).

Derived from sprite-anim-forge/scripts/grok_media.py; extended with the `image` subcommand (text-to-image
via the built-in `image_gen` tool) and an inline ffprobe helper (no saf_common dependency).

Runs `grok -p` with exactly ONE media tool allowed, streams the NDJSON event stream to
<work dir>/grok-stream.ndjson (evidence, kept even on timeout), takes the output path from the
`tool_call_update(status=completed).rawOutput.path`, copies the produced file to --out (images → PNG)
and verifies it with PIL / ffprobe. Prints exactly one JSON line. Never prints credentials.

  grok_media.py doctor [--online]
  grok_media.py image -o out.png --prompt "..." | --prompt-file F  --aspect 3:4        (image_gen; 3:4 9:16 16:9 1:1 ...)
  grok_media.py edit  -o out.png --prompt "..." | --prompt-file F  --image A.png [--image B.png ...] [--aspect auto]
  grok_media.py i2v   -o clip.mp4 --image base.png [--prompt "..."] [--duration 6|10] [--resolution 480p|720p]
  grok_media.py r2v   -o clip.mp4 --prompt "..." --image A.png [...] --aspect 1:1 [--duration 1..15] [--resolution 480p]
Common: [--work-dir DIR] [--timeout SEC] [--dry-run]

Calibrated (grok 1.0.18, 2026-09-03): image_gen 3:4 → 864×1152 JPEG (~25 s); image_edit output inherits the input
aspect; image_to_video keeps the input aspect, 24 fps, H.264 + AAC audio track (strip it downstream), duration 6|10,
480p|720p. One tool round trip = 2 turns, hence --max-turns 4. `bash` is not a valid --tools id. 401/403 → `grok login`.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

ASPECTS = {"auto", "1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "2:1", "1:2", "19.5:9", "9:19.5", "20:9", "9:20"}
RESOLUTIONS = {"480p", "720p"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}
MEDIA_RE = re.compile(r"(/[^\s\"'`<>\\]+?\.(?:png|jpe?g|webp|mp4|mov|webm))", re.I)
TOOL_TIMEOUT = {"image_gen": 300, "image_edit": 300, "image_to_video": 720, "reference_to_video": 720}


def find_grok() -> Path | None:
    found = shutil.which("grok")
    if found:
        return Path(found)
    fb = Path.home() / ".grok" / "bin" / "grok"
    return fb if fb.is_file() else None


def grok_bin() -> Path:
    gb = find_grok()
    if gb is None:
        fail("grok CLI not found (expected on PATH or at ~/.grok/bin/grok)", 1)
    return gb


def fail(msg: str, code: int = 2, extra: dict | None = None):
    out = {"ok": False, "error": msg}
    if extra:
        out.update(extra)
    print(json.dumps(out, ensure_ascii=False))
    raise SystemExit(code)


def build_instruction(tool: str, args: dict) -> str:
    return (f"You are a tool runner. The user explicitly asks for this media file. "
            f"Call the built-in tool `{tool}` exactly once with exactly these arguments:\n"
            f"{json.dumps(args, ensure_ascii=False, indent=2)}\n"
            "Rules: do not change the prompt text; do not call any other tool; do not retry unless the tool reports an error; "
            "when the tool returns, reply with only the absolute path of the saved output file.")


def walk_strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_strings(v)


def parse_stream(text: str) -> dict:
    """Event shapes (grok 1.0.18 streaming-json): thought/text {data}, usage, tool_call {toolName, rawInput},
    tool_call_update {status: null|completed|failed, content[], rawOutput: {type, path, filename, session_folder}},
    end {stopReason, sessionId, total_cost_usd, num_turns}. available_commands lines are noise."""
    events, tool_calls, results, texts, end, errors = [], [], [], [], None, []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "available_commands":
            continue
        events.append(ev)
        t = ev.get("type")
        if t == "tool_call":
            tool_calls.append(ev)
        elif t == "tool_call_update":
            status = ev.get("status")
            if status == "completed":
                results.append(ev)
            elif status in ("failed", "error", "cancelled"):
                errors.append(ev)
        elif t == "text":
            texts.append(ev.get("data", ""))
        elif t == "end":
            end = ev
    return {"events": events, "toolCalls": tool_calls, "results": results, "text": "".join(texts), "end": end, "errors": errors}


def candidate_paths(parsed: dict, work_dir: Path, started: float, exts: set) -> list[Path]:
    """Output file candidates, most trustworthy first: rawOutput.path → any path string in the tool results →
    the reply text → the grok session folder for this run → fresh files under the work dir."""
    seen, cands = set(), []

    def add_path(p: Path):
        if p.suffix.lower() in exts and p.is_file() and str(p) not in seen:
            seen.add(str(p))
            cands.append(p)

    def add_text(s: str):
        for m in MEDIA_RE.findall(s):
            add_path(Path(m))

    for r in parsed["results"]:
        raw = r.get("rawOutput")
        if isinstance(raw, dict) and isinstance(raw.get("path"), str):
            add_path(Path(raw["path"]))
    for r in parsed["results"]:
        for s in walk_strings(r):
            add_text(s)
    add_text(parsed["text"])
    sid = (parsed.get("end") or {}).get("sessionId")
    if sid:
        for sess in (Path.home() / ".grok" / "sessions").glob(f"*/{sid}"):
            for sub in ("images", "videos"):
                d = sess / sub
                if d.is_dir():
                    for p in sorted(d.iterdir(), key=lambda q: q.stat().st_mtime, reverse=True):
                        if p.stat().st_mtime >= started - 5:
                            add_path(p)
    for sub in ("images", "videos", "."):
        d = work_dir / sub
        if d.is_dir():
            for p in d.iterdir():
                if p.is_file() and p.stat().st_mtime >= started - 5:
                    add_path(p)
    return cands


def verify_image(path: Path) -> dict:
    from PIL import Image
    im = Image.open(path)
    im.load()
    if im.width < 64 or im.height < 64:
        fail(f"output image too small: {im.size}", 4)
    return {"width": im.width, "height": im.height, "mode": im.mode}


def video_info(path: Path) -> dict:
    """ffprobe summary: width, height, duration, fps, codec, pixFmt, nbFrames, hasAudio."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        fail("ffprobe not found on PATH", 1)
    out = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
                         capture_output=True, text=True).stdout
    data = json.loads(out or "{}")
    vs = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    if vs is None:
        fail(f"no video stream in {path}", 4)
    rate = vs.get("avg_frame_rate") or vs.get("r_frame_rate") or "0/1"
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except ValueError:
        fps = float(rate)
    duration = float(data.get("format", {}).get("duration") or vs.get("duration") or 0.0)
    return {"width": int(vs["width"]), "height": int(vs["height"]), "duration": duration, "fps": fps,
            "codec": vs.get("codec_name"), "pixFmt": vs.get("pix_fmt"), "nbFrames": int(vs.get("nb_frames") or 0),
            "hasAudio": any(s.get("codec_type") == "audio" for s in data.get("streams", []))}


def verify_video(path: Path) -> dict:
    info = video_info(path)
    if info["duration"] < 0.5:
        fail(f"output video too short: {info['duration']}s", 4)
    return info


def run_tool(tool: str, args: dict, out: Path, work_dir: Path, timeout: int, dry_run: bool, is_image: bool) -> int:
    instruction = build_instruction(tool, args)
    cmd = [str(grok_bin()), "-p", instruction, "--verbatim", "--output-format", "streaming-json", "--no-plan",
           "--max-turns", "4", "--tools", tool, "--cwd", str(work_dir)]
    if dry_run:
        print(json.dumps({"ok": True, "dryRun": True, "tool": tool, "args": args, "cmd": cmd}, ensure_ascii=False, indent=2))
        return 0
    work_dir.mkdir(parents=True, exist_ok=True)
    log = work_dir / "grok-stream.ndjson"
    started = time.time()
    # stdout goes straight to the evidence file so a timeout / kill still leaves the partial stream behind
    with log.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.PIPE, text=True, cwd=str(work_dir))
        try:
            _, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            fail(f"grok timed out after {timeout}s", 2, {"tool": tool, "stream": str(log)})
    parsed = parse_stream(log.read_text(encoding="utf-8", errors="replace"))
    end = parsed["end"] or {}
    summary = {"tool": tool, "sessionId": end.get("sessionId"), "stopReason": end.get("stopReason"),
               "costUsd": end.get("total_cost_usd"), "seconds": round(time.time() - started, 1), "stream": str(log),
               "toolCalls": len(parsed["toolCalls"]), "toolResults": len(parsed["results"])}
    if proc.returncode != 0 and not parsed["results"]:
        msg = (stderr or "").strip()[:400] or parsed["text"][:400]
        if re.search(r"\b(401|403)\b|unauthori[sz]ed|forbidden|not logged in|login", msg, re.I):
            msg += " — run `grok login` and retry"
        fail(f"grok exited {proc.returncode}: {msg}", 2, summary)
    if parsed["errors"]:
        msgs = [s for e in parsed["errors"] for s in walk_strings(e.get("content") or e.get("rawOutput") or [])]
        fail("tool reported an error: " + " | ".join(msgs)[:600], 2, summary)
    if not parsed["toolCalls"]:
        fail("grok never called the tool: " + parsed["text"][:400], 2, summary)
    cands = candidate_paths(parsed, work_dir, started, IMAGE_EXT if is_image else VIDEO_EXT)
    if not cands:
        detail = " | ".join(s for r in parsed["results"] for s in walk_strings(r.get("rawOutput") or r.get("content") or []))[:400]
        fail("no output file found in tool results, reply text, session folder or work dir: " + (detail or parsed["text"][:200]), 3, summary)
    src = cands[0]
    out.parent.mkdir(parents=True, exist_ok=True)
    if is_image and src.suffix.lower() != ".png":
        from PIL import Image
        Image.open(src).convert("RGB").save(out)
    else:
        shutil.copy2(src, out)
    info = verify_image(out) if is_image else verify_video(out)
    summary.update({"ok": True, "out": str(out.resolve()), "source": str(src), "sourceFormat": src.suffix.lower().lstrip("."),
                    "bytes": out.stat().st_size, **info})
    print(json.dumps(summary, ensure_ascii=False))
    return 0


def read_prompt(a) -> str:
    if a.prompt_file:
        return Path(a.prompt_file).read_text(encoding="utf-8").strip()
    if a.prompt is not None:
        return a.prompt.strip()
    return ""


def abs_images(paths) -> list[str]:
    out = []
    for p in paths or []:
        q = Path(p).expanduser().resolve()
        if not q.is_file():
            fail(f"image not found: {q}", 1)
        out.append(str(q))
    return out


def cmd_doctor(a) -> int:
    """Offline by default: binary, version, auth file present, ffmpeg/ffprobe, PIL. --online also runs `grok models`."""
    report = {"grok": None, "version": None, "auth": None, "login": None, "ffmpeg": shutil.which("ffmpeg"),
              "ffprobe": shutil.which("ffprobe"), "python": sys.version.split()[0], "modules": {}}
    gb = find_grok()
    if gb:
        report["grok"] = str(gb)
        try:
            report["version"] = subprocess.run([str(gb), "--version"], capture_output=True, text=True, timeout=20).stdout.strip()
        except Exception as exc:  # pragma: no cover
            report["version"] = f"error: {exc}"
    auth = Path.home() / ".grok" / "auth.json"
    report["auth"] = "present" if auth.is_file() and auth.stat().st_size > 2 else "missing — run `grok login`"
    if a.online and gb:
        try:
            r = subprocess.run([str(gb), "models"], capture_output=True, text=True, timeout=40)
            blob = (r.stdout + r.stderr).lower()
            report["login"] = "logged in" if "logged in" in blob else (r.stdout + r.stderr).strip()[:200]
        except Exception as exc:  # pragma: no cover
            report["login"] = f"error: {exc}"
    for mod in ("PIL",):
        try:
            __import__(mod)
            report["modules"][mod] = True
        except Exception:
            report["modules"][mod] = False
    report["ok"] = bool(gb and report["auth"] == "present" and report["ffmpeg"] and report["ffprobe"] and report["modules"].get("PIL"))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("doctor", help="check grok CLI, auth file, ffmpeg/ffprobe, PIL (offline; --online also runs `grok models`)")
    p.add_argument("--online", action="store_true")
    p.set_defaults(fn=cmd_doctor)

    def common(p, video: bool):
        p.add_argument("-o", "--out", required=True)
        p.add_argument("--prompt")
        p.add_argument("--prompt-file")
        p.add_argument("--image", action="append")
        p.add_argument("--work-dir")
        p.add_argument("--timeout", type=int, default=720 if video else 300)
        p.add_argument("--dry-run", action="store_true")

    p = sub.add_parser("image", help="image_gen: text-to-image at a chosen aspect (cover, hook base, plates, badge)")
    common(p, False)
    p.add_argument("--aspect", default="3:4")
    p.set_defaults(fn=run_image)
    p = sub.add_parser("edit", help="image_edit: edit / restyle an existing image (output inherits the input aspect)")
    common(p, False)
    p.add_argument("--aspect", default="auto")
    p.set_defaults(fn=run_edit)
    p = sub.add_parser("i2v", help="image_to_video: animate a base image (first frame locked, aspect inherited)")
    common(p, True)
    p.add_argument("--duration", type=int, default=6)
    p.add_argument("--resolution", default="480p")
    p.set_defaults(fn=run_i2v)
    p = sub.add_parser("r2v", help="reference_to_video: 1-15s clip from reference images (first frame not locked)")
    common(p, True)
    p.add_argument("--aspect", default="1:1")
    p.add_argument("--duration", type=int, default=4)
    p.add_argument("--resolution", default="480p")
    p.set_defaults(fn=run_r2v)
    a = ap.parse_args()
    return a.fn(a)


def work_dir_of(a) -> Path:
    return Path(a.work_dir).expanduser().resolve() if a.work_dir else Path(a.out).expanduser().resolve().parent


def run_image(a) -> int:
    prompt = read_prompt(a)
    if not prompt:
        fail("image needs --prompt/--prompt-file", 1)
    if a.image:
        fail("image is text-to-image; use `edit --image` to start from an existing image", 1)
    if a.aspect not in ASPECTS or a.aspect == "auto":
        fail(f"image needs an explicit --aspect, one of {sorted(ASPECTS - {'auto'})}", 1)
    args = {"prompt": prompt, "aspect_ratio": a.aspect}
    return run_tool("image_gen", args, Path(a.out).expanduser().resolve(), work_dir_of(a), a.timeout, a.dry_run, True)


def run_edit(a) -> int:
    prompt = read_prompt(a)
    images = abs_images(a.image)
    if not prompt or not images:
        fail("edit needs --prompt/--prompt-file and at least one --image", 1)
    if len(images) > 5:
        fail("image_edit accepts at most 5 reference images", 1)
    if a.aspect not in ASPECTS:
        fail(f"aspect must be one of {sorted(ASPECTS)}", 1)
    args = {"prompt": prompt, "image": images}
    if len(images) > 1 and a.aspect != "auto":
        args["aspect_ratio"] = a.aspect
    return run_tool("image_edit", args, Path(a.out).expanduser().resolve(), work_dir_of(a), a.timeout, a.dry_run, True)


def run_i2v(a) -> int:
    images = abs_images(a.image)
    if len(images) != 1:
        fail("i2v needs exactly one --image", 1)
    if a.duration not in (6, 10):
        fail("image_to_video duration must be 6 or 10", 1)
    if a.resolution not in RESOLUTIONS:
        fail("resolution must be 480p or 720p", 1)
    args = {"image": images[0], "duration": a.duration, "resolution_name": a.resolution}
    prompt = read_prompt(a)
    if prompt:
        args["prompt"] = prompt
    return run_tool("image_to_video", args, Path(a.out).expanduser().resolve(), work_dir_of(a), a.timeout, a.dry_run, False)


def run_r2v(a) -> int:
    prompt = read_prompt(a)
    images = abs_images(a.image)
    if not prompt or not images:
        fail("r2v needs --prompt and at least one --image", 1)
    if len(images) > 7:
        fail("reference_to_video accepts at most 7 images", 1)
    if not (1 <= a.duration <= 15):
        fail("reference_to_video duration must be 1..15", 1)
    if a.aspect not in ASPECTS or a.aspect == "auto":
        fail("r2v needs an explicit --aspect such as 1:1", 1)
    if a.resolution not in RESOLUTIONS:
        fail("resolution must be 480p or 720p", 1)
    args = {"prompt": prompt, "images": images, "aspect_ratio": a.aspect, "duration": a.duration, "resolution_name": a.resolution}
    return run_tool("reference_to_video", args, Path(a.out).expanduser().resolve(), work_dir_of(a), a.timeout, a.dry_run, False)


if __name__ == "__main__":
    raise SystemExit(main())
