# Fase 02 - Contrato de API e Versionamento de Config

## Objetivo
Garantir aplicação consistente de config entre múltiplos nós.

## Entregáveis
- `config_version` obrigatório em payloads de apply.
- Regras de idempotência (`request_id`, `etag`, `if-match`).
- Estado de convergência por nó: `desired_version`, `applied_version`, `drift`.
- Endpoint de reconciliação por tenant/shard.

## Critérios
- Config inválida rejeitada antes de aplicar.
- Aplicação parcial deve retornar diff + `requires_restart` + `rollback_hint`.
