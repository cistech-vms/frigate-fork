# Fase 06 - Canary de Configuracao e Rollback Automatico

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P2
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-06
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-06-canary-for-config-and-automatic-rollback.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu diminuo risco de tuning agressivo usando rollout progressivo por camera e tenant.

## Escopo da issue
- Aplicar mudancas primeiro em subset canario.
- Medir impacto em janelas curtas e medias.
- Promover automaticamente se metas forem cumpridas.
- Acionar rollback automatico em caso de degradacao.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Aplicar mudancas primeiro em subset canario.
- [x] Medir impacto em janelas curtas e medias.
- [x] Promover automaticamente se metas forem cumpridas.
- [x] Acionar rollback automatico em caso de degradacao.

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
- Nenhuma regressao ampla por configuracao ruim.
- Rollback automatico funcional e rapido.
- Evidencias de promocao/rollback armazenadas.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Runtime store com estado de canary, baseline, avaliacao e rollback/promocao automatica.
- `config/apply` com modo canary para subset de cameras.
- Endpoints de status e rollback manual para canary.
- Inclusao de estado de canary no `status` headless.
- Testes unitarios adicionados para snapshot, avaliacao de saude e rollback.
