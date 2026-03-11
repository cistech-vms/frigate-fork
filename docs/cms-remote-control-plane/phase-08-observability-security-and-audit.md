# Fase 08 - Observabilidade, Seguranca e Auditoria

## Objetivo da fase
Dar visibilidade operacional completa e reforcar seguranca do canal de controle remoto.

## Observabilidade
- Metricas:
  - latencia de chamadas CMS
  - taxa de sucesso de auth/sync
  - idade da ultima config aplicada
  - estado da licenca
- Logs estruturados com `tenant_id`, `edge_id`, `request_id`.

## Seguranca
- TLS obrigatorio para CMS remoto.
- Sanitizacao de logs (sem token/senha).
- Rotacao de segredos e revogacao.

## Auditoria
- Trilha de eventos: auth, enrollment, license check, config apply, rollback.
- Export de auditoria para investigacao.

## Entregaveis
- Endpoint `GET /v1/cms/status`.
- Endpoint `POST /v1/cms/sync` (admin).
- Eventos de auditoria persistidos no estado local.

## Criterios de aceite
- Diagnostico completo por API e metricas.
- Nenhum segredo exposto em logs.
- Auditoria suficiente para RCA de incidente.

## Definicao de pronto para avancar
- Operacao e seguranca aptas para homologacao avancada.
