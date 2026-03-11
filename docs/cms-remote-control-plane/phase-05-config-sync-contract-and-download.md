# Fase 05 - Contrato de Sync e Download de Config

## Objetivo da fase
Definir contrato de configuracao remota e baixar apenas mudancas necessarias com versionamento.

## Contrato minimo esperado do CMS
- `config_version`
- `etag`
- `contract_version`
- `generated_at`
- `payload` (config efetiva)

## Entregaveis
- Cliente de fetch de configuracao com `If-None-Match`.
- Validacao de schema e contract version.
- Persistencia local do pacote recebido.

## Decisoes tecnicas
- Sem compatibilidade de contrato: rejeitar apply.
- Sem mudanca de `etag`: nao reaplicar.

## Criterios de aceite
- Download inicial funcional.
- `304 Not Modified` suportado.
- Erro de contrato/scheme gera evento de auditoria.

## Definicao de pronto para avancar
- Config remota versionada disponivel para apply seguro.
