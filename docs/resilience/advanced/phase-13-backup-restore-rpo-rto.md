# Fase 13 - Backup e Restore com RPO/RTO

## Objetivo da fase
Nesta fase eu estruturo a estratégia de backup e restore para garantir continuidade operacional com metas claras de RPO e RTO.

## O que eu vou alterar
- Definir política de backup por tipo de dado (estado runtime, metadados, mídia).
- Documentar janelas de backup incremental e completo.
- Formalizar RPO/RTO por perfil de cliente.
- Validar restore em ambiente de teste com evidência.

## Decisões técnicas tomadas
- Eu vou separar backup de metadado transacional e backup de artefatos de mídia.
- Eu vou tratar backup como processo testável, não apenas configuração.
- Eu vou versionar plano de restore por release.

## Impacto no sistema
Com restore validado, a operação reduz risco de perda permanente após falhas de nó ou corrupção local.

## Limitações atuais
Sem automação completa de restore, parte da recuperação ainda depende de execução operacional manual.

## Próximos passos
Eu avanço para gestão de segredos e rotação de chaves.

## Implementação aplicada
- Manager de backup/restore com manifesto versionado e metadados de RPO/RTO.
- Endpoints para criar, listar e restaurar backup do estado operacional.
- Restore orientado por escopo (runtime/rate-limit) para recuperação controlada.

## Evidência de operação
- `POST /v1/resilience/backup/create`
- `GET /v1/resilience/backup/list`
- `POST /v1/resilience/backup/restore`
