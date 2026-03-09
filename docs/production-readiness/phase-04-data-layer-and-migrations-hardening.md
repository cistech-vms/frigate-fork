# Fase 04 - Hardening de Camada de Dados e Migrações

## Objetivo
Evitar indisponibilidade e corrupção de estado em upgrades.

## O que executar
- Formalizar adapter de banco com suporte real aos drivers-alvo.
- Definir estratégia de migração forward/backward e backup pré-migração.
- Validar rollback de schema e configuração em staging.

## Critérios de aceite
- Migração idempotente com rollback testado.
- Evidência de restore pós-falha com RPO/RTO dentro da meta.
- Sem perda de estado crítico em cenários de reinício.
