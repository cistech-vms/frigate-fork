# Horizontal Scaling Plan (Cameras / Tenants)

## Objetivo
Mapear e executar a evolução do runtime para escalar horizontalmente por câmera e por tenant, reduzindo gargalos de processo único e banco local único.

## Diagnóstico rápido (estado atual)
- Runtime único por instância, com orquestração central em `frigate/app.py`.
- Fila de detecção compartilhada (`self.detection_queue`) para todas as câmeras.
- Banco SQLite local único (`self.config.database.path`) com concorrência limitada.
- API servida em único processo uvicorn (`host=127.0.0.1`, `port=5001`).
- Hot reload parcial, sem reconciliação distribuída.

## Fases do plano
1. `phase-00-current-state.md` - Mapeamento técnico e gargalos.
2. `phase-01-target-architecture.md` - Arquitetura-alvo (Control Plane x Data Plane).
3. `phase-02-api-contract-and-config-versioning.md` - Contratos de API/config/versionamento.
4. `phase-03-camera-sharding-and-assignment.md` - Sharding de câmeras e alocação.
5. `phase-04-runtime-partitioning.md` - Particionamento do runtime (workers por shard).
6. `phase-05-state-and-storage-strategy.md` - Estratégia de estado/armazenamento.
7. `phase-06-event-pipeline-and-backpressure.md` - Evento, fila e backpressure.
8. `phase-07-observability-slo.md` - Métricas, SLO e capacidade.
9. `phase-08-migration-rollout.md` - Migração/rollout/canary/rollback.

## Board de execução
- [x] Fase 00 - Mapeamento inicial
- [ ] Fase 01 - Arquitetura alvo detalhada
- [ ] Fase 02 - Contrato e versionamento
- [ ] Fase 03 - Sharding de câmeras
- [ ] Fase 04 - Particionamento runtime
- [ ] Fase 05 - Estado e storage
- [ ] Fase 06 - Pipeline de eventos
- [ ] Fase 07 - Observabilidade e SLO
- [ ] Fase 08 - Migração e rollout

## Critérios de sucesso
- Escala linear aproximada por adição de nós/shards.
- Limite de câmeras por instância definido por perfil (CPU/GPU/IO) e validado.
- Sem single-point de ingest/processamento para múltiplos tenants.
- Operação segura com rollback rápido por versão de config.
