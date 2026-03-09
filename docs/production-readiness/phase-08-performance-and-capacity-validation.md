# Fase 08 - Validação de Performance e Capacidade

## Objetivo
Comprovar capacidade real por perfil de carga antes de produção.

## O que executar
- Rodar benchmark progressivo por faixas de câmeras/nó.
- Medir p95/p99 de inferência e entrega de evento.
- Validar saturação de CPU/GPU/filas e limites operacionais.

## Critérios de aceite
- SLOs atingidos na capacidade-alvo.
- Sem crescimento infinito de fila sob carga sustentada.
- Plano de escala horizontal calibrado por evidência.
