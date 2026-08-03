#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/source-videos"
WORK_DIR="$ROOT_DIR/tmp/video"
OUT_DIR="$ROOT_DIR/assets"
OUT_FILE="$OUT_DIR/l205-teaching-highlights.mp4"

mkdir -p "$WORK_DIR" "$OUT_DIR"

declare -a CLIPS=(
  "intro.mp4:0:18"
  "catastro.mp4:120:20"
  "lecture_attrib.mp4:180:22"
  "mech1.mp4:120:20"
  "mech2.mp4:120:20"
  "end.mp4:0:20"
)

index=0
inputs=()
filters=()
concat_inputs=""

for clip in "${CLIPS[@]}"; do
  IFS=":" read -r name start duration <<< "$clip"
  src="$SOURCE_DIR/$name"
  if [[ ! -f "$src" ]]; then
    echo "Missing $src" >&2
    echo "Copy the source videos into $SOURCE_DIR with these exact names, then run this script again." >&2
    exit 1
  fi

  inputs+=("-ss" "$start" "-t" "$duration" "-i" "$src")
  filters+=("[$index:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,format=yuv420p[v$index]")
  filters+=("[$index:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=1.0[a$index]")
  concat_inputs+="[v$index][a$index]"
  index=$((index + 1))
done

filter_graph="$(IFS=';'; echo "${filters[*]}");${concat_inputs}concat=n=${#CLIPS[@]}:v=1:a=1[v][a]"

ffmpeg -y \
  "${inputs[@]}" \
  -filter_complex "$filter_graph" \
  -map "[v]" \
  -map "[a]" \
  -c:v libx264 \
  -preset medium \
  -crf 22 \
  -c:a aac \
  -b:a 160k \
  -movflags +faststart \
  "$OUT_FILE"

echo "Created $OUT_FILE"
