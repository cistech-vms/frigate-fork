# Fase 03 - Modelagem de Dados com Prisma

## Objetivo da fase
Nesta fase eu implemento schema de dados do CMS com Prisma em PostgreSQL, incluindo estrategia multi-tenant e migracoes controladas.

## O que eu vou alterar
- Criar `schema.prisma` com entidades centrais:
  - `Tenant`
  - `User`
  - `Role`
  - `Permission`
  - `Content`
  - `ContentVersion`
  - `MediaAsset`
  - `WebhookSubscription`
  - `AuditLog`
- Definir indices compostos por `tenant_id`.
- Configurar Prisma Client e `PrismaService` no NestJS.
- Estabelecer fluxo de migracao (`prisma migrate`).

## Decisoes tecnicas tomadas
- Eu vou usar `uuid` como chave primaria para distribuicao segura.
- Eu vou manter soft delete em entidades de negocio criticas.
- Eu vou explicitar constraints de unicidade por tenant.

## Criterios de aceite
- Migracoes aplicando sem drift em ambiente limpo.
- Queries principais com plano de execucao aceitavel.
- Regras de tenant isolation validadas por teste.

## Impacto no sistema
A aplicacao ganha persistencia consistente e pronta para escalar dominios.

## Limitacoes atuais
Camada de autenticacao e autorizacao ainda nao aplicada ponta a ponta.

## Proximos passos
Eu implemento auth, RBAC e isolamento de tenant na Fase 04.
