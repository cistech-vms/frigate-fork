# Fase 01 - Otimizacao de Ingestao e Decode de Video

## Metadados para Linear
- Trilha/Epic sugerido: Optimization Precision Speed
- Prioridade sugerida: P1
- Labels sugeridas: optimization,latency,precision,phase-01
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/optimization-precision-speed/phase-01-video-ingest-and-decode-optimization.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu reduzo latencia e carga de CPU no caminho de entrada de video.

## Escopo da issue
- Padronizar uso de substream para deteccao.
- Ajustar FPS de deteccao por camera (3-5 como baseline).
- Reduzir resolucao de detect para o minimo eficaz por classe/cenario.
- Ativar aceleracao de decode por hardware quando disponivel.
- Revisar buffer de captura para evitar backlog oculto.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Padronizar uso de substream para deteccao.
- [ ] Ajustar FPS de deteccao por camera (3-5 como baseline).
- [ ] Reduzir resolucao de detect para o minimo eficaz por classe/cenario.
- [ ] Ativar aceleracao de decode por hardware quando disponivel.
- [ ] Revisar buffer de captura para evitar backlog oculto.

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
- Queda de uso de CPU no decode.
- Reducao de `queue_depth` sob carga equivalente.
- Sem perda relevante de precisao na validacao.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
