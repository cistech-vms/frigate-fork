# Fase 02 - Config Loader

## Objetivo da fase
Nesta fase eu implementei um loader de configuração com prioridade runtime/API > ENV > fallback.

## O que foi alterado
Eu criei `frigate/headless/runtime_config.py` com `RuntimeConfigStore` e suporte a overlay genérico por ambiente com prefixo `FRIGATE_CFG__...`.
Eu adicionei suporte opcional a `FRIGATE_CONFIG_JSON` para overlay completo.
Eu apliquei overlay de ENV no bootstrap (`frigate/__main__.py`) antes de iniciar o motor.

## Decisões técnicas tomadas
Eu usei merge profundo (`deep_merge`) para preservar compatibilidade com o schema atual.
Eu mantive validação com `FrigateConfig.model_validate` para reutilizar as regras já existentes.

## Impacto no sistema
A instância pode ser configurada sem arquivo YAML para chaves suportadas por overlay.
A configuração efetiva passa a ser observável pela API headless.

## Limitações atuais
Nem toda chave ainda possui estratégia de hot reload; parte das mudanças continua exigindo restart.

## Próximos passos
Expandir classificação de diffs por componente para granularidade fina de restart/hot-reload.
