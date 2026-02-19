# Fase 06 - Chaos Engineering, Recuperação e Self-Healing

## Objetivo da fase
Nesta fase eu provo resiliência na prática, simulando falhas controladas e validando capacidade de recuperação automática sem intervenção manual constante.

## O que eu vou alterar
- Introduzir testes de falha de rede, timeout e reinício de processo.
- Validar recuperação de filas, estado e publicadores após crash.
- Definir políticas de restart e cooldown para evitar crash-loop.
- Criar runbooks operacionais para incidentes recorrentes.

## Decisões técnicas tomadas
- Eu vou focar em cenários de falha mais prováveis no edge.
- Eu vou medir MTTR e taxa de recuperação como critérios de aceite.
- Eu vou registrar evidência reproduzível por cenário de caos.

## Impacto no sistema
A resiliência deixa de ser teórica e passa a ser validada por experimento, com confiança maior para ambientes reais.

## Limitações atuais
Sem observabilidade madura, a detecção precoce de degradação ainda fica limitada.

## Próximos passos
Eu consolido métricas, alertas e SLO na Fase 07.
