# Fase 04 - Validacao de Licenca e Politica Operacional

## Objetivo da fase
Validar licenca do tenant/edge antes de liberar operacao remota e definir politica de degradacao.

## Politica alvo
- Licenca valida: operacao normal.
- Licenca invalida/expirada: bloquear operacoes criticas remotas.
- CMS indisponivel: usar grace period + ultima licenca valida conhecida.

## Entregaveis
- Cliente de validacao de licenca.
- Estado local de licenca (`valid`, `grace`, `invalid`).
- Integracao com readiness/release gate.

## Decisoes tecnicas
- `fail-closed` apos grace period.
- Guardar timestamp da ultima validacao valida.

## Criterios de aceite
- Licenca valida libera fluxo.
- Licenca expirada muda runtime para modo restrito.
- `GET /v1/cms/status` exibe estado de licenca e expiracao.

## Definicao de pronto para avancar
- Gate de licenca controlando fluxo de config remota.
