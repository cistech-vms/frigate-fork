# Fase 11 - Integração de Object Storage (S3/R2)

## Objetivo da fase
Nesta fase eu adiciono integração nativa com object storage para armazenar clips, snapshots e artefatos de evento em `Amazon S3` ou `Cloudflare R2`, dirigida por configuração recebida via ENV e API.

## O que eu vou alterar
- Definir contrato `ObjectStorageAdapter` com operações padrão:
  - `put_object`
  - `get_object_url`
  - `delete_object`
  - `head_object`
- Implementar adapters:
  - `S3Adapter` (AWS S3)
  - `R2Adapter` (endpoint S3-compatible)
- Adicionar seleção por configuração efetiva:
  - `storage.provider` (`local`, `s3`, `r2`)
  - `storage.bucket`
  - `storage.region`
  - `storage.endpoint` (obrigatório para R2)
  - `storage.access_key`
  - `storage.secret_key`
  - `storage.prefix`
  - `storage.sse`
- Permitir atualização dinâmica por API para parâmetros suportados sem restart.
- Manter fallback para armazenamento local quando cloud storage estiver indisponível.

## Decisões técnicas tomadas
- Eu vou manter modelo híbrido edge-first: grava local primeiro e replica para nuvem de forma assíncrona.
- Eu vou evitar bloquear pipeline de detecção por latência de upload.
- Eu vou tratar credenciais por segredo injetado e nunca logar valor sensível.

## Impacto no sistema
Com S3/R2, o edge reduz risco de perda definitiva de evidência, facilita retenção centralizada e reduz pressão de disco local em operação contínua.

## Limitações atuais
Object storage não substitui estado transacional do runtime; ele cobre mídia e artefatos, não metadados operacionais críticos.

## Próximos passos
Na fase seguinte eu consolido regras de consistência, reenvio e reconciliação para mudanças de configuração em tempo real.

## Implementação aplicada
- Contrato `ObjectStorageAdapter` com `local`, `s3` e `r2` (S3-compatible).
- Fallback local automático quando cloud storage estiver indisponível.
- Arquivamento de dead-letter de eventos em pipeline assíncrono de replicação.

## Configuração principal
- `FRIGATE_STORAGE_PROVIDER`
- `FRIGATE_STORAGE_BUCKET`
- `FRIGATE_STORAGE_REGION`
- `FRIGATE_STORAGE_ENDPOINT`
- `FRIGATE_STORAGE_PREFIX`
