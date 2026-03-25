#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

MODEL_SIZE="t"
IMG_SIZE="320"
OUTPUT_DIR="${repo_dir}/config/model_cache"
OUTPUT_NAME="yolo.onnx"

usage() {
  cat <<'USAGE'
Usage:
  scripts/export_yolov9_onnx.sh [options]

Options:
  --model-size VALUE    YOLOv9 model size. Default: t
  --img-size VALUE      Export image size. Default: 320
  --output-dir PATH     Destination directory. Default: config/model_cache
  --output-name VALUE   Output file name. Default: yolo.onnx
  -h, --help            Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --model-size)
      MODEL_SIZE="$2"
      shift 2
      ;;
    --img-size)
      IMG_SIZE="$2"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="$2"
      shift 2
      ;;
    --output-name)
      OUTPUT_NAME="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

mkdir -p "$OUTPUT_DIR"

if [[ ! -w "$OUTPUT_DIR" ]]; then
  echo "Output directory is not writable: $OUTPUT_DIR" >&2
  exit 2
fi

cd "$repo_dir"

docker build .   --build-arg MODEL_SIZE="$MODEL_SIZE"   --build-arg IMG_SIZE="$IMG_SIZE"   --output "$OUTPUT_DIR"   -f- <<EOF
FROM python:3.11 AS build
RUN apt-get update && apt-get install --no-install-recommends -y     libgl1     git     cmake     build-essential     wget     && rm -rf /var/lib/apt/lists/*
WORKDIR /yolov9
RUN git clone --depth=1 https://github.com/WongKinYiu/yolov9.git .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir onnx==1.18.0 onnxruntime onnxsim onnxscript
ARG MODEL_SIZE
ARG IMG_SIZE
RUN wget -O yolov9-\${MODEL_SIZE}.pt https://github.com/WongKinYiu/yolov9/releases/download/v0.1/yolov9-\${MODEL_SIZE}-converted.pt
RUN sed -i "s/ckpt = torch.load(attempt_download(w), map_location='cpu')/ckpt = torch.load(attempt_download(w), map_location='cpu', weights_only=False)/g" models/experimental.py
RUN python3 export.py --weights ./yolov9-\${MODEL_SIZE}.pt --imgsz \${IMG_SIZE} --simplify --include onnx
FROM scratch
COPY --from=build /yolov9/yolov9-${MODEL_SIZE}.onnx /${OUTPUT_NAME}
EOF

echo "Modelo exportado em: ${OUTPUT_DIR}/${OUTPUT_NAME}"
