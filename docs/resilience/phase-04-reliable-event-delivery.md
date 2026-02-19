# Fase 04 - Entrega Confiável de Eventos

## Objetivo da fase
Nesta fase eu torno a entrega de eventos previsível e auditável, mesmo com instabilidade de webhook/MQTT.

## O que eu vou alterar
- Adicionar fila de saída com retry exponencial e jitter.
- Definir limites de tentativa e encaminhamento para dead-letter.
- Persistir status de entrega para inspeção operacional.
- Tornar idempotência explícita por `event_id` e `delivery_id`.

## Decisões técnicas tomadas
- Eu vou evitar bloqueio do pipeline principal de detecção.
- Eu vou tratar webhooks e MQTT como canais independentes de entrega.
- Eu vou expor métricas de sucesso, latência e falha por destino.

## Impacto no sistema
Perda silenciosa de eventos deixa de ser comportamento aceitável, com trilha clara de reprocessamento.

## Limitações atuais
Rate limiting ainda é local e precisa de estratégia distribuída quando houver múltiplos nós.

## Próximos passos
Eu trato controle de abuso e limitação distribuída na Fase 05.
