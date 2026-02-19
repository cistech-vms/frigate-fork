# Fase 04 - Regions API

## Objetivo da fase
Nesta fase eu implementei gerenciamento remoto de regiões por câmera para integração com control-plane externo.

## O que foi alterado
Eu adicionei endpoints:
- `POST /v1/cameras/{camera_id}/regions/upsert`
- `GET /v1/cameras/{camera_id}/regions`
- `DELETE /v1/cameras/{camera_id}/regions/{region_id}`

Eu modelei `polygon`, `bbox` e `mask` com metadata e passei a armazenar regiões por `tenant_id`.
Eu adicionei hot reload opcional para regiões poligonais mapeadas em zonas quando aplicável.

## Decisões técnicas tomadas
Eu mantive separação entre o formato externo de região (API) e o formato interno de zona (engine), com adaptação controlada.

## Impacto no sistema
O CMS externo consegue criar/editar/remover demarcações sem UI local.

## Limitações atuais
Nem todos os atributos avançados de zona interna foram expostos no primeiro contrato.

## Próximos passos
Adicionar validações geométricas mais robustas e mapeamento completo de filtros por objeto.
