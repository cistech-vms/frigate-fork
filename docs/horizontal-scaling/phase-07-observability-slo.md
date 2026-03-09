# Fase 07 - Observabilidade e SLO

## Objetivo
Medir capacidade real e estabelecer SLOs por tenant/nó.

## Entregáveis
- Métricas por shard: ingest fps, detect latency p95/p99, queue depth, drop rate.
- Dashboard de capacidade e saturação.
- SLOs e alertas acionáveis.

## Implementação aplicada
- Snapshot SLO de scaling em `GET /v1/scaling/slo`.
- Métricas de shard e pipeline com critérios objetivos (`latency_ok`, `queue_ok`, `drop_ok`).
- Base para alerta operacional orientado a saturação por nó/tenant.
