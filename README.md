# Frigate Headless - Estado Atual do Projeto

## Sumário Executivo
Este repositório foi transformado para operar como **motor headless de visão computacional** (detecção, tracking e eventos), sem camada de interface gráfica local.

No estado atual:
- A pasta de frontend (`web/`) foi removida.
- O runtime visual legado (`frigate/output/` e `frigate/comms/ws.py`) foi removido.
- O bootstrap da API roda em modo headless por padrão.
- A operação é orientada por API + ENV + pipeline de eventos.

## Objetivo da Arquitetura Atual
O Frigate agora atua como **data-plane de borda** para ser controlado por um **control-plane externo** (CMS/cloud), com:
- configuração por ENV
- configuração dinâmica por API
- segurança por HMAC/JWT + RBAC
- eventos por MQTT e SSE

## Como o Sistema Está Organizado

### Núcleo de execução
- `frigate/__main__.py`: bootstrap e carregamento de configuração
- `frigate/app.py`: orquestração dos processos/threads principais
- `frigate/video.py`: captura e pipeline de frames
- `frigate/object_detection/*`: inferência/detecção
- `frigate/track/*`: tracking
- `frigate/events/*`: ciclo de eventos
- `frigate/record/*`: gravação/retenção/export

### Camada headless (nova)
- `frigate/headless/settings.py`: feature flags/ENV operacionais
- `frigate/headless/runtime_config.py`: store de config efetiva (merge/validação)
- `frigate/headless/security.py`: auth HMAC/JWT, RBAC, tenant e rate limit
- `frigate/api/headless.py`: endpoints operacionais (`/v1/*`, `/healthz`, `/readyz`, `/metrics`)
- `frigate/comms/sse.py`: stream de eventos via SSE

### API
- `frigate/api/fastapi_app.py` decide roteamento conforme modo headless.
- Em headless, somente routers operacionais são expostos.

## Fluxo de Configuração (Prioridade)
1. **Config runtime via API** (`/v1/config/apply`)
2. **Config via ENV** (`FRIGATE_CFG__...` e `FRIGATE_CONFIG_JSON`)
3. **Base/fallback validado** (`FrigateConfig`)

## Endpoints Headless Ativos

### Operacionais
- `GET /healthz`
- `GET /readyz`
- `GET /metrics` (se habilitado)
- `GET /v1/status`

### Configuração
- `POST /v1/config/apply`
- `POST /v1/config/validate`
- `GET /v1/config/effective`
- `POST /v1/reload`

### Triggers
- `POST /v1/triggers/upsert`
- `GET /v1/triggers`
- `DELETE /v1/triggers/{id}`

### Regiões
- `POST /v1/cameras/{camera_id}/regions/upsert`
- `GET /v1/cameras/{camera_id}/regions`
- `DELETE /v1/cameras/{camera_id}/regions/{region_id}`

### Stream de eventos
- `GET /v1/events/stream` (SSE)

## Segurança Aplicada
- Autenticação:
  - HMAC por request (`X-Key-Id`, `X-Timestamp`, `X-Signature`)
  - JWT HS256 (alternativa)
- RBAC mínimo:
  - `admin`
  - `reader`
- Tenant enforcement (`tenant_id`)
- Rate limit in-memory por chave/IP
- CORS bloqueado por padrão (allowlist opcional por ENV)
- Logging com suporte a JSON (`FRIGATE_LOG_FORMAT=json`)

## Build, Docker e CI
- Frontend removido da imagem final.
- `docker/main/Dockerfile` ajustado para headless.
- Healthcheck usa `http://127.0.0.1:5001/healthz`.
- CI de frontend removido do fluxo principal de PR.
- Exemplo de ENV em: `.env.example`.

## Estrutura Relevante no Repositório
- `frigate/` (core engine)
- `docker/` (imagens/build)
- `migrations/` (schema migrations)
- `docs/phase-*.md` (histórico técnico por fase)
- `.env.example` (configuração de referência)

## O que Foi Removido
- `web/` (UI completa)
- `frigate/output/` (pipeline de saída visual)
- `frigate/comms/ws.py` (websocket UI)
- dependências e passos de build vinculados ao frontend

## Limitações/Observações
- Ainda existem módulos de API legados no código-fonte (`frigate/api/media.py`, `frigate/api/preview.py`, etc.), mas não são parte do roteamento headless padrão.
- O rate limit atual é local ao processo (não distribuído).

## Validação Executada
- `python3 -m compileall frigate`
- `python3 -m unittest frigate.test.test_headless_runtime`

Resultado: compilação e testes mínimos da camada headless OK.

## Deploy Ubuntu + NVIDIA
- Compose de producao apontando para imagem TensorRT local: `docker-compose.prod.yml`
- Bootstrap de `.env` e config minima: `scripts/bootstrap_headless_deploy.sh`
- Exemplo de config GPU/ONNX seguro: `config/config.nvidia.onnx.example.yml`
- Export do modelo ONNX: `scripts/export_yolov9_onnx.sh`
- Build da imagem TensorRT local: `scripts/build_local_tensorrt_image.sh`
- Helper para assinar requests HMAC: `scripts/render_hmac_headers.py`
- Guia operacional: `docs/deploy-ubuntu-nvidia.md`
