# Fase 00 - Contrato Estavel e Fundacao de Estado

## Objetivo
Criar a primeira camada da nova arquitetura sem quebrar o contrato consumido por `cms-app` e dashboard.

## Problema Atual
O projeto usa o mesmo funil para schema, runtime, persistencia e restore:
- `model_dump(...)`
- `deep_merge(...)`
- `model_validate(...)`

Isso aumenta o acoplamento entre:
- config do engine
- overlay runtime
- onboarding/installer
- restore no boot
- persistencia por tenant

## Decisao Arquitetural
Introduzir duas novas representacoes explicitas:
- `Desired State`: intencao declarativa por tenant e por camera
- `Operational State`: saude e situacao operacional por tenant e por camera

Esses estados passam a existir como contratos internos, sem alterar os endpoints atuais.

## Padroes Aplicados
- Repository: persistencia desacoplada do `HeadlessStateStore`
- Adapter: repositorio adaptador para o formato atual de `headless_state.json`
- Builder/Projection: projecao de runtime patches para `Desired State`

## Entregaveis desta fase
- novos modelos em `frigate/headless/control_plane_state.py`
- novo repositorio em `frigate/headless/state_repository.py`
- persistencia expandida em `frigate/headless/state_persistence.py`
- integracao nao-destrutiva em `config/apply` e `installer/connect`

## Compatibilidade com cms-app/dashboard
Nenhuma alteracao de contrato e necessaria nesta fase.

## Criterios de aceite
- `cms-app` continua usando os endpoints existentes sem mudanca
- runtime overlay continua funcionando como antes
- o projeto passa a persistir um `Desired State` por tenant em paralelo ao overlay atual
- a base fica pronta para fases seguintes sem depender de novo roundtrip global de `FrigateConfig`

## Proximas fases propostas
### Fase 01
Compilar `Desired State` para `Compiled Engine Config` com fronteira explicita.

### Fase 02
Separar writes em classes (`safe_recovery_write`, `runtime_config_write`, `topology_write`).

### Fase 03
Introduzir state machine por camera (`discovered`, `validated`, `staged`, `applied`, `healthy`, `failed_auth`, `failed_transport`).

### Fase 04
Refatorar installer para pipeline deterministico (`scan`, `probe`, `select`, `stage`, `apply`).

### Fase 05
Isolar Video Plane do Control Plane e endurecer observabilidade/performance por camera.
