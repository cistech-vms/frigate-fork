# Roadmap de Resiliência (Headless Runtime)

Este diretório consolida as novas fases que eu vou aplicar para elevar o Frigate headless a um nível de resiliência de produção.

## Objetivo
Eu vou endurecer o runtime para operar de forma confiável em edge-first, com fail-closed em segurança, persistência de estado operacional, readiness real, pipeline de eventos com retry e observabilidade orientada a SLO.

## Fases
- `phase-00-baseline-and-risk-register.md`
- `phase-01-auth-fail-closed-and-rbac-hardening.md`
- `phase-02-runtime-state-persistence.md`
- `phase-03-readiness-and-degradation-gates.md`
- `phase-04-reliable-event-delivery.md`
- `phase-05-distributed-rate-limit-and-abuse-control.md`
- `phase-06-chaos-recovery-and-self-healing.md`
- `phase-07-observability-slo-and-capacity-guardrails.md`
- `phase-08-test-matrix-and-release-gates.md`
- `phase-09-database-adapter-layer.md`
- `phase-10-redis-integration-layer.md`
- `phase-11-object-storage-s3-r2-integration.md`
- `phase-12-storage-consistency-and-reconciliation.md`

## Sequência de execução
Eu vou aplicar as fases na ordem acima. Cada fase fecha com critérios objetivos de aceite para evitar regressão funcional no core de detecção/track.

## Trilha avançada
- `advanced/README.md`
- `advanced/phase-13-backup-restore-rpo-rto.md`
- `advanced/phase-14-secrets-and-key-rotation.md`
- `advanced/phase-15-api-event-contract-versioning.md`
- `advanced/phase-16-schema-config-migrations.md`
- `advanced/phase-17-end-to-end-idempotency.md`
- `advanced/phase-18-operational-runbooks.md`
- `advanced/phase-19-disaster-recovery-plan.md`
- `advanced/phase-20-multi-tenant-isolation-and-quotas.md`
- `advanced/phase-21-supply-chain-and-image-hardening.md`
- `advanced/phase-22-load-and-chaos-validation.md`
