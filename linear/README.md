# Backlog para Linear (gerado a partir de `docs/` + estado atual do projeto)

Este diretorio contem as issues prontas para abertura no Linear, 1:1 com as fases de roadmap ativas do projeto.

## Estrutura
- `issues/resilience/`
- `issues/resilience-advanced/`
- `issues/horizontal-scaling/`
- `issues/optimization-precision-speed/`
- `issues/adaptive-tuning-advanced/`
- `issues/cms-monorepo-nest-prisma/`

## Convencao de abertura no Linear
- Criar 1 epic por trilha.
- Abrir as issues em ordem de fase (`00 -> ...`), mantendo dependencia da fase anterior.
- Usar os campos de cada arquivo: prioridade sugerida, labels, criterios de aceite e riscos.

## Observacao importante
As fases historicas em `docs/phase-*.md` (raiz de `docs/`) representam trabalho ja executado no runtime headless atual e foram separadas em `linear/reference/implemented-phases.md` para evitar duplicidade de backlog.
