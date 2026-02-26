# Roadmap CMS Robusto (Monorepo + NestJS + Prisma)

Este diretório documenta o plano completo para construir um CMS robusto em monorepo, com backend em NestJS e camada de dados em Prisma.

## Objetivo
Eu vou estruturar uma plataforma CMS pronta para produção com foco em multi-tenant, segurança, consistência de dados, observabilidade e operação contínua.

## Stack base
- Monorepo: `pnpm workspaces` + `Turborepo`
- Backend: `NestJS` (REST + workers)
- Banco: `PostgreSQL`
- ORM: `Prisma`
- Cache/fila: `Redis`
- Mensageria assíncrona: `BullMQ`
- Armazenamento de mídia: `S3/R2`

## Fases
- `phase-00-vision-and-nfr.md`
- `phase-01-monorepo-foundation.md`
- `phase-02-nestjs-backend-bootstrap.md`
- `phase-03-prisma-data-modeling.md`
- `phase-04-auth-rbac-and-tenant-isolation.md`
- `phase-05-content-domain-and-editorial-flow.md`
- `phase-06-versioning-publishing-and-scheduling.md`
- `phase-07-media-pipeline-and-object-storage.md`
- `phase-08-api-contracts-and-webhooks.md`
- `phase-09-search-cache-and-performance-layer.md`
- `phase-10-observability-audit-and-compliance.md`
- `phase-11-test-strategy-and-release-gates.md`
- `phase-12-ci-cd-migrations-and-rollbacks.md`
- `phase-13-deployment-topology-and-sre-runbooks.md`
- `phase-14-evolution-roadmap-and-governance.md`
- `phase-15-frigate-event-control-and-configuration.md`

## Sequência de execução
Eu vou executar as fases na ordem acima, com critérios objetivos de aceite em cada etapa para bloquear avanço com débito técnico crítico.
