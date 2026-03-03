# Fase 10 - Observabilidade, Auditoria e Compliance

## Metadados para Linear
- Trilha/Epic sugerido: CMS Monorepo Nest Prisma
- Prioridade sugerida: P3
- Labels sugeridas: cms,control-plane,integration,phase-10
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/cms-monorepo-nest-prisma/phase-10-observability-audit-and-compliance.md

## Contexto do projeto atual
- Projeto atual contem o data-plane headless (Frigate), nao o CMS em NestJS.
- Integracao CMS x Frigate deve usar endpoints em `frigate/api/headless.py` (`/v1/config/*`, `/v1/triggers/*`, `/v1/cameras/*/regions/*`).
- Esta trilha exige novo workspace/servico (control-plane) com contrato versionado.

## Objetivo
Nesta fase eu consolido visibilidade operacional e conformidade para reduzir risco tecnico e regulatorio.

## Escopo da issue
- Padronizar logs estruturados com `request_id`, `tenant_id` e `actor_id`.
- Expor metricas (latencia, erro, throughput, fila, cache, webhooks).
- Implementar tracing distribuido nas rotas criticas.
- Consolidar `AuditLog` para operacoes sensiveis.
- Definir politicas de retencao e acesso a logs por compliance.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Padronizar logs estruturados com `request_id`, `tenant_id` e `actor_id`.
- [ ] Expor metricas (latencia, erro, throughput, fila, cache, webhooks).
- [ ] Implementar tracing distribuido nas rotas criticas.
- [ ] Consolidar `AuditLog` para operacoes sensiveis.
- [ ] Definir politicas de retencao e acesso a logs por compliance.

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
- Dashboards e alertas cobrindo SLOs principais.
- Auditoria rastreando quem fez o que e quando.
- Evidencia de conformidade para trilha critica de dados.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
