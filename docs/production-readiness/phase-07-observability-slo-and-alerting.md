# Fase 07 - Observabilidade, SLO e Alertas

## Objetivo
Detectar degradação antes de ruptura e permitir resposta rápida.

## O que executar
- Padronizar logs estruturados com correlação (`request_id`, `tenant_id`).
- Publicar métricas de latência, erro, backlog, drops e throughput.
- Definir SLOs por perfil e alertas acionáveis.

## Critérios de aceite
- Dashboard operacional com indicadores críticos.
- Alertas testados (simulação de incidente) com rota de escalonamento.
- Gate de release conectado ao estado de SLO.
