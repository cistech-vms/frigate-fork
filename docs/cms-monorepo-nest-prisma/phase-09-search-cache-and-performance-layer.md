# Fase 09 - Busca, Cache e Camada de Performance

## Objetivo da fase
Nesta fase eu otimizo leitura e descoberta de conteudo com cache, indices e estrategia de busca.

## O que eu vou alterar
- Implementar cache read-through com Redis para listagens frequentes.
- Definir invalidação por evento de alteracao/publicacao.
- Adicionar busca textual (Postgres FTS ou engine dedicada conforme volume).
- Otimizar queries Prisma com projection seletiva e paginação cursor-based.
- Incluir limites de taxa para endpoints de listagem pesada.

## Decisoes tecnicas tomadas
- Eu vou usar cache como aceleracao opcional, nao como fonte da verdade.
- Eu vou manter fallback seguro para leitura direta do banco.
- Eu vou monitorar hit ratio e latencia para guiar tuning.

## Criterios de aceite
- P95 de leitura dentro da meta definida por NFR.
- Hit ratio minima de cache em endpoints alvo.
- Nao regressao de consistencia em cenarios de invalidacao.

## Impacto no sistema
A API passa a suportar maior volume de leitura com menor custo.

## Limitacoes atuais
Governanca de observabilidade e compliance ainda incompletas.

## Proximos passos
Eu evoluo observabilidade, auditoria e compliance na Fase 10.
