# Deploy Ubuntu + NVIDIA

Este guia prepara a branch headless para um host Ubuntu com Docker e GPU NVIDIA.

## Artefatos adicionados para deploy

- `docker-compose.prod.yml`: compose de producao para Frigate headless + MQTT com runtime NVIDIA.
- `.env.production.example`: base segura para gerar `.env` local.
- `config/config.headless.example.yml`: configuracao minima inicial para bootstrap seguro.
- `config/config.nvidia.onnx.example.yml`: exemplo de configuracao otimizada para decode NVIDIA + detector ONNX.
- `scripts/bootstrap_headless_deploy.sh`: bootstrap idempotente de `.env` e `config/config.yml`.
- `scripts/render_hmac_headers.py`: helper para assinar requests HMAC da API.

## Pre-requisitos do host

```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
```

Se os dois comandos mostrarem a GPU, o host esta pronto.

## Bootstrap inicial

No host remoto, a partir da raiz do repositorio:

```bash
bash scripts/bootstrap_headless_deploy.sh --tenant-id tenant-local
```

Se quiser iniciar ja com um config voltado para GPU NVIDIA + ONNX:

```bash
bash scripts/bootstrap_headless_deploy.sh   --tenant-id tenant-local   --config-template config/config.nvidia.onnx.example.yml
```

Isso vai:

- criar `.env` se nao existir
- gerar segredos HMAC/JWT se estiverem ausentes ou com placeholder
- criar `config/config.yml` se nao existir
- preparar a pasta `storage/`

## Subir os containers

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

## Verificacoes basicas

```bash
docker compose -f docker-compose.prod.yml ps
curl http://127.0.0.1:5000/healthz
curl http://127.0.0.1:5000/readyz
docker exec -it frigate-headless nvidia-smi
docker exec -it frigate-headless python3 -c "import onnxruntime as ort; print(ort.get_available_providers())"
```

## O que validar na configuracao

No `config.yml`, confirme estes pontos:

- `detectors.onnx.type: onnx`
- sem `detectors.cpu`
- `ffmpeg.hwaccel_args: preset-nvidia`
- stream principal para `record`
- substream para `detect`
- `detect.fps: 5`

## Instalador headless

```bash
docker exec -it frigate-headless python3 -m frigate install
```

Ou em etapas:

```bash
docker exec -it frigate-headless python3 -m frigate install status
docker exec -it frigate-headless python3 -m frigate install profile
docker exec -it frigate-headless python3 -m frigate install scan 192.168.1.0/24 --username admin --password 'SUA_SENHA'
docker exec -it frigate-headless python3 -m frigate install connect --all
docker compose -f docker-compose.prod.yml restart frigate
```

## Consumir a API com HMAC

Para um GET sem body:

```bash
curl http://127.0.0.1:5000/v1/status   $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-reader --curl)
```

Para um POST com JSON:

```bash
cat > payload.json <<'JSON'
{"cameras":{}}
JSON

curl -X POST http://127.0.0.1:5000/v1/config/validate   -H 'Content-Type: application/json'   --data @payload.json   $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-admin --body-file payload.json --curl)
```

## Rotacionar credenciais de API

```bash
bash scripts/bootstrap_headless_deploy.sh --force-rotate-api-secrets --tenant-id tenant-local
```

Apos rotacionar, reinicie o container para recarregar o `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate frigate
```
