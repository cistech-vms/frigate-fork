# Fase 09 - Testes, Gates e Rollout

## Objetivo da fase
Fechar qualidade com matriz de testes e plano de rollout progressivo para teste em producao.

## Matriz de testes
- Unitarios:
  - settings bootstrap
  - auth client
  - license policy
  - config validator/apply policy
- Integracao:
  - login + enrollment + license + sync
  - retry/backoff
  - canary e rollback
- Resiliencia:
  - CMS fora do ar
  - token expirado
  - config invalida

## Gates de release
- `readyz` estavel e sem bloqueio indevido.
- `release-gate` aprovado.
- `production-readiness` sem pendencias criticas para o escopo.

## Rollout sugerido
1. laboratorio interno
2. tenant piloto (baixo risco)
3. coorte limitada
4. rollout amplo

## Entregaveis
- Checklist de go/no-go por ambiente.
- Evidencias de teste anexadas por fase.
- Plano de rollback operacional.

## Criterios de aceite
- Sem regressao funcional no core de deteccao/tracking/eventos.
- Tempo de recuperacao dentro do esperado.
- Equipe de operacao apta a executar rollback.

## Conclusao da trilha
Ao fim desta fase, o Frigate pode operar em modo headless conectado ao CMS remoto com governanca tecnica para teste em producao.
