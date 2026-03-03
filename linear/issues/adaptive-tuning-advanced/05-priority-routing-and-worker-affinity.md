# Fase 05 - Roteamento por Prioridade e Afinidade de Worker

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P2
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-05
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-05-priority-routing-and-worker-affinity.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu isolo cargas pesadas para reduzir interferencia entre cameras e aumentar previsibilidade.

## Escopo da issue
- Definir afinidade de cameras pesadas em workers dedicados.
- Separar roteamento por prioridade de evento.
- Aplicar quotas por tenant para evitar efeito domino.
- Ajustar concorrencia por shard conforme perfil real.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Definir afinidade de cameras pesadas em workers dedicados.
- [x] Separar roteamento por prioridade de evento.
- [x] Aplicar quotas por tenant para evitar efeito domino.
- [x] Ajustar concorrencia por shard conforme perfil real.

3. Integracao com runtime e API
- [ ] Garantir compatibilidade com endpoints headless e fluxo de configuracao efetiva.
- [ ] Validar comportamento em cenarios de erro, retry e degradacao.
- [ ] Garantir isolamento por tenant quando aplicavel.

4. Observabilidade e seguranca
- [x] Expor metricas e logs estruturados para os novos fluxos.
- [ ] Adicionar trilha de auditoria para mudancas operacionais criticas.
- [ ] Revisar controles de auth/rbac/rate-limit relacionados.

5. Testes e validacao
- [x] Adicionar/atualizar testes unitarios e de integracao para os caminhos alterados.
- [ ] Executar teste de carga/estabilidade proporcional ao risco da fase.
- [ ] Anexar evidencias de validacao para aprovacao.

6. Entrega e documentacao
- [ ] Atualizar documentacao tecnica e runbook operacional.
- [ ] Definir criterio de go/no-go e plano de rollback.
- [ ] Publicar changelog de comportamento e impactos esperados.

## Criterios de aceite
- Menor variancia de latencia entre cameras.
- Reducao de interferencia cruzada.
- Estabilidade maior em carga sustentada.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Duas filas de inferencia no runtime (`high-priority` e `normal`).
- Politica de roteamento por camera com prioridade, afinidade e quota.
- Afinidade e lane de processamento configuraveis por detector.
- Quota com shedding low-priority para conter efeito domino em saturacao.
- Metricas de roteamento adicionadas em stats e Prometheus.
- Testes de config e parser de payload de roteamento adicionados.
