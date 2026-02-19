# Fase 06 - Event Pipeline

## Objetivo da fase
Nesta fase eu adaptei o pipeline de eventos para consumo headless por stream e automações.

## O que foi alterado
Eu criei `frigate/comms/sse.py` e integrei no `Dispatcher` como comunicador adicional.
Eu adicionei endpoints de triggers:
- `POST /v1/triggers/upsert`
- `GET /v1/triggers`
- `DELETE /v1/triggers/{id}`

Eu adicionei stream SSE em:
- `GET /v1/events/stream`

## Decisões técnicas tomadas
Eu reutilizei o modelo pub/sub interno do Frigate para evitar duplicação de pipeline de eventos.
Eu apliquei backpressure simples com fila bounded e descarte controlado do item mais antigo.

## Impacto no sistema
Clientes externos podem receber eventos em tempo real sem websocket de UI.

## Limitações atuais
As ações de trigger (kafka e callbacks avançados) estão previstas no contrato, mas parcialmente implementadas.

## Próximos passos
Ligar executor de ações assíncronas com retries, assinatura de webhook e DLQ.
