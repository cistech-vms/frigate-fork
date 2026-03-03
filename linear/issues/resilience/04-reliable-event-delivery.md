# Fase 04 - Entrega Confiável de Eventos

## Metadados para Linear
- Trilha/Epic sugerido: Resilience
- Prioridade sugerida: P2
- Labels sugeridas: resilience,headless,runtime,phase-04
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/resilience/phase-04-reliable-event-delivery.md

## Contexto do projeto atual
- Runtime headless ativo em `frigate/api/headless.py` e `frigate/headless/*`.
- Pipeline de eventos atual passa por `frigate/comms/dispatcher.py` e `frigate/comms/sse.py`.
- Persistencia principal ainda orientada a SQLite local (`frigate/db/sqlitevecq.py`).

## Objetivo
Nesta fase eu torno a entrega de eventos previsível e auditável, mesmo com instabilidade de webhook/MQTT.

## Escopo da issue
- Adicionar fila de saída com retry exponencial e jitter.
- Definir limites de tentativa e encaminhamento para dead-letter.
- Persistir status de entrega para inspeção operacional.
- Tornar idempotência explícita por `event_id` e `delivery_id`.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Adicionar fila de saída com retry exponencial e jitter.
- [ ] Definir limites de tentativa e encaminhamento para dead-letter.
- [ ] Persistir status de entrega para inspeção operacional.
- [ ] Tornar idempotência explícita por `event_id` e `delivery_id`.

3. Integracao com runtime e API
- [ ] Garantir compatibilidade com endpoints headless e fluxo de configuracao efetiva.
- [ ] Validar comportamento em cenarios de erro, retry e degradacao.
- [ ] Garantir isolamento por tenant quando aplicavel.

4. Observabilidade e seguranca
- [ ] Expor metricas e logs estruturados para os novos fluxos.
- [ ] Adicionar trilha de auditoria para mudancas operacionais criticas.
- [ ] Revisar controles de auth/rbac/rate-limit relacionados.

5. Testes e validacao
- [ ] Adicionar/atualizar testes unitarios e de integracao para os caminhos alterados.
- [ ] Executar teste de carga/estabilidade proporcional ao risco da fase.
- [ ] Anexar evidencias de validacao para aprovacao.

6. Entrega e documentacao
- [ ] Atualizar documentacao tecnica e runbook operacional.
- [ ] Definir criterio de go/no-go e plano de rollback.
- [ ] Publicar changelog de comportamento e impactos esperados.

## Criterios de aceite
- Evidencias de teste e validacao anexadas
- Documentacao atualizada
- Sem regressao funcional nas rotas e no pipeline afetado

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
