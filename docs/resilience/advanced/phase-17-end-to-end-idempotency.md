# Fase 17 - Idempotência de Ponta a Ponta

## Objetivo da fase
Nesta fase eu removo efeitos colaterais de duplicidade em requisições e entregas de evento.

## O que eu vou alterar
- Definir `idempotency_key` para endpoints críticos.
- Persistir histórico curto de chaves processadas por tenant.
- Marcar eventos com identificadores estáveis de entrega.
- Garantir reprocessamento seguro sem duplicar ações externas.

## Decisões técnicas tomadas
- Eu vou padronizar janela temporal de idempotência.
- Eu vou priorizar idempotência em rotas de escrita e integração.
- Eu vou expor motivo de deduplicação para auditoria.

## Impacto no sistema
Retentativas de rede deixam de causar inconsistência funcional, especialmente em automações externas.

## Limitações atuais
Idempotência depende de retenção de estado adequada para não perder contexto de deduplicação.

## Próximos passos
Eu consolido runbooks operacionais por cenário de incidente.

## Implementação aplicada
- Store de idempotência com TTL e deduplicação por `tenant + request_key + payload_hash`.
- Enforcement em rotas críticas de escrita por `x-idempotency-key`.
- Endpoint de inspeção/validação para uso operacional e testes de integração.

## Evidência de operação
- `POST /v1/resilience/idempotency/check`
- `GET /v1/resilience/idempotency/status`
