# Fase 01 - Paridade de Ambiente e Dependências

## Objetivo
Garantir que dev/staging/prod tenham comportamento previsível e reproduzível.

## O que executar
- Congelar versões de runtime e libs críticas.
- Definir imagem base imutável e matriz de plataformas suportadas.
- Validar presença de dependências nativas (ex.: OpenCV, numpy, peewee, fastapi).

## Critérios de aceite
- Build reproduzível com lockfile e imagem versionada.
- Suite completa executável em staging sem falha por dependência ausente.
- Divergência de ambiente documentada e tratada.
