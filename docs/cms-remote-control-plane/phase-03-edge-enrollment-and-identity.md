# Fase 03 - Enrollment e Identidade de Edge

## Objetivo da fase
Registrar o edge no CMS e manter identidade estavel para rastreio, politica e governanca.

## Dados de enrollment
- `tenant_code`
- `node_id`
- versao do Frigate
- fingerprint do host/container
- capacidades (cpu/gpu, modulos ativos)

## Entregaveis
- Endpoint cliente de enrollment.
- Persistencia local de `edge_id` e metadata.
- Re-enrollment controlado quando fingerprint mudar.

## Decisoes tecnicas
- `edge_id` persistido localmente para estabilidade.
- Mudanca de identidade gera evento de auditoria e alerta.

## Criterios de aceite
- Primeiro boot gera enrollment.
- Boots seguintes reutilizam `edge_id` valido.
- Falha de enrollment bloqueia sync de config.

## Definicao de pronto para avancar
- Frigate identificado de forma univoca no CMS.
