# Refatoracao Arquitetural Headless

Esta trilha documenta a migracao incremental do Frigate Headless para uma arquitetura mais resiliente, declarativa e compativel com o contrato atual do `cms-app` e do dashboard.

## Restricao de Compatibilidade
Durante as fases iniciais, o contrato externo permanece estavel:
- `:5000` continua sendo o `baseUrl`
- `GET /healthz`, `GET /readyz`
- `GET /v1/status`
- `GET/POST /v1/config/*`
- `GET/POST /install/*`
- HMAC atual (`sha256(body + timestamp + secret)`)
- `tenant_id` no body e/ou `x-tenant-id`

## Direcao da Arquitetura
A arquitetura alvo separa explicitamente:
- Video Plane
- Control Plane Local
- Desired State
- Compiled Engine Config
- Operational State

## Documentos
1. `phase-00-contract-and-state-foundation.md`
2. `roadmap.md`

## Regra de evolucao
Nenhuma fase inicial pode quebrar `cms-app` ou dashboard. Se uma mudanca de contrato se tornar inevitavel, ela deve entrar apenas com compatibilidade retroativa, migracao planejada e aviso explicito.
