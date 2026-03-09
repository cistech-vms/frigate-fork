# Fase 05 - Estado Distribuído e Controle de Abuso

## Objetivo
Tornar comportamento consistente sob múltiplos nós e tráfego distribuído.

## O que executar
- Consolidar backend distribuído para coordenação de limite/estado crítico.
- Padronizar chave de limitação por tenant/principal/rota.
- Aplicar bloqueio progressivo com auditoria de abuso.

## Critérios de aceite
- Rate-limit previsível entre instâncias.
- Queda segura para fallback local sem bypass crítico.
- Métricas e auditoria de rejeição com motivo/retry-after.
