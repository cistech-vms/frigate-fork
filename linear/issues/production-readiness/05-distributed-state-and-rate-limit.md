# Fase 05 - Estado Distribuido e Controle de Abuso

## Metadados para Linear
- Trilha/Epic sugerido: Production Readiness
- Prioridade sugerida: P0
- Labels sugeridas: production-readiness,distributed-state,rate-limit,phase-05
- Dependencia: Fase 04
- Documento de origem: docs/production-readiness/phase-05-distributed-state-and-rate-limit.md

## Objetivo
Garantir comportamento consistente entre multiplos nos e controle de abuso sem bypass.

## Escopo da issue
- Backend distribuido para estado critico e rate limit.
- Chave padrao por tenant/principal/rota.
- Bloqueio progressivo com telemetria e auditoria.

## Etapas detalhadas
1. Arquitetura de estado
- [ ] Definir armazenamento distribuido para estado de limite.
- [ ] Implementar estrategia de fallback local controlado.
- [ ] Evitar divergir contador entre instancias.

2. Politica de limitacao
- [ ] Padronizar chave e janela de limitacao.
- [ ] Implementar resposta com `retry-after` consistente.
- [ ] Versionar regras por endpoint critico.

3. Observabilidade
- [ ] Expor metricas de throttle e rejeicao por motivo.
- [ ] Publicar auditoria de abuso por tenant/principal.
- [ ] Definir alertas para falso positivo/falso negativo.

## Criterios de aceite
- Rate-limit previsivel entre instancias.
- Fallback local sem bypass critico.
- Auditoria e metricas com motivo/retry-after.

## Riscos e pontos de atencao
- Inconsistencia de contador entre nos quebra previsibilidade.
- Politica agressiva pode gerar indisponibilidade para cliente legitimo.
