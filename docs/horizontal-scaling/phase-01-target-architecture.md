# Fase 01 - Arquitetura Alvo (Control Plane x Data Plane)

## Objetivo
Definir desenho-alvo para escala horizontal por tenant/câmera.

## Proposta

### Control Plane (cloud)
- Cadastro de tenants, câmeras e políticas.
- Versionamento de configuração.
- Scheduler de alocação de câmeras por nó/shard.
- Rollout/canary/rollback.

### Data Plane (edge nodes)
- Runtime headless Frigate por nó.
- Cada nó executa N shards (process groups) com subset de câmeras.
- API local para status/aplicar config/version.

### Contrato entre planos
- Config declarativa versionada (`config_version`, `tenant_id`, `assigned_cameras`).
- Heartbeat periódico com carga/capacidade (`fps`, `queue_depth`, `inference_latency`).

## Decisão técnica
Manter Frigate como engine de inferência e tracking, adicionando camada de shard orchestration sem acoplamento com UI.

## Saída da fase
Especificação de topologia e responsabilidades por componente.

## Implementação aplicada
- Manager de scaling no data-plane com estado de plano por tenant, heartbeat e rollout.
- Separação funcional entre plano desejado (`desired_version`) e convergência aplicada (`applied_version`).
- Endpoints dedicados para aplicar plano, reconciliar estado e observar rollout.
