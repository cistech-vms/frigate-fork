# Fase 06 - Versionamento, Publicacao e Agendamento

## Objetivo da fase
Nesta fase eu torno a publicacao rastreavel e previsivel com versionamento de conteudo e jobs agendados.

## O que eu vou alterar
- Persistir `ContentVersion` imutavel por revisao.
- Implementar publicacao imediata e agendada.
- Adicionar mecanismo de rollback para versao anterior.
- Criar worker para processar agenda de publicacao/despublicacao.
- Expor endpoint de preview seguro por token temporario.

## Decisoes tecnicas tomadas
- Eu vou tratar versao publicada como snapshot imutavel.
- Eu vou usar fila para tarefas de publish em lote.
- Eu vou separar horario editorial de horario efetivo de indexacao.

## Criterios de aceite
- Rollback funcional sem perda de historico.
- Agendamento executado com idempotencia.
- Preview acessivel apenas com escopo/autorizacao valida.

## Impacto no sistema
O CMS ganha controle fino de release de conteudo e reversao segura.

## Limitacoes atuais
Pipeline de midia ainda nao escalavel para alto volume.

## Proximos passos
Eu implemento pipeline de midia e object storage na Fase 07.
