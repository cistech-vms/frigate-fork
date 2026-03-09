# Fase 06 - Pipeline de Eventos e Backpressure

## Objetivo
Garantir entrega estável de eventos sob carga alta.

## Entregáveis
- Fila de eventos com níveis de prioridade.
- Retry/DLQ para webhooks.
- Controle de burst e backpressure por tenant.
- Métricas de entrega, lag e taxa de erro.

## Implementação aplicada
- Pipeline com filas de prioridade (`high/normal/low`) por nó.
- Backpressure com drop controlado e registro em DLQ.
- Endpoints para publicar/processar eventos e inspecionar estado do pipeline.
