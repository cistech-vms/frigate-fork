# Fase 18 - Runbooks Operacionais

## Metadados para Linear
- Trilha/Epic sugerido: Resilience Advanced
- Prioridade sugerida: P3
- Labels sugeridas: resilience,advanced,headless,phase-18
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/resilience/advanced/phase-18-operational-runbooks.md

## Contexto do projeto atual
- Runtime headless ativo em `frigate/api/headless.py` e `frigate/headless/*`.
- Pipeline de eventos atual passa por `frigate/comms/dispatcher.py` e `frigate/comms/sse.py`.
- Persistencia principal ainda orientada a SQLite local (`frigate/db/sqlitevecq.py`).

## Objetivo
Nesta fase eu transformo resposta a incidente em procedimento repetível, reduzindo tempo de diagnóstico e correção.

## Escopo da issue
- Criar runbooks para falhas comuns: storage offline, fila acumulada, nó degradado.
- Definir checklist de triagem por severidade.
- Formalizar comandos e validações de recuperação.
- Incluir critérios claros de escalonamento.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Criar runbooks para falhas comuns: storage offline, fila acumulada, nó degradado.
- [ ] Definir checklist de triagem por severidade.
- [ ] Formalizar comandos e validações de recuperação.
- [ ] Incluir critérios claros de escalonamento.

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
