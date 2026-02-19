# Fase 10 - Camada Redis para Reduzir Fricção Operacional

## Objetivo da fase
Nesta fase eu adiciono Redis como camada complementar para reduzir atrito geral de performance e coordenação entre componentes.

## O que eu vou alterar
- Implementar `RedisAdapter` opcional ativado por ENV (`FRIGATE_REDIS_ENABLED=true`).
- Usar Redis para:
  - cache de leitura frequente (config efetiva, status agregado, lookup de triggers)
  - rate limit distribuído por tenant/principal
  - locks leves de coordenação entre workers
  - fila curta para eventos transitórios não críticos
- Definir política de TTL e invalidação para evitar dados obsoletos.
- Prever fallback seguro para modo sem Redis (edge standalone).

## Decisões técnicas tomadas
- Eu vou tratar Redis como aceleração opcional, não dependência obrigatória do core.
- Eu vou manter consistência por estratégia cache-aside e invalidação dirigida por evento.
- Eu vou limitar uso de Redis a casos de alto ganho operacional para não aumentar complexidade sem retorno.

## Impacto no sistema
A camada Redis reduz carga do banco primário, melhora latência de APIs críticas e melhora coordenação em ambientes com múltiplos nós.

## Limitações atuais
Redis não substitui persistência definitiva; ele complementa o banco transacional e exige política clara de alta disponibilidade.

## Próximos passos
Após esta fase, eu consolido benchmark de ganho real por cenário (single-node, multi-node e pico de eventos).
