# Fase 06 - Apply Seguro, Canary, Rollback e Last Known Good

## Objetivo da fase
Aplicar configuracao remota com seguranca operacional e capacidade de recuperar rapidamente.

## Estrategia
- Validar patch antes de aplicar.
- Aplicar por canary quando mudanca for de alto risco.
- Em degradacao, rollback automatico para estado anterior.
- Manter `last_known_good` persistido.

## Entregaveis
- Pipeline de apply remoto usando runtime config store.
- Politica de risco para decidir canary x apply direto.
- Registro de diff aplicado e resultado.

## Decisoes tecnicas
- Nao promover canary sem evidencias de health/slo.
- Rollback sempre idempotente.

## Criterios de aceite
- Config valida aplicada sem restart indevido.
- Config invalida nunca aplicada.
- Canary com rollback automatico em falha.
- `last_known_good` restauravel.

## Definicao de pronto para avancar
- Apply remoto seguro e auditavel em producao.
