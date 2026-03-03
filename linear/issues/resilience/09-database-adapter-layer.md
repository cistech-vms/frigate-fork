# Fase 09 - Camada de Adapter para Banco de Dados

## Metadados para Linear
- Trilha/Epic sugerido: Resilience
- Prioridade sugerida: P3
- Labels sugeridas: resilience,headless,runtime,phase-09
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/resilience/phase-09-database-adapter-layer.md

## Contexto do projeto atual
- Runtime headless ativo em `frigate/api/headless.py` e `frigate/headless/*`.
- Pipeline de eventos atual passa por `frigate/comms/dispatcher.py` e `frigate/comms/sse.py`.
- Persistencia principal ainda orientada a SQLite local (`frigate/db/sqlitevecq.py`).

## Objetivo
Nesta fase eu modularizo a persistência com padrão Adapter para suportar `sqlite`, `mysql` e `postgresql` sem espalhar condicionais de banco no core.

## Escopo da issue
- Definir contrato único de persistência (`DatabaseAdapter`) para operações de runtime.
- Criar adapters concretos:
- Introduzir fábrica de adapters por ENV (`FRIGATE_DB_DRIVER`).
- Isolar migrações e diferenças de SQL por backend.
- Manter compatibilidade com o modo edge local padrão (`sqlite`).

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Definir contrato único de persistência (`DatabaseAdapter`) para operações de runtime.
- [ ] Criar adapters concretos:
- [ ] Introduzir fábrica de adapters por ENV (`FRIGATE_DB_DRIVER`).
- [ ] Isolar migrações e diferenças de SQL por backend.
- [ ] Manter compatibilidade com o modo edge local padrão (`sqlite`).

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
