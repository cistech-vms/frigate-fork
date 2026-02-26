# Fase 02 - Bootstrap do Backend NestJS

## Objetivo da fase
Nesta fase eu crio o backend principal do CMS em NestJS com base modular, validacao forte e padrao de erro consistente.

## O que eu vou alterar
- Inicializar `apps/api` com NestJS e TypeScript estrito.
- Configurar modulos base: `AppModule`, `HealthModule`, `ConfigModule`.
- Implementar validacao global com `class-validator` e `class-transformer`.
- Padronizar response/error envelope e filtros de excecao.
- Adicionar `Swagger/OpenAPI` para contrato inicial.

## Decisoes tecnicas tomadas
- Eu vou usar arquitetura modular por dominio e nao por camada generica.
- Eu vou centralizar middlewares e interceptors globais.
- Eu vou manter compatibilidade com execucao stateless na API.

## Criterios de aceite
- API sobe com endpoints de health/liveness/readiness.
- Validacao global e tratamento de erro unificado ativos.
- Documentacao OpenAPI gerada automaticamente.

## Impacto no sistema
A base HTTP fica pronta para evolucao dos modulos de negocio.

## Limitacoes atuais
Persistencia ainda nao conectada ao banco de dados.

## Proximos passos
Eu modelo dados com Prisma na Fase 03.
