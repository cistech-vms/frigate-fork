# CMS Remote Control Plane Integration (Frigate Headless)

## Objetivo
Definir e executar um plano para o Frigate subir em modo headless, autenticar em um CMS remoto, validar licenca e sincronizar configuracao de forma segura e auditavel.

## Escopo
- Bootstrap fail-closed com parametros obrigatorios.
- Autenticacao no CMS por token ou user/password.
- Enrollment do edge (`tenant_code`, `edge_id`, fingerprint).
- Validacao de licenca antes de liberar operacao plena.
- Download e apply de configuracao remota com canary/rollback.
- Operacao resiliente com `last_known_good` quando CMS indisponivel.
- Observabilidade, auditoria e testes de release.

## Fora de escopo
- Implementacao do CMS (control plane) em si.
- Mudancas em pipeline de deteccao que nao sejam necessarias para aplicacao de config.
- Billing/licensing server externo ao CMS.

## Fluxo alvo (resumo)
1. Frigate inicia em headless e carrega `local bootstrap config`.
2. Frigate autentica no CMS.
3. Frigate registra/valida identidade de edge.
4. Frigate valida licenca do tenant/edge.
5. Frigate baixa config efetiva versionada.
6. Frigate valida e aplica com seguranca (canary/rollback).
7. Frigate entra em `ready` e segue reconciliando periodicamente.

## Fases do plano
1. `phase-00-vision-and-nfr.md`
2. `phase-01-bootstrap-and-required-inputs.md`
3. `phase-02-cms-auth-and-session.md`
4. `phase-03-edge-enrollment-and-identity.md`
5. `phase-04-license-validation-and-policy.md`
6. `phase-05-config-sync-contract-and-download.md`
7. `phase-06-safe-apply-canary-rollback-and-lkg.md`
8. `phase-07-periodic-reconcile-and-offline-mode.md`
9. `phase-08-observability-security-and-audit.md`
10. `phase-09-test-matrix-and-rollout.md`

## Board de execucao
- [x] Fase 00 - Visao e NFR
- [x] Fase 01 - Bootstrap e entradas obrigatorias
- [x] Fase 02 - Auth no CMS e sessao
- [x] Fase 03 - Enrollment e identidade de edge
- [x] Fase 04 - Validacao de licenca
- [x] Fase 05 - Contrato de sync e download de config
- [x] Fase 06 - Apply seguro + canary + rollback + LKG
- [x] Fase 07 - Reconciliacao periodica e offline mode
- [x] Fase 08 - Observabilidade, seguranca e auditoria
- [x] Fase 09 - Testes, gates e rollout

## Implementacao aplicada
- Manager dedicado para integracao CMS remota com auth, enrollment, licenca e sync de config.
- Worker de reconciliacao periodica com persistencia de estado e `last_known_good`.
- Endpoints de operacao: `GET /v1/cms/status` e `POST /v1/cms/sync`.
- Enriquecimento de readiness com status/licenca CMS.
- Testes unitarios da trilha CMS e validacao de settings obrigatorios.

## Go/No-Go final da trilha
- `GET /v1/cms/status` retorna conectado e licenca valida.
- `GET /v1/production/readiness` retorna `summary.production_ready=true`.
- `GET /v1/resilience/release-gate` retorna `passed=true`.
- Sem regressao no pipeline principal de deteccao/tracking/eventos.
