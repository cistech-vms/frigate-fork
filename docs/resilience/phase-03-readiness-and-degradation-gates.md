# Fase 03 - Readiness Real e Portões de Degradação

## Objetivo da fase
Nesta fase eu transformo `/readyz` em um indicador real de capacidade operacional, não apenas sinal superficial de processo ativo.

## O que eu vou alterar
- Verificar estado de DB local, processos críticos e filas internas.
- Incluir sinal de saúde do pipeline de detecção e publicadores.
- Expor motivos objetivos de `not ready` para operação.
- Definir modos de degradação (aceitar leitura, bloquear escrita crítica, etc.).

## Decisões técnicas tomadas
- Eu vou separar claramente liveness de readiness.
- Eu vou usar thresholds de backlog/latência para decisão de readiness.
- Eu vou manter resposta estruturada para automação de orquestrador.

## Impacto no sistema
A plataforma evita rotear carga para nós incapazes de cumprir SLA mínimo, reduzindo cascata de falhas.

## Limitações atuais
Ainda falta garantir entrega confiável de eventos externos sob falha intermitente de rede.

## Próximos passos
Eu avanço para confiabilidade de eventos na Fase 04.
