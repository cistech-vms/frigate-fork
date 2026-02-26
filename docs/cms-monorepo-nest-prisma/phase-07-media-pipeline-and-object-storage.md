# Fase 07 - Pipeline de Midia e Object Storage

## Objetivo da fase
Nesta fase eu estruturo upload, processamento e entrega de midia com alta confiabilidade.

## O que eu vou alterar
- Integrar storage S3/R2 para assets.
- Implementar upload direto com URL assinada.
- Processar thumbnails/variantes via worker assicrono.
- Persistir metadados tecnicos (hash, mime, dimensoes, tamanho, status de processamento).
- Adicionar politica de ciclo de vida e exclusao segura de assets orfaos.

## Decisoes tecnicas tomadas
- Eu vou evitar upload binario pesado passando pelo backend quando possivel.
- Eu vou garantir idempotencia por hash do arquivo.
- Eu vou bloquear publicacao com asset em estado inconsistente.

## Criterios de aceite
- Upload e processamento funcionando com retry/backoff.
- Variantes geradas com rastreabilidade por job.
- Integridade de metadados validada por teste de contrato.

## Impacto no sistema
O CMS passa a operar com midia em escala sem sobrecarregar API principal.

## Limitacoes atuais
Integracao externa de conteudo e notificacao ainda limitada.

## Proximos passos
Eu defino contratos de API e webhooks na Fase 08.
