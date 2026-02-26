# Fase 05 - Dominio de Conteudo e Fluxo Editorial

## Objetivo da fase
Nesta fase eu implemento os modulos centrais do CMS para criacao, revisao e organizacao de conteudo.

## O que eu vou alterar
- Criar modulos de dominio:
  - `ContentModule`
  - `CategoryModule`
  - `TagModule`
  - `AuthorModule`
- Implementar estados editoriais: `draft`, `in_review`, `approved`, `published`, `archived`.
- Adicionar validacoes de consistencia editorial (slug unico por tenant, campos obrigatorios por tipo).
- Implementar historico de mudancas com autor e timestamp.

## Decisoes tecnicas tomadas
- Eu vou separar estado editorial de estado de publicacao.
- Eu vou usar servicos de dominio para regras e repositorios para persistencia.
- Eu vou manter schema extensivel para novos tipos de conteudo.

## Criterios de aceite
- CRUD completo com regras de permissao por papel.
- Transicoes de estado validadas por maquina de estado.
- Auditoria de alteracoes gravada automaticamente.

## Impacto no sistema
O backend passa a suportar o ciclo editorial principal do CMS.

## Limitacoes atuais
Publicacao programada e versionamento ainda nao completos.

## Proximos passos
Eu implemento versionamento, publish e agendamento na Fase 06.
