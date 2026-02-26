# Fase 00 - Visao do Produto e NFRs

## Objetivo da fase
Nesta fase eu defino escopo funcional do CMS, perfis de usuario e requisitos nao funcionais que guiam toda a arquitetura.

## O que eu vou alterar
- Formalizar dominios: conteudo, midia, taxonomia, publicacao e permissoes.
- Definir personas: autor, editor, revisor, admin e integrador.
- Estabelecer NFRs: disponibilidade, latencia, RPO/RTO, seguranca e auditoria.
- Definir metas de escala por tenant e por volume de conteudo.

## Decisoes tecnicas tomadas
- Eu vou tratar multi-tenant como requisito de base.
- Eu vou separar APIs sincrona e workloads assincronos desde o inicio.
- Eu vou adotar padrao fail-closed para autenticacao/autorizacao.

## Criterios de aceite
- Documento de escopo aprovado com prioridades (MVP, V1, V2).
- NFRs versionados com metas mensuraveis.
- Matriz de risco inicial publicada.

## Impacto no sistema
A plataforma passa a evoluir com direcao clara, reduzindo retrabalho de arquitetura.

## Limitacoes atuais
As decisoes de tecnologia ainda nao estao operacionalizadas no repositorio.

## Proximos passos
Eu inicio a fundacao do monorepo na Fase 01.
