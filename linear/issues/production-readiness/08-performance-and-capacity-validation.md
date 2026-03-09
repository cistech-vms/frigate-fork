# Fase 08 - Validacao de Performance e Capacidade

## Metadados para Linear
- Trilha/Epic sugerido: Production Readiness
- Prioridade sugerida: P1
- Labels sugeridas: production-readiness,performance,capacity,phase-08
- Dependencia: Fase 07
- Documento de origem: docs/production-readiness/phase-08-performance-and-capacity-validation.md

## Objetivo
Comprovar capacidade real por perfil de carga antes do go-live amplo.

## Escopo da issue
- Benchmark progressivo por faixas de cameras por no.
- Medicao de p95/p99 de inferencia e entrega de evento.
- Definicao de limite operacional e plano de escala.

## Etapas detalhadas
1. Plano de carga
- [ ] Definir perfis de workload e volume alvo.
- [ ] Preparar cenarios de pico e carga sustentada.
- [ ] Definir metricas de sucesso por perfil.

2. Execucao de benchmark
- [ ] Rodar testes progressivos e coletar evidencias.
- [ ] Medir consumo de CPU/GPU/memoria/filas.
- [ ] Identificar ponto de saturacao por componente.

3. Calibracao de capacidade
- [ ] Publicar limites recomendados por no.
- [ ] Atualizar estrategia de escala horizontal.
- [ ] Revisar tuning com base no resultado.

## Criterios de aceite
- SLO atingido na capacidade alvo.
- Sem fila crescendo indefinidamente sob carga sustentada.
- Plano de escala calibrado por evidencia.

## Riscos e pontos de atencao
- Benchmark nao representativo gera falso positivo.
- Sem perfil de pico, incidentes aparecem so em producao.
