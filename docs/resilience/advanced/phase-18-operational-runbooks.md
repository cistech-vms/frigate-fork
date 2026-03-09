# Fase 18 - Runbooks Operacionais

## Objetivo da fase
Nesta fase eu transformo resposta a incidente em procedimento repetível, reduzindo tempo de diagnóstico e correção.

## O que eu vou alterar
- Criar runbooks para falhas comuns: storage offline, fila acumulada, nó degradado.
- Definir checklist de triagem por severidade.
- Formalizar comandos e validações de recuperação.
- Incluir critérios claros de escalonamento.

## Decisões técnicas tomadas
- Eu vou escrever runbooks acionáveis e curtos.
- Eu vou vincular cada runbook a métricas e alertas.
- Eu vou revisar runbooks após cada incidente relevante.

## Impacto no sistema
A operação ganha resposta mais rápida e consistente, reduzindo MTTR em ambiente real.

## Limitações atuais
Runbook sem treino operacional periódico perde efetividade ao longo do tempo.

## Próximos passos
Eu avanço para plano de disaster recovery.

## Implementação aplicada
- Runbooks operacionais estruturados para `storage_offline`, `queue_accumulation` e `degraded_node`.
- Checklist de triagem, recuperação e critério de escalonamento por cenário.
- Exposição via endpoint para integração com automação e NOC.

## Evidência de operação
- `GET /v1/resilience/runbooks`
