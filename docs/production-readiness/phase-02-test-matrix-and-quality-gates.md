# Fase 02 - Matriz de Testes e Gates de Qualidade

## Objetivo
Bloquear promoção sem evidência mínima de qualidade e regressão.

## O que executar
- Definir matriz obrigatória: unit, integração, contrato, resiliência, carga mínima.
- Configurar gate de CI com thresholds de cobertura e sucesso.
- Separar testes bloqueantes de testes informativos.

## Critérios de aceite
- Pipeline de CI com status verde obrigatório para merge/release.
- Falha em teste bloqueante impede promoção.
- Relatório consolidado de evidências anexado por release.
