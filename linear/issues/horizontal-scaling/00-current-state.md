# Fase 00 - Estado Atual e Gargalos

## Metadados para Linear
- Trilha/Epic sugerido: Horizontal Scaling
- Prioridade sugerida: P1
- Labels sugeridas: scaling,sharding,runtime,phase-00
- Dependencia: Sem dependencia
- Documento de origem: docs/horizontal-scaling/phase-00-current-state.md

## Contexto do projeto atual
- Orquestracao centralizada no processo principal em `frigate/app.py`.
- Filas e IPC locais em `frigate/comms/*` e multiprocessing.
- API local e estado por instancia, sem coordenacao multi-no nativa.

## Objetivo
Registrar onde estão as limitações de escala horizontal no estado atual do projeto.

## Escopo da issue
- 1) Orquestrador central com fan-in/fan-out único
- `frigate/app.py` centraliza inicialização e coordenação de todos os componentes.
- Todos os fluxos passam por um único runtime da instância.
- 2) Fila de detecção compartilhada para todas as câmeras
- `self.detection_queue = mp.Queue()` em `frigate/app.py`.
- Câmeras compartilham a mesma fila de entrada para detectores.
- 3) Banco SQLite local único por instância
- `SqliteExtDatabase`/`SqliteVecQueueDatabase` em `frigate/app.py` e `frigate/db/sqlitevecq.py`.
- Convergência de eventos, gravações, review e embeddings em arquivo local.
- 4) API single-process no data-plane
- `uvicorn.run(... host="127.0.0.1", port=5001)` em `frigate/app.py`.
- 5) IPC local por ZMQ/IPC sockets
- `InterProcessCommunicator` e `ConfigPublisher/Subscriber` em `frigate/comms/*` usam `ipc:///tmp/cache/...`.
- 6) Hot reload parcial
- Runtime headless atual aplica reload parcial (ex.: zonas/regiões) e marca restart para outras classes de mudança.

## Etapas detalhadas
1. Preparacao tecnica
- [ ] Revisar impacto desta fase no codigo existente e nas configuracoes por tenant/camera.
- [ ] Definir contrato de entrada/saida e estrategia de rollout incremental.
- [ ] Registrar riscos tecnicos e plano de mitigacao.

2. Implementacao principal
- [ ] 1) Orquestrador central com fan-in/fan-out único
- [ ] `frigate/app.py` centraliza inicialização e coordenação de todos os componentes.
- [ ] Todos os fluxos passam por um único runtime da instância.
- [ ] 2) Fila de detecção compartilhada para todas as câmeras
- [ ] `self.detection_queue = mp.Queue()` em `frigate/app.py`.
- [ ] Câmeras compartilham a mesma fila de entrada para detectores.
- [ ] 3) Banco SQLite local único por instância
- [ ] `SqliteExtDatabase`/`SqliteVecQueueDatabase` em `frigate/app.py` e `frigate/db/sqlitevecq.py`.
- [ ] Convergência de eventos, gravações, review e embeddings em arquivo local.
- [ ] 4) API single-process no data-plane
- [ ] `uvicorn.run(... host="127.0.0.1", port=5001)` em `frigate/app.py`.
- [ ] 5) IPC local por ZMQ/IPC sockets
- [ ] `InterProcessCommunicator` e `ConfigPublisher/Subscriber` em `frigate/comms/*` usam `ipc:///tmp/cache/...`.
- [ ] 6) Hot reload parcial
- [ ] Runtime headless atual aplica reload parcial (ex.: zonas/regiões) e marca restart para outras classes de mudança.

3. Integracao com runtime e API
- [ ] Garantir compatibilidade com endpoints headless e fluxo de configuracao efetiva.
- [ ] Validar comportamento em cenarios de erro, retry e degradacao.
- [ ] Garantir isolamento por tenant quando aplicavel.

4. Observabilidade e seguranca
- [ ] Expor metricas e logs estruturados para os novos fluxos.
- [ ] Adicionar trilha de auditoria para mudancas operacionais criticas.
- [ ] Revisar controles de auth/rbac/rate-limit relacionados.

5. Testes e validacao
- [ ] Adicionar/atualizar testes unitarios e de integracao para os caminhos alterados.
- [ ] Executar teste de carga/estabilidade proporcional ao risco da fase.
- [ ] Anexar evidencias de validacao para aprovacao.

6. Entrega e documentacao
- [ ] Atualizar documentacao tecnica e runbook operacional.
- [ ] Definir criterio de go/no-go e plano de rollback.
- [ ] Publicar changelog de comportamento e impactos esperados.

## Criterios de aceite
- Evidencias de teste e validacao anexadas
- Documentacao atualizada
- Sem regressao funcional nas rotas e no pipeline afetado

## Riscos e pontos de atencao
- Evitar regressao no pipeline principal de deteccao/tracking/eventos.
- Evitar breaking change de contrato sem versionamento e estrategia de migracao.
- Garantir que fallback e rollback estejam exercitados antes de promover rollout amplo.
