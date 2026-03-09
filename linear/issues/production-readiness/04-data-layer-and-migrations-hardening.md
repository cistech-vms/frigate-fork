# Fase 04 - Hardening de Camada de Dados e Migracoes

## Metadados para Linear
- Trilha/Epic sugerido: Production Readiness
- Prioridade sugerida: P0
- Labels sugeridas: production-readiness,data,migrations,phase-04
- Dependencia: Fase 03
- Documento de origem: docs/production-readiness/phase-04-data-layer-and-migrations-hardening.md

## Objetivo
Evitar indisponibilidade e corrupcao de estado durante upgrades de schema e configuracao.

## Escopo da issue
- Adapter de banco formal com drivers alvo.
- Estrategia de migracao forward/backward com backup pre-migracao.
- Validacao de rollback e restore com RPO/RTO alvo.

## Etapas detalhadas
1. Padrao de adaptador
- [ ] Definir contrato do adapter para banco suportado.
- [ ] Cobrir conexao, timeout, retry e fallback.
- [ ] Validar compatibilidade com fluxos criticos.

2. Migracao segura
- [ ] Definir ordem de migracoes e prechecks.
- [ ] Garantir idempotencia e rollback controlado.
- [ ] Automatizar backup antes da promocao.

3. Drill de recuperacao
- [ ] Simular falha durante migracao.
- [ ] Executar restore e reconciliacao.
- [ ] Medir RPO/RTO real e registrar evidencia.

## Criterios de aceite
- Migracao idempotente com rollback testado.
- Restore comprovado dentro de RPO/RTO meta.
- Sem perda de estado critico em reinicio/rollback.

## Riscos e pontos de atencao
- Migracao sem janela controlada pode travar runtime.
- Restore nao exercitado invalida confianca de producao.
