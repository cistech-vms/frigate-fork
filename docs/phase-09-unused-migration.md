# Fase 09 - Migração de Código Não Utilizado

## Objetivo
Isolar módulos legados que não participam do runtime headless atual para remoção definitiva posterior.

## O que foi movido para `nao_utilizado/`
- API legacy completa (rotas de UI e recursos não-headless):
  - `frigate/api/app.py`
  - `frigate/api/auth.py`
  - `frigate/api/camera.py`
  - `frigate/api/classification.py`
  - `frigate/api/event.py`
  - `frigate/api/export.py`
  - `frigate/api/media.py`
  - `frigate/api/notification.py`
  - `frigate/api/preview.py`
  - `frigate/api/review.py`
  - `frigate/api/defs/**`
- Testes HTTP da API legacy:
  - `frigate/test/http_api/**`
  - `frigate/test/test_proxy_auth.py`

## Ajustes para manter execução
- `frigate/api/fastapi_app.py` foi simplificado para headless-only.
- `hash_password` foi extraído para `frigate/security/password.py`.
- `frigate/app.py` passou a importar hash do novo módulo core.

## Resultado
- Runtime atual compila em modo headless sem dependências da API legacy movida.

## Próximo passo
- Revisar e remover permanentemente `nao_utilizado/` após validação final de regressão.
