# Fase 00 - Estado Atual e Gargalos

## Objetivo
Registrar onde estão as limitações de escala horizontal no estado atual do projeto.

## Achados principais

### 1) Orquestrador central com fan-in/fan-out único
- `frigate/app.py` centraliza inicialização e coordenação de todos os componentes.
- Todos os fluxos passam por um único runtime da instância.

Impacto: cresce complexidade e contenção conforme aumenta o número de câmeras.

### 2) Fila de detecção compartilhada para todas as câmeras
- `self.detection_queue = mp.Queue()` em `frigate/app.py`.
- Câmeras compartilham a mesma fila de entrada para detectores.

Impacto: head-of-line blocking entre câmeras e imprevisibilidade de latência.

### 3) Banco SQLite local único por instância
- `SqliteExtDatabase`/`SqliteVecQueueDatabase` em `frigate/app.py` e `frigate/db/sqlitevecq.py`.
- Convergência de eventos, gravações, review e embeddings em arquivo local.

Impacto: escala vertical limitada; concorrência e lock contention sob carga alta.

### 4) API single-process no data-plane
- `uvicorn.run(... host="127.0.0.1", port=5001)` em `frigate/app.py`.

Impacto: API não escala internamente por workers, dependente de scale-out externo.

### 5) IPC local por ZMQ/IPC sockets
- `InterProcessCommunicator` e `ConfigPublisher/Subscriber` em `frigate/comms/*` usam `ipc:///tmp/cache/...`.

Impacto: ótimo intra-host, mas não resolve coordenação entre múltiplos nós.

### 6) Hot reload parcial
- Runtime headless atual aplica reload parcial (ex.: zonas/regiões) e marca restart para outras classes de mudança.

Impacto: mudanças de capacidade e pipeline pesado ainda exigem ciclo de restart por nó.

## Consequência prática (câmeras)
- A capacidade total por instância é limitada por CPU/GPU + I/O + fila compartilhada + SQLite.
- Escalar número de câmeras hoje significa aumentar recursos da instância ou replicar instâncias de forma manual.

## Resultado esperado da próxima fase
Definir arquitetura-alvo para transformar esse runtime em pool de workers/shards controlados por plano de alocação.
