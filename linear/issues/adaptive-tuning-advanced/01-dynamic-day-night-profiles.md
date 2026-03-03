# Fase 01 - Perfis Dinamicos Dia e Noite

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P1
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-01
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-01-dynamic-day-night-profiles.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu aplico perfis de deteccao distintos por periodo para reduzir falso positivo em variacao de iluminacao.

## Escopo da issue
- Criar presets por camera para `day_profile` e `night_profile`.
- Ajustar `min_confidence`, `motion_threshold` e `min_area` por perfil.
- Definir troca automatica por horario e opcional por sensor de luminosidade.
- Registrar mudanca de perfil com auditoria.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Criar presets por camera para `day_profile` e `night_profile`.
- [ ] Ajustar `min_confidence`, `motion_threshold` e `min_area` por perfil.
- [ ] Definir troca automatica por horario e opcional por sensor de luminosidade.
- [ ] Registrar mudanca de perfil com auditoria.

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
- Comutacao sem interrupcao do pipeline.
- Queda de falso positivo em baixa luz.
- Sem regressao relevante de falso negativo.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
