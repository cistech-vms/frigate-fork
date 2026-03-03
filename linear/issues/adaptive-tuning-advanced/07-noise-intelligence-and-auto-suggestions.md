# Fase 07 - Inteligencia de Ruido e Sugestoes Automaticas

## Metadados para Linear
- Trilha/Epic sugerido: Adaptive Tuning Advanced
- Prioridade sugerida: P3
- Labels sugeridas: adaptive-tuning,noise-reduction,runtime,phase-07
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/adaptive-tuning-advanced/phase-07-noise-intelligence-and-auto-suggestions.md

## Contexto do projeto atual
- Caminho critico de video/inferencia em `frigate/video.py`, `frigate/detectors/*`, `frigate/track/*`.
- Regras/eventos em `frigate/events/*` e `frigate/api/headless.py`.
- Telemetria base em `frigate/stats/*` para suportar tuning orientado por metricas.

## Objetivo
Nesta fase eu transformo historico operacional em recomendacoes de tuning para reduzir trabalho manual.

## Escopo da issue
- Detectar regras com maior taxa de ruido por camera/regiao.
- Gerar sugestoes de ajuste (`threshold`, `cooldown`, ROI, mascara).
- Exibir impacto estimado antes de aplicar.
- Permitir aprovacao manual ou auto-aprovacao restrita.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [x] Detectar regras com maior taxa de ruido por camera/regiao.
- [x] Gerar sugestoes de ajuste (`threshold`, `cooldown`, ROI, mascara).
- [x] Exibir impacto estimado antes de aplicar.
- [x] Permitir aprovacao manual ou auto-aprovacao restrita.

3. Integracao com runtime e API
- [ ] Garantir compatibilidade com endpoints headless e fluxo de configuracao efetiva.
- [ ] Validar comportamento em cenarios de erro, retry e degradacao.
- [ ] Garantir isolamento por tenant quando aplicavel.

4. Observabilidade e seguranca
- [ ] Expor metricas e logs estruturados para os novos fluxos.
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
- Sugestoes com ganho mensuravel em ambiente piloto.
- Sem aumento relevante de falso negativo.
- Trilha de auditoria para cada sugestao aplicada.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.

## Evidencias desta iteracao
- Motor de noise intelligence com geracao de sugestoes por camera.
- Sugestoes com impacto estimado e patch aplicavel quando suportado.
- Endpoints para listar, aprovar e auditar sugestoes.
- Auto-aprovacao restrita a sugestoes de baixo risco.
- Testes unitarios para geracao de sugestoes em cenarios de carga/saude.
