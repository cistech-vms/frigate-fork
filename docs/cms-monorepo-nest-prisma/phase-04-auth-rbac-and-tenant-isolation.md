# Fase 04 - Auth, RBAC e Isolamento Multi-Tenant

## Objetivo da fase
Nesta fase eu implemento seguranca de acesso para garantir que cada tenant e usuario so acesse o que lhe pertence.

## O que eu vou alterar
- Adicionar autenticacao JWT com refresh token rotativo.
- Implementar guardas NestJS para RBAC por permissao.
- Aplicar `tenant_id` obrigatorio em contexto de requisicao.
- Bloquear acesso cruzado entre tenants em repositorios/servicos.
- Introduzir trilha de login, falha e revogacao.

## Decisoes tecnicas tomadas
- Eu vou negar por padrao qualquer requisicao ambigua.
- Eu vou separar credenciais de usuario e credenciais de integracao.
- Eu vou expor escopos minimos para tokens de API.

## Criterios de aceite
- Testes cobrindo bypass de RBAC e tenant break-out.
- Rotacao/revogacao de token funcionando sem downtime.
- Logs de seguranca com correlacao por `request_id`.

## Impacto no sistema
A superficie de ataque reduz e a governanca por tenant fica confiavel.

## Limitacoes atuais
Fluxo editorial de conteudo ainda nao modelado no backend.

## Proximos passos
Eu implemento dominio de conteudo e workflow editorial na Fase 05.
