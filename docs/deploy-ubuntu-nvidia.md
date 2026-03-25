# Deploy Ubuntu + NVIDIA

Este guia prepara a branch headless para um host Ubuntu com Docker e GPU NVIDIA usando TensorRT para inferencia via imagem local `frigate:local-tensorrt`.

## Artefatos adicionados para deploy

- `docker-compose.prod.yml`: compose de producao apontando para `${FRIGATE_IMAGE:-frigate:local-tensorrt}`.
- `.env.production.example`: define `FRIGATE_IMAGE` e `FRIGATE_GPU_DEVICE`.
- `config/config.headless.example.yml`: bootstrap minimo e seguro.
- `config/config.nvidia.onnx.example.yml`: bootstrap NVIDIA/ONNX sem cameras placeholder.
- `scripts/bootstrap_headless_deploy.sh`: bootstrap idempotente de `.env` e `config/config.yml`.
- `scripts/export_yolov9_onnx.sh`: exporta `config/model_cache/yolo.onnx`.
- `scripts/build_local_tensorrt_image.sh`: gera a imagem local `frigate:local-tensorrt`.
- `scripts/render_hmac_headers.py`: helper para assinar requests HMAC da API.

## Pre-requisitos do host

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
```

Se os dois comandos mostrarem a GPU, o host esta pronto.

## Bootstrap inicial

```bash
bash scripts/bootstrap_headless_deploy.sh --tenant-id tenant-local
```

Se quiser usar a base NVIDIA/ONNX logo no bootstrap:

```bash
bash scripts/bootstrap_headless_deploy.sh   --tenant-id tenant-local   --config-template config/config.nvidia.onnx.example.yml
```

## Limpeza antes de gerar as imagens

```bash
docker compose -f docker-compose.prod.yml down --remove-orphans || true
docker builder prune -af
docker image prune -af
docker container prune -f
docker volume prune -f
docker system df
```

## Gerar o modelo ONNX

```bash
bash scripts/export_yolov9_onnx.sh
ls -lah config/model_cache/yolo.onnx
```

## Gerar a imagem TensorRT local

```bash
bash scripts/build_local_tensorrt_image.sh
docker images | grep frigate | grep local-tensorrt
```

Se quiser limpar antes do build da imagem:

```bash
bash scripts/build_local_tensorrt_image.sh --clean
```

## Subir os containers

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f frigate
```

## Verificacoes basicas

```bash
docker exec -it frigate-headless nvidia-smi
docker exec -it frigate-headless python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

Para estar realmente em GPU, voce precisa ver `CUDAExecutionProvider` e/ou `TensorrtExecutionProvider`.
Se aparecer apenas `CPUExecutionProvider`, a imagem de inferencia em GPU nao entrou.

## O que validar no config.yml

- `detectors.onnx.type: onnx`
- sem `detectors.cpu`
- `model.path: /config/model_cache/yolo.onnx`
- `ffmpeg.hwaccel_args: preset-nvidia`
- `go2rtc.streams: {}` no bootstrap inicial
- `cameras: {}` no bootstrap inicial

## Consumir a API com HMAC

Para um GET sem body:

```bash
eval "curl http://127.0.0.1:5000/v1/status $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-reader --curl)"
```

Para um POST com JSON:

```bash
cat > payload.json <<'JSON'
{"cameras":{}}
JSON

eval "curl -X POST http://127.0.0.1:5000/v1/config/validate   -H 'Content-Type: application/json'   --data @payload.json   $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-admin --body-file payload.json --curl)"
```

## Instalador headless

```bash
docker exec -it frigate-headless python3 -m frigate install status
docker exec -it frigate-headless python3 -m frigate install profile
```

Depois do bootstrap limpo, conecte as cameras reais. Nao deixe `camera_exemplo` nem IPs ficticios em producao.
