# Fase 01 - Fundacao do Monorepo

## Objetivo da fase
Nesta fase eu estruturo o monorepo para suportar backend, bibliotecas compartilhadas e apps auxiliares com governanca unificada.

## O que eu vou alterar
- Criar workspace com `pnpm` e `turbo`.
- Definir layout base:
  - `apps/api` (NestJS)
  - `apps/worker` (processamento assincrono)
  - `packages/config`
  - `packages/types`
  - `packages/eslint-config`
  - `packages/tsconfig`
- Padronizar scripts de build, lint, test e typecheck por pacote.
- Configurar cache local/remoto de pipeline do monorepo.

## Decisoes tecnicas tomadas
- Eu vou manter versionamento unico do repositorio para simplificar release.
- Eu vou isolar configuracoes compartilhadas em pacotes reaproveitaveis.
- Eu vou bloquear drift de tooling com lockfile obrigatorio.

## Criterios de aceite
- Workspaces resolvendo dependencias corretamente.
- Pipeline `turbo run lint test build` funcional.
- Estrutura base documentada para onboarding.

## Impacto no sistema
O desenvolvimento fica mais rapido e previsivel, com reutilizacao de codigo entre apps.

## Limitacoes atuais
Ainda sem modulo funcional de dominio de CMS.

## Proximos passos
Eu inicializo o backend NestJS na Fase 02.
