# Fase 03 - Runtime API

## Objetivo da fase
Nesta fase eu construí a API headless principal para controle de configuração e status operacional.

## O que foi alterado
Eu criei `frigate/api/headless.py` com:
- `POST /v1/config/apply`
- `POST /v1/config/validate`
- `GET /v1/config/effective`
- `POST /v1/reload`
- `GET /v1/status`
- `GET /healthz`
- `GET /readyz`
- `GET /metrics` (condicional)

## Decisões técnicas tomadas
Eu implementei validação forte antes de aplicar patch em runtime e resposta com `requires_restart`.
Eu preservei comportamento seguro: apenas alterações hot-reload explícitas são aplicadas imediatamente.

## Impacto no sistema
O Frigate passa a funcionar como data-plane gerenciável por API, sem dependência de UI local.

## Limitações atuais
A avaliação de `requires_restart` ainda está em nível top-level para algumas áreas.

## Próximos passos
Refinar diff por subsistema (decoder, detector, ffmpeg, output) para mensagens de restart mais detalhadas.
