# Fase 05 - Security Layer

## Objetivo da fase
Nesta fase eu adicionei autenticação, autorização e proteção básica contra abuso para a API headless.

## O que foi alterado
Eu criei `frigate/headless/security.py` com:
- autenticação HMAC por requisição (`X-Key-Id`, `X-Timestamp`, `X-Signature`)
- alternativa JWT HS256
- RBAC mínimo (`admin`, `reader`)
- validação de tenant
- rate limiting simples por chave/IP

Eu também adicionei suporte a `request_id` por middleware e preparei logs estruturados JSON por ENV.

## Decisões técnicas tomadas
Eu usei dependências do FastAPI por rota para reduzir risco de bypass.
Eu mantive CORS desabilitado por padrão e allowlist opcional por ambiente.

## Impacto no sistema
A API deixa de ter superfícies “admin abertas” no modo headless.

## Limitações atuais
O rate limiter atual é in-memory por processo e não distribuído.

## Próximos passos
Adicionar backend distribuído de rate limit e rotação de chaves com versionamento.
