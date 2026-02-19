# Fase 04 - Particionamento do Runtime

## Objetivo
Implementar execução por shard no data-plane.

## Entregáveis
- Separação de filas por shard (detecção/eventos).
- Process groups isolados por shard/câmera set.
- Limites por shard (`max_queue`, `max_fps`, `drop_policy`).

## Resultado esperado
Redução de interferência entre câmeras e previsibilidade de latência por partição.
