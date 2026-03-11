# Fase 01 - Bootstrap e Entradas Obrigatorias

## Objetivo da fase
Garantir que o runtime suba em modo headless com parametros obrigatorios para conectar no CMS remoto.

## Parametros obrigatorios
- `FRIGATE_CMS_URL`
- `FRIGATE_TENANT_CODE`
- `FRIGATE_CMS_AUTH_MODE=token|password`
- `FRIGATE_CMS_TOKEN` ou (`FRIGATE_CMS_USERNAME` + `FRIGATE_CMS_PASSWORD`)

## Parametros recomendados
- `FRIGATE_NODE_ID`
- `FRIGATE_CMS_SYNC_INTERVAL_SEC`
- `FRIGATE_CMS_REQUEST_TIMEOUT_SEC`
- `FRIGATE_CMS_LICENSE_GRACE_SEC`

## Entregaveis
- Loader de settings para CMS remoto.
- Validacao de bootstrap no startup com erro explicito.
- Estados operacionais iniciais: `booting`, `config_required`, `auth_pending`.

## Decisoes tecnicas
- Sem parametros obrigatorios: nao habilitar plano remoto.
- Mensagens claras em log e endpoint de status para diagnostico rapido.

## Criterios de aceite
- Startup valida combinacoes invalidas e interrompe fluxo remoto.
- `GET /healthz` segue disponivel.
- `GET /readyz` mostra `not_ready` com motivo objetivo quando faltarem entradas.

## Definicao de pronto para avancar
- Ambiente consegue iniciar de forma deterministica com/sem parametros.
