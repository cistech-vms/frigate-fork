# Fase 09 - Camada de Adapter para Banco de Dados

## Objetivo da fase
Nesta fase eu modularizo a persistência com padrão Adapter para suportar `sqlite`, `mysql` e `postgresql` sem espalhar condicionais de banco no core.

## O que eu vou alterar
- Definir contrato único de persistência (`DatabaseAdapter`) para operações de runtime.
- Criar adapters concretos:
  - `SqliteAdapter`
  - `MySQLAdapter`
  - `PostgresAdapter`
- Introduzir fábrica de adapters por ENV (`FRIGATE_DB_DRIVER`).
- Isolar migrações e diferenças de SQL por backend.
- Manter compatibilidade com o modo edge local padrão (`sqlite`).

## Decisões técnicas tomadas
- Eu vou manter o core de detecção/track agnóstico de banco.
- Eu vou encapsular transações, retries e mapeamento de erro no adapter.
- Eu vou padronizar schema lógico único e mapear dialetos na borda de infraestrutura.

## Impacto no sistema
A aplicação passa a trocar banco sem reescrever regras de negócio, reduzindo acoplamento e facilitando evolução para cenários distribuídos.

## Limitações atuais
Mesmo com adapter, cada banco possui diferenças de tuning, isolamento e lock que exigem perfil operacional próprio.

## Próximos passos
Na sequência eu adiciono a camada Redis para reduzir fricção em cache, coordenação e throughput.
