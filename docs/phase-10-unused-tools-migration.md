# Fase 10 - Migração de Ferramentas Auxiliares Não Runtime

## Objetivo
Isolar scripts e artefatos de suporte que não participam do runtime headless de produção.

## Itens movidos para `nao_utilizado/tools/`
- `benchmark.py`
- `benchmark_motion.py`
- `process_clip.py`
- `generate_config_translations.py`
- `netlify.toml`
- `package-lock.json` (raiz)
- `notebooks/YOLO_NAS_Pretrained_Export.ipynb`

## Critério aplicado
Foram movidos apenas itens sem participação no caminho de execução do runtime headless (engine/API/worker pipeline).

## Validação
- Busca por referências dos itens movidos: sem ocorrências no código ativo.
- `python3 -m compileall frigate`: OK.

## Próximo passo
Revisar `nao_utilizado/` em lote final para remoção definitiva após janela de segurança.
