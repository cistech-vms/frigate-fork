# Fase 07 - Observabilidade, SLO e Guardrails de Capacidade

## Objetivo da fase
Nesta fase eu fecho o ciclo de confiabilidade operacional com telemetria orientada a decisão, limites de capacidade por nó e metas de serviço.

## O que eu vou alterar
- Padronizar logs JSON com `request_id`, `tenant_id` e correlação.
- Publicar métricas de latência, erro, backlog, drops e throughput.
- Definir SLOs de API e pipeline de eventos por perfil de cliente.
- Configurar alertas por saturação de CPU/GPU, fila e perda de evento.

## Decisões técnicas tomadas
- Eu vou manter métricas de baixo custo para edge-first.
- Eu vou separar indicadores de saúde técnica e saúde de negócio.
- Eu vou ligar capacidade de câmeras por nó a thresholds observáveis.

## Impacto no sistema
A operação passa a prever degradação antes da ruptura, permitindo ação proativa e escalonamento controlado.

## Limitações atuais
Ainda preciso consolidar gate final de release com matriz de testes obrigatórios.

## Próximos passos
Eu implemento critérios formais de promoção em ambiente na Fase 08.
