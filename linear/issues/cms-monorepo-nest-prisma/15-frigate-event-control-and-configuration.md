# Fase 15 - Controle de Eventos do Frigate e Configuracao Operacional

## Metadados para Linear
- Trilha/Epic sugerido: CMS Monorepo Nest Prisma
- Prioridade sugerida: P3
- Labels sugeridas: cms,control-plane,integration,phase-15
- Dependencia: Depende da fase anterior da mesma trilha
- Documento de origem: docs/cms-monorepo-nest-prisma/phase-15-frigate-event-control-and-configuration.md

## Contexto do projeto atual
- Projeto atual contem o data-plane headless (Frigate), nao o CMS em NestJS.
- Integracao CMS x Frigate deve usar endpoints em `frigate/api/headless.py` (`/v1/config/*`, `/v1/triggers/*`, `/v1/cameras/*/regions/*`).
- Esta trilha exige novo workspace/servico (control-plane) com contrato versionado.

## Objetivo
Nesta fase eu documento o contrato funcional para o CMS controlar configuracoes de eventos do Frigate por tenant, camera e regiao, incluindo sensibilidade, filtros e automacoes.

## Escopo da issue
- Demarcacao de regioes por camera.
- Sensibilidade de deteccao por contexto (global/camera/regiao).
- Regras de disparo por tipo de evento.
- Acoes por evento (webhook, fila, automacao interna).
- Janela de ativacao (horario, dia da semana, perfil).
- Versionamento, auditoria e rollback de configuracao.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] Demarcacao de regioes por camera.
- [ ] Sensibilidade de deteccao por contexto (global/camera/regiao).
- [ ] Regras de disparo por tipo de evento.
- [ ] Acoes por evento (webhook, fila, automacao interna).
- [ ] Janela de ativacao (horario, dia da semana, perfil).
- [ ] Versionamento, auditoria e rollback de configuracao.

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
- CMS consegue controlar regiao, sensibilidade e triggers por tenant.
- Validacao bloqueia configuracao invalida antes de aplicacao.
- Aplicacao de config e auditavel com autoria, horario e diff.
- Existe rollback funcional para versao anterior sem perda de rastreabilidade.

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
