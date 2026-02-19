# Fase 05 - Estado e Estratégia de Storage

## Objetivo
Evoluir persistência para suportar escala horizontal com consistência operacional.

## Entregáveis
- Separação entre estado quente (runtime) e histórico.
- Estratégia para metadados/eventos em backend escalável.
- Política para retenção e compactação de dados por tenant.

## Observação
SQLite local pode continuar como cache/local journal, mas não como única fonte para fleet multi-node.
