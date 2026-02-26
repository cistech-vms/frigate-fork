# Fase 08 - Contratos de API e Webhooks

## Objetivo da fase
Nesta fase eu estabilizo integracao com consumidores externos via contratos versionados e webhooks confiaveis.

## O que eu vou alterar
- Versionar API (`/v1`) e payloads de eventos.
- Publicar contratos OpenAPI e schemas JSON para eventos.
- Implementar `WebhookSubscription` por tenant/evento.
- Adicionar entrega assinada com retry, DLQ e observabilidade.
- Incluir idempotency key em operacoes mutaveis criticas.

## Decisoes tecnicas tomadas
- Eu vou impedir mudanca breaking sem estrategia de migracao.
- Eu vou separar fila de webhooks do fluxo transacional principal.
- Eu vou usar assinatura HMAC por webhook para verificacao do consumidor.

## Criterios de aceite
- Contratos validados automaticamente no CI.
- Entrega de webhook com taxa de sucesso dentro do SLO.
- Reprocessamento seguro sem duplicidade funcional.

## Impacto no sistema
Integrações com CMS ficam previsiveis e auditaveis.

## Limitacoes atuais
Camada de busca e cache ainda sem otimização para escala alta.

## Proximos passos
Eu implemento busca, cache e performance na Fase 09.
