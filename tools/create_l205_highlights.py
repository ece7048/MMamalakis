#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "source-videos"
WORK_DIR = ROOT / "tmp" / "video"
OUT_DIR = ROOT / "assets"
OUT_FILE = OUT_DIR / "l205-teaching-highlights.mp4"
REPORT_FILE = WORK_DIR / "l205-highlight-selection.json"


@dataclass(frozen=True)
class ClipSpec:
    filename: str
    label: str
    target_seconds: int
    scan_step: int
    skip_start: int = 40
    skip_end: int = 40


CLIPS = [
    ClipSpec("intro.mp4", "Opening: L205 teaching context", 15, 20, 0, 20),
    ClipSpec("catastro.mp4", "Catastrophic forgetting and model behaviour", 20, 45),
    ClipSpec("lecture_attrib.mp4", "Attribution and explainable AI", 25, 60),
    ClipSpec("mech1.mp4", "Mechanistic interpretability I", 20, 45),
    ClipSpec("mech2.mp4", "Mechanistic interpretability II", 25, 60),
    ClipSpec("end.mp4", "Closing: teaching and synthesis", 15, 30, 0, 20),
]

CURATED_STARTS = {
    # Selected after visual contact-sheet review to avoid desktop/setup moments
    # and keep the reel focused on polished lecture content.
    "intro.mp4": 190,
    "catastro.mp4": 540,
    "lecture_attrib.mp4": 2640,
    "mech1.mp4": 1629,
    "mech2.mp4": 2400,
    "end.mp4": 1431,
}


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def duration(path: Path) -> float:
    result = run([
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return float(result.stdout.strip())


def candidate_starts(total: float, spec: ClipSpec) -> list[int]:
    latest = max(0, int(total - spec.target_seconds - spec.skip_end))
    first = min(spec.skip_start, latest)
    if latest <= first:
        return [first]
    sample_count = min(12, max(4, math.ceil((latest - first) / max(spec.scan_step, 1)) + 1))
    starts = [int(round(value)) for value in np.linspace(first, latest, sample_count)]
    return sorted(set(starts))


def refine_starts(best: list[dict[str, object]], total: float, spec: ClipSpec) -> list[int]:
    latest = max(0, int(total - spec.target_seconds - spec.skip_end))
    stride = max(8, int(spec.scan_step / 4))
    refined: set[int] = set()
    for item in best[:2]:
        center = int(item["start"])
        for offset in (-2 * stride, -stride, 0, stride, 2 * stride):
            refined.add(min(latest, max(0, center + offset)))
    return sorted(refined)


def extract_frames(src: Path, start: int, seconds: int, dest: Path) -> list[Path]:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    pattern = dest / "frame_%03d.jpg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            str(start),
            "-t",
            str(seconds),
            "-i",
            str(src),
            "-vf",
            "fps=1/4,scale=320:-1",
            "-q:v",
            "4",
            str(pattern),
        ],
        check=True,
    )
    return sorted(dest.glob("frame_*.jpg"))


def frame_arrays(paths: list[Path]) -> list[np.ndarray]:
    arrays: list[np.ndarray] = []
    for path in paths:
        with Image.open(path) as img:
            arrays.append(np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0)
    return arrays


def score_frames(frames: list[np.ndarray]) -> float:
    if len(frames) < 2:
        return 0.0

    detail_scores = []
    saturation_scores = []
    brightness_scores = []
    for frame in frames:
        gray = frame.mean(axis=2)
        dx = np.abs(np.diff(gray, axis=1)).mean()
        dy = np.abs(np.diff(gray, axis=0)).mean()
        detail_scores.append(float(dx + dy))

        maxc = frame.max(axis=2)
        minc = frame.min(axis=2)
        saturation_scores.append(float((maxc - minc).mean()))

        brightness = float(gray.mean())
        brightness_scores.append(1.0 - min(1.0, abs(brightness - 0.52) / 0.52))

    motion_scores = []
    for prev, current in zip(frames, frames[1:]):
        motion_scores.append(float(np.abs(current - prev).mean()))

    detail = float(np.mean(detail_scores))
    motion = float(np.mean(motion_scores))
    saturation = float(np.mean(saturation_scores))
    brightness = float(np.mean(brightness_scores))

    # Emphasise lively teaching moments: motion plus visual detail, with mild
    # preference for well-lit, colorful frames over blank or static slides.
    return (motion * 5.0) + (detail * 2.2) + (saturation * 0.8) + (brightness * 0.3)


