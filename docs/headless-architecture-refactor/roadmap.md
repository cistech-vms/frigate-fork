# Roadmap de Refatoracao Arquitetural

## Objetivo macro
Transformar o Frigate Headless em um edge runtime declarativo, resiliente e leve, preservando o contrato atual consumido por `cms-app` e dashboard e protegendo o caminho critico do video contra qualquer sobrecarga do control plane.

## Principios de arquitetura
- SOLID para reduzir acoplamento e facilitar substituicao de componentes.
- Clean Architecture para separar dominio, adaptadores e detalhes de infraestrutura.
- Contratos estaveis para preservar `cms-app` e dashboard.
- Video Plane isolado do Control Plane.
- Persistencia explicita de intencao (`Desired State`) e saude (`Operational State`).
- Recovery seguro mesmo em modo degradado.

## Padroes orientadores
- Repository para persistencia desacoplada.
- Adapter para compatibilidade com `headless_state.json`, HMAC, CMS e endpoints atuais.
- Strategy para probing de camera, politica RTSP e heuristicas de descoberta.
- State Machine para lifecycle por camera.
- Observer/Pub-Sub para eventos internos de apply, health, rollback e drift.
- Builder/Compiler para transformar `Desired State` em config pronta para o engine.
- Anti-Corruption Layer para blindar `cms-app` e dashboard contra refactors internos.

## Fase 00 - Contrato estavel e fundacao de estado
### Objetivo
Introduzir `Desired State` e `Operational State` como contratos internos sem quebrar o fluxo atual.
### Modulos principais
- `frigate/headless/control_plane_state.py`
- `frigate/headless/state_repository.py`
- `frigate/headless/state_persistence.py`
- integracoes pontuais em `frigate/api/headless.py`
### Impacto externo
Nenhum.
### Criterio de aceite
- endpoints atuais seguem intactos
- `headless_state.json` passa a persistir os novos estados em paralelo ao overlay atual

## Fase 01 - Compiled Engine Config
### Objetivo
Criar uma fronteira explicita entre intencao declarativa e config executavel do engine.
### Modulos previstos
- `frigate/headless/config_compiler.py`
- `frigate/headless/compiled_patch.py`
- `frigate/config/config.py` apenas como destino de compilacao
### Padroes
- Builder
- Compiler
- Strategy para defaults e compatibilidade por camera
### Impacto externo
Nenhum; `cms-app` continua enviando o contrato atual.
### Criterio de aceite
- `Desired State` vira a fonte primaria de intencao
- o engine deixa de depender de roundtrip global de `FrigateConfig`

## Fase 02 - Politica de writes e readiness resiliente
### Objetivo
Separar mutacoes seguras de recovery de mutacoes estruturais pesadas.
### Classes de operacao
- `safe_recovery_write`
- `runtime_config_write`
- `topology_write`
### Padroes
- Command
- Policy Object
- Guard/Specification
### Impacto externo
Sem mudanca obrigatoria de contrato.
### Criterio de aceite
- correcoes operacionais simples continuam permitidas mesmo em `not_ready`
- write gate deixa de bloquear recuperacao basica de cameras

## Fase 03 - State machine por camera
### Objetivo
Dar visibilidade e determinismo ao ciclo de vida de cada camera.
### Estados iniciais sugeridos
- `discovered`
- `validated`
- `staged`
- `applied`
- `healthy`
- `degraded`
- `failed_auth`
- `failed_transport`
### Padroes
- State Machine
- Observer
### Impacto externo
Opcionalmente novos campos de status, mas sem quebrar os existentes.
### Criterio de aceite
- falhas RTSP, auth e transport ficam classificadas por camera
- readiness passa a refletir estado operacional mais rico

## Fase 04 - Installer deterministico
### Objetivo
Quebrar o installer em pipeline previsivel e reexecutavel.
### Pipeline alvo
- `scan`
- `probe`
- `select`
- `stage`
- `apply`
### Padroes
- Pipeline
- Strategy
- Adapter
### Impacto externo
Manter endpoints atuais; evoluir payloads de forma aditiva.
### Criterio de aceite
- `connect` deixa de inferir demais e passa a aplicar manifests ja validados
- fluxo tenant-aware fica nativo na CLI e na API

## Fase 05 - Isolamento do Video Plane e hardening
### Objetivo
Reduzir risco de atraso de video, jitter e contenção com o control plane.
### Focos
- observabilidade por camera
- filas e retries fora do hot path
- backpressure explicito
- limites de custo do CMS sync e governanca
### Padroes
- Pub/Sub interno
- Circuit Breaker
- Backoff
- Bulkhead
### Impacto externo
Nenhum obrigatorio.
### Criterio de aceite
- caminho de video permanece fluido sob carga administrativa
- control plane degradado nao derruba o processamento principal

## Regra para `cms-app` e dashboard
Enquanto as fases 00 a 03 estiverem em andamento, qualquer alteracao de contrato deve ser evitada. Se uma mudanca se tornar necessaria, o edge deve oferecer compatibilidade retroativa antes da migracao do cliente.
