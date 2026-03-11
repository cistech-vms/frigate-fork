# Fase 02 - Auth no CMS e Sessao

## Objetivo da fase
Implementar autenticacao no CMS em dois modos: token fixo e login por user/password.

## Fluxos
1. `token`
- Usa bearer configurado localmente.
- Verifica validade no endpoint de introspeccao (quando existir).

2. `password`
- Faz login no CMS.
- Recebe `access_token` e `refresh_token`.
- Renova token antes de expirar.

## Entregaveis
- Cliente HTTP para auth com timeout, retry e backoff.
- Armazenamento seguro de sessao (sem logar segredo).
- Tratamento de erros (401, 403, 429, 5xx).

## Decisoes tecnicas
- Nao mascarar falha de auth: estado explicito `auth_failed`.
- Limite de tentativas para evitar lockout e ruido operacional.

## Criterios de aceite
- Modo token funcional.
- Modo password funcional com refresh.
- Eventos de auditoria para login, refresh e falhas.

## Definicao de pronto para avancar
- Sessao autenticada disponivel para chamadas de enrollment/licenca/config.
