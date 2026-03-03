# Fase 01 - Arquitetura Alvo (Control Plane x Data Plane)

## Metadados para Linear
- Trilha/Epic sugerido: Horizontal Scaling
- Prioridade sugerida: P1
- Labels sugeridas: scaling,sharding,runtime,phase-01
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/horizontal-scaling/phase-01-target-architecture.md

## Contexto do projeto atual
- Orquestracao centralizada no processo principal em `frigate/app.py`.
- Filas e IPC locais em `frigate/comms/*` e multiprocessing.
- API local e estado por instancia, sem coordenacao multi-no nativa.

## Objetivo
Definir desenho-alvo para escala horizontal por tenant/câmera.

## Escopo da issue
- Control Plane (cloud)
- Cadastro de tenants, câmeras e políticas.
- Versionamento de configuração.
- Scheduler de alocação de câmeras por nó/shard.
- Rollout/canary/rollback.
- Data Plane (edge nodes)
- Runtime headless Frigate por nó.
- Cada nó executa N shards (process groups) com subset de câmeras.
- API local para status/aplicar config/version.
- Contrato entre planos
- Config declarativa versionada (`config_version`, `tenant_id`, `assigned_cameras`).
- Heartbeat periódico com carga/capacidade (`fps`, `queue_depth`, `inference_latency`).

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Control Plane (cloud)
- [ ] Cadastro de tenants, câmeras e políticas.
- [ ] Versionamento de configuração.
- [ ] Scheduler de alocação de câmeras por nó/shard.
- [ ] Rollout/canary/rollback.
- [ ] Data Plane (edge nodes)
- [ ] Runtime headless Frigate por nó.
- [ ] Cada nó executa N shards (process groups) com subset de câmeras.
- [ ] API local para status/aplicar config/version.
- [ ] Contrato entre planos
- [ ] Config declarativa versionada (`config_version`, `tenant_id`, `assigned_cameras`).
- [ ] Heartbeat periódico com carga/capacidade (`fps`, `queue_depth`, `inference_latency`).

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
