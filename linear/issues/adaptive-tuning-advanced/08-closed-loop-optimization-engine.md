# Fase 08 - Motor de Otimizacao em Loop Fechado

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P3
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-08
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-08-closed-loop-optimization-engine.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu conecto observabilidade, regra adaptativa e rollout em um ciclo continuo controlado.

## Escopo da issue
- Consolidar motor de decisao baseado em politicas.
- Definir janela de observacao e frequencia de ajuste.
- Aplicar limites de seguranca para evitar oscilacao.
- Congelar alteracoes automaticas em incidentes maiores.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Consolidar motor de decisao baseado em politicas.
- [x] Definir janela de observacao e frequencia de ajuste.
- [x] Aplicar limites de seguranca para evitar oscilacao.
- [x] Congelar alteracoes automaticas em incidentes maiores.

3. Integracao com runtime e API
- [ ] Garantir compatibilidade com endpoints headless e fluxo de configuracao efetiva.
- [ ] Validar comportamento em cenarios de erro, retry e degradacao.
- [ ] Garantir isolamento por tenant quando aplicavel.

4. Observabilidade e seguranca
- [x] Expor metricas e logs estruturados para os novos fluxos.
- [x] Adicionar trilha de auditoria para mudancas operacionais criticas.
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
- Ciclo automatico estavel sem flapping.
- Ganho sustentado de latencia e precisao.
- Controles de seguranca impedindo degradacao em cascata.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Motor de loop fechado implementado com politica de decisao e guardrails.
- Integracao observabilidade -> sugestao -> canary -> promocao/rollback.
- Freeze automatico em incidente maior e em sequencia de rollback.
- Endpoints para status e controle operacional do loop.
- Testes unitarios dedicados ao ciclo fechado.