def choose_segment(spec: ClipSpec) -> dict[str, object]:
    src = SOURCE_DIR / spec.filename
    if not src.exists():
        raise FileNotFoundError(f"Missing {src}")

    total = duration(src)
    if spec.filename in CURATED_STARTS:
        start = min(int(CURATED_STARTS[spec.filename]), max(0, int(total - spec.target_seconds)))
        print(f"Using curated {spec.filename}: {start}s for {spec.target_seconds}s", flush=True)
        return {
            "file": spec.filename,
            "label": spec.label,
            "source_duration": round(total, 3),
            "chosen_start": start,
            "chosen_duration": spec.target_seconds,
            "score": None,
            "selection_method": "curated after visual contact-sheet review",
        }

    print(f"Scanning {spec.filename} ({round(total)}s)...", flush=True)
    starts = candidate_starts(total, spec)
    scored = []
    for start in starts:
        frame_dir = WORK_DIR / "frames" / src.stem / f"{start:06d}"
        frames = extract_frames(src, start, spec.target_seconds, frame_dir)
        score = score_frames(frame_arrays(frames))
        scored.append({"start": start, "duration": spec.target_seconds, "score": score})

    scored.sort(key=lambda item: item["score"], reverse=True)
    seen = {int(item["start"]) for item in scored}
    for start in refine_starts(scored, total, spec):
        if start in seen:
            continue
        frame_dir = WORK_DIR / "frames" / src.stem / f"{start:06d}"
        frames = extract_frames(src, start, spec.target_seconds, frame_dir)
        score = score_frames(frame_arrays(frames))
        scored.append({"start": start, "duration": spec.target_seconds, "score": score})
        seen.add(start)

    scored.sort(key=lambda item: item["score"], reverse=True)
    winner = scored[0]
    print(f"  selected {winner['start']}s for {spec.target_seconds}s", flush=True)
    return {
        "file": spec.filename,
        "label": spec.label,
        "source_duration": round(total, 3),
        "chosen_start": winner["start"],
        "chosen_duration": winner["duration"],
        "score": round(float(winner["score"]), 6),
        "top_candidates": [
            {"start": item["start"], "duration": item["duration"], "score": round(float(item["score"]), 6)}
            for item in scored[:5]
        ],
    }


def export_video(selections: list[dict[str, object]]) -> None:
    inputs: list[str] = []
    filters: list[str] = []
    concat_parts = []

    for idx, item in enumerate(selections):
        src = SOURCE_DIR / str(item["file"])
        start = str(item["chosen_start"])
        length = str(item["chosen_duration"])
        inputs.extend(["-ss", start, "-t", length, "-i", str(src)])
        filters.append(
            f"[{idx}:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
            f"pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
            f"fade=t=in:st=0:d=0.35,fade=t=out:st={float(length) - 0.35}:d=0.35,"
            f"format=yuv420p[v{idx}]"
        )
        filters.append(
            f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
            f"afade=t=in:st=0:d=0.25,afade=t=out:st={float(length) - 0.25}:d=0.25[a{idx}]"
        )
        concat_parts.append(f"[v{idx}][a{idx}]")

    filter_graph = ";".join(filters) + ";" + "".join(concat_parts) + f"concat=n={len(selections)}:v=1:a=1[v][a]"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-y",
        *inputs,
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "[a]",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "21",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        str(OUT_FILE),
    ]
    subprocess.run(cmd, check=True)


def main() -> int:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        print("ffmpeg and ffprobe are required.", file=sys.stderr)
        return 1

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    selections = [choose_segment(spec) for spec in CLIPS]
    REPORT_FILE.write_text(json.dumps(selections, indent=2) + "\n")
    export_video(selections)

    total = sum(int(item["chosen_duration"]) for item in selections)
    print(f"Created {OUT_FILE}")
    print(f"Duration target: {total} seconds")
    print(f"Wrote selection report: {REPORT_FILE}")
    for item in selections:
        start = int(item["chosen_start"])
        print(f"- {item['file']}: {start}s for {item['chosen_duration']}s ({item['label']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
