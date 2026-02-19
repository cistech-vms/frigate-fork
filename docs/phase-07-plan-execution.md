# Fase 07 - Execução do Plano Recomendado

## Objetivo da fase
Nesta fase eu consolidei a execução completa do plano recomendado (PR1 a PR6), registrando o que foi aplicado no código, a ordem de execução e as validações que eu rodei.

## Etapas aplicadas (ordem real de execução)

### PR1 - Headless bootstrap e desligamento da UI por padrão
Eu habilitei o modo headless como padrão com `FRIGATE_HEADLESS=true` e alterei o bootstrap para não montar rotas de UI quando headless está ativo.
Eu removi a inclusão de rotas visuais no `FastAPI` em modo headless e desativei o `WebSocketClient` da UI no dispatcher quando headless.

Arquivos aplicados:
- `frigate/api/fastapi_app.py`
- `frigate/app.py`
- `frigate/headless/settings.py`

### PR2 - Loader de configuração ENV + runtime overlay
Eu implementei o store de configuração efetiva com prioridade:
1. overlay em runtime via API
2. overlay de ENV (`FRIGATE_CFG__...` e `FRIGATE_CONFIG_JSON`)
3. configuração base validada

Eu também apliquei overlay de ENV no startup antes da inicialização do motor.

Arquivos aplicados:
- `frigate/headless/runtime_config.py`
- `frigate/__main__.py`

### PR3 - API runtime headless
Eu criei os endpoints de configuração e operação headless:
- `POST /v1/config/apply`
- `GET /v1/config/effective`
- `POST /v1/config/validate`
- `POST /v1/reload`
- `GET /v1/status`
- `GET /healthz`
- `GET /readyz`
- `GET /metrics`

Arquivos aplicados:
- `frigate/api/headless.py`
- `frigate/api/fastapi_app.py`

### PR4 - Regiões, triggers e stream de eventos
Eu implementei os endpoints:
- `POST /v1/triggers/upsert`
- `GET /v1/triggers`
- `DELETE /v1/triggers/{id}`
- `POST /v1/cameras/{camera_id}/regions/upsert`
- `GET /v1/cameras/{camera_id}/regions`
- `DELETE /v1/cameras/{camera_id}/regions/{region_id}`
- `GET /v1/events/stream` (SSE)

Eu adicionei um comunicador SSE interno conectado ao dispatcher para permitir stream de eventos server->client sem UI websocket.

Arquivos aplicados:
- `frigate/api/headless.py`
- `frigate/comms/sse.py`
- `frigate/app.py`
- `frigate/api/fastapi_app.py`

### PR5 - Segurança (HMAC/JWT + RBAC + tenant + rate limit)
Eu adicionei middleware/dependências de segurança para modo headless:
- autenticação HMAC por request
- alternativa JWT HS256
- RBAC mínimo (`admin`, `reader`)
- validação de tenant
- rate limiting in-memory por chave/IP
- CORS somente por allowlist de ENV

Arquivos aplicados:
- `frigate/headless/security.py`
- `frigate/api/headless.py`
- `frigate/api/fastapi_app.py`

### PR6 - Docker headless, observabilidade e documentação
Eu removi o copy de assets web da imagem final e alterei healthcheck para endpoint headless.
Eu adicionei exemplo completo de ENV e documentação faseada técnica.
Eu também adicionei um teste unitário de runtime config.

Arquivos aplicados:
- `docker/main/Dockerfile`
- `.env.example`
- `frigate/log.py`
- `frigate/test/test_headless_runtime.py`
- `docs/phase-01-ui-removal.md`
- `docs/phase-02-config-loader.md`
- `docs/phase-03-runtime-api.md`
- `docs/phase-04-regions-api.md`
- `docs/phase-05-security-layer.md`
- `docs/phase-06-event-pipeline.md`

## Decisões técnicas tomadas
Eu preservei o core de detecção/tracking sem reescrever pipeline crítico.
Eu isolei o comportamento headless por feature flag e por bootstrap para reduzir risco de regressão.
Eu reutilizei a infraestrutura de pub/sub existente (dispatcher/comms) para SSE, evitando duplicidade de arquitetura.

## Impacto no sistema
A instância passa a operar como data-plane headless controlável por ENV + API.
A UI deixa de ser exposta em modo headless.
A governança por tenant e autenticação/autorizações mínimas passam a ser nativas no runtime headless.

## Limitações atuais
O rate limiter é local por processo (não distribuído).
`requires_restart` ainda pode evoluir para granularidade mais fina em algumas áreas.
As ações avançadas de trigger (ex: Kafka full executor) estão previstas no contrato e podem ser estendidas na próxima fase.

## Evidências de validação
Eu executei:
- `python3 -m compileall frigate` (compilação sem erro)
- `python3 -m unittest frigate.test.test_headless_runtime` (OK)

## Próximos passos
1. Refinar matriz de hot-reload vs restart por subsistema (decoder/model/detector/output).
2. Adicionar testes de contrato HTTP para rotas `/v1/*` (auth, tenant, validação de schema).
3. Criar imagem Docker dedicada `frigate-headless` removendo dependências legadas de UI/proxy.
