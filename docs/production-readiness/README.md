# Production Readiness Roadmap

Este diretório consolida uma trilha completa para levar o projeto a nível de produção com foco em confiabilidade, segurança, performance, operação e governança.

## Objetivo
Fechar gaps técnicos e operacionais com gates objetivos para promoção segura em produção.

## Fases
- `phase-00-readiness-baseline-and-gap-analysis.md`
- `phase-01-environment-parity-and-dependencies.md`
- `phase-02-test-matrix-and-quality-gates.md`
- `phase-03-security-hardening-and-secret-governance.md`
- `phase-04-data-layer-and-migrations-hardening.md`
- `phase-05-distributed-state-and-rate-limit.md`
- `phase-06-event-delivery-and-backpressure-certification.md`
- `phase-07-observability-slo-and-alerting.md`
- `phase-08-performance-and-capacity-validation.md`
- `phase-09-disaster-recovery-and-backup-restore-drills.md`
- `phase-10-release-rollout-and-change-management.md`
- `phase-11-operational-runbooks-and-oncall-readiness.md`
- `phase-12-go-live-and-hypercare.md`
- `phase-13-post-go-live-optimization-and-governance.md`

## Regras de execução
- Cada fase só avança com evidências anexadas.
- Mudanças de alto risco exigem canário e rollback validado.
- Nenhuma fase substitui testes de regressão do core de detecção/tracking/eventos.

## Aplicação no Runtime
- Endpoint agregado de prontidão de produção: `GET /v1/production/readiness`
- Este endpoint consolida as fases `00..13` com:
- status por fase (`passed`, `in_progress`, `failed`)
- blockers e evidências por fase
- score geral e flag `production_ready`
