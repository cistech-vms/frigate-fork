# Fase 03 - Frame Skip Adaptativo e Load Shedding

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P2
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-03
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-03-adaptive-frame-skip-and-load-shedding.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu protejo latencia do pipeline durante picos sem colapso global.

## Escopo da issue
- Ajustar frame skip conforme `queue_depth` e `inference_latency`.
- Priorizar classes e cameras criticas em saturacao.
- Aplicar shedding controlado em eventos de baixa prioridade.
- Restaurar modo normal automaticamente apos estabilizacao.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Ajustar frame skip conforme `queue_depth` e `inference_latency`.
- [x] Priorizar classes e cameras criticas em saturacao.
- [x] Aplicar shedding controlado em eventos de baixa prioridade.
- [x] Restaurar modo normal automaticamente apos estabilizacao.

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
- Fila deixa de crescer indefinidamente em pico.
- Eventos criticos mantem latencia dentro de meta.
- Recuperacao automatica apos burst.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Codigo atualizado para `adaptive_load_shedding` em runtime de deteccao/tracking.
- Metricas adicionadas em `stats_snapshot` e Prometheus para saturacao, skip e latencia.
- Testes unitarios adicionados para controlador adaptativo e validacoes de config.
- Validacao local de sintaxe executada com `python3 -m compileall` nos arquivos alterados.
