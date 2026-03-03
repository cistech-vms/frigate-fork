# Fase 04 - Politica Inteligente de Regioes e Agenda de ROI

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P2
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-04
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-04-smart-region-policy-and-roi-scheduling.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu torno demarcacoes de regiao dinamicas por contexto para melhorar precisao operacional.

## Escopo da issue
- Definir perfis de ROI por horario e dia da semana.
- Aplicar mascaras dinamicas para fontes de ruido recorrente.
- Ajustar modo de regiao (`inside`, `crossing`, `enter_exit`) por periodo.
- Versionar mudancas de geometria e politica de regiao.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Definir perfis de ROI por horario e dia da semana.
- [x] Aplicar mascaras dinamicas para fontes de ruido recorrente.
- [x] Ajustar modo de regiao (`inside`, `crossing`, `enter_exit`) por periodo.
- [x] Versionar mudancas de geometria e politica de regiao.

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
- Reducao de ruido em horarios conhecidos.
- Melhor acerto em zonas criticas.
- Mudancas rastreaveis por versao.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Configuracao de agenda de ROI adicionada no schema de `detect`.
- Runtime com selecao dinamica de perfil por dia/hora e aplicacao de mascara/escala.
- Modos de zona periodicos implementados no tracking (`inside`, `crossing`, `enter_exit`).
- Metricas de perfil ROI ativo e versao expostas em stats e Prometheus.
- Testes de configuracao adicionados para agenda de ROI e validacao de formato horario.
