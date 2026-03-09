# Fase 03 - Sharding de Câmeras e Alocação

## Objetivo
Separar carga por partições para evitar contenção global.

## Estratégia
- Chave de shard: `tenant_id + camera_id`.
- Alocação por capacidade de nó (CPU/GPU/decoder throughput).
- Rebalance com hysteresis (evitar flapping).

## Entregáveis
- Tabela de assignment por shard.
- Política de failover e reassignment.
- Limite máximo de câmeras por perfil de nó.

## Implementação aplicada
- Geração determinística de shard por `tenant_id + camera_id`.
- Tabela de assignment por shard exposta via `GET /v1/scaling/shards/status`.
- Rebalance com hysteresis e limite por nó via `POST /v1/scaling/shards/rebalance`.
