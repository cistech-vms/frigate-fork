# Deploy Ubuntu + NVIDIA

Este guia prepara a branch headless para um host Ubuntu com Docker e GPU NVIDIA.

## Artefatos adicionados para deploy

- `docker-compose.prod.yml`: compose de producao para Frigate headless + MQTT.
- `.env.production.example`: base segura para gerar `.env` local.
- `config/config.headless.example.yml`: configuracao minima inicial.
- `scripts/bootstrap_headless_deploy.sh`: bootstrap idempotente de `.env` e `config/config.yml`.
- `scripts/render_hmac_headers.py`: helper para assinar requests HMAC da API.

## Bootstrap inicial

No host remoto, a partir da raiz do repositorio:

```bash
bash scripts/bootstrap_headless_deploy.sh --tenant-id tenant-local
```

Isso vai:

- criar `.env` se nao existir
- gerar segredos HMAC/JWT se estiverem ausentes ou com placeholder
- criar `config/config.yml` minimo se nao existir
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
```

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
curl http://127.0.0.1:5000/v1/status \
  $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-reader --curl)
```

Para um POST com JSON:

```bash
cat > payload.json <<'JSON'
{"cameras":{}}
JSON

curl -X POST http://127.0.0.1:5000/v1/config/validate \
  -H 'Content-Type: application/json' \
  --data @payload.json \
  $(python3 scripts/render_hmac_headers.py --env-file .env --key-id edge-admin --body-file payload.json --curl)
```

## Rotacionar credenciais de API

```bash
bash scripts/bootstrap_headless_deploy.sh --force-rotate-api-secrets --tenant-id tenant-local
```

Apos rotacionar, reinicie o container para recarregar o `.env`:

```bash
docker compose -f docker-compose.prod.yml up -d --force-recreate frigate
```
