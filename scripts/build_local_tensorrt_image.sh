#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

IMAGE_TAG="frigate:local-tensorrt"
CLEAN=0
COMPUTE_LEVEL=""

usage() {
  cat <<'USAGE'
Usage:
  scripts/build_local_tensorrt_image.sh [options]

Options:
  --tag VALUE           Image tag to publish locally. Default: frigate:local-tensorrt
  --compute-level VAL   Optional compute level passed to the TensorRT build.
  --clean               Run docker compose down + prune steps before build.
  -h, --help            Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tag)
      IMAGE_TAG="$2"
      shift 2
      ;;
    --compute-level)
      COMPUTE_LEVEL="$2"
      shift 2
      ;;
    --clean)
      CLEAN=1
      shift
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

cd "$repo_dir"

if [[ "$CLEAN" -eq 1 ]]; then
  docker compose -f docker-compose.prod.yml down --remove-orphans || true
  docker builder prune -af
  docker image prune -af
fi

cmd=(docker buildx bake --file docker/tensorrt/trt.hcl tensorrt --load --set "tensorrt.tags=${IMAGE_TAG}")
if [[ -n "$COMPUTE_LEVEL" ]]; then
  cmd+=(--set "*.args.COMPUTE_LEVEL=${COMPUTE_LEVEL}")
fi

"${cmd[@]}"

echo "Imagem TensorRT gerada: ${IMAGE_TAG}"
