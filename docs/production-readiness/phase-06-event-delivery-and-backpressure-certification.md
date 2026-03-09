# Fase 06 - Certificação de Entrega de Eventos e Backpressure

## Objetivo
Eliminar perda silenciosa e colapso de fila em picos.

## O que executar
- Validar fila de saída com retry/backoff/jitter e DLQ.
- Certificar prioridade de eventos críticos sob saturação.
- Exercitar reconciliação de pendências e recuperação após falha de destino.

## Critérios de aceite
- Eventos críticos sem perda silenciosa em cenários-alvo.
- Backlog convergente após burst.
- DLQ e reprocessamento auditáveis.
