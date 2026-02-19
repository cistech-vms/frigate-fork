# Fase 01 - Auth Fail-Closed e Hardening de RBAC

## Objetivo da fase
Nesta fase eu elimino comportamentos permissivos em autenticação, imponho política fail-closed e fortaleço o RBAC para impedir acesso indevido em qualquer cenário de misconfig.

## O que eu vou alterar
- Remover fallback administrativo anônimo.
- Aceitar apenas `auth_mode` explicitamente válido (`hmac` ou `jwt`).
- Negar requisições quando segredo/chave obrigatória estiver ausente.
- Validar `tenant_id` de forma estrita em todas as rotas mutáveis.
- Tornar CORS desabilitado por padrão e explícito por allowlist.

## Decisões técnicas tomadas
- Eu vou usar negação por padrão em toda condição ambígua.
- Eu vou padronizar resposta de erro segura sem vazar detalhes sensíveis.
- Eu vou manter RBAC mínimo (`reader`, `admin`) com enforcement centralizado.

## Impacto no sistema
O runtime passa a operar com superfície de ataque menor, reduzindo risco de exposição acidental por variável de ambiente inválida.

## Limitações atuais
Ainda falta limitar abuso de forma distribuída e persistir trilhas de auditoria de autenticação.

## Próximos passos
Eu avanço para persistência de estado operacional na Fase 02.
