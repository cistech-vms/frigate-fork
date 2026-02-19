# Fase 01 - UI Removal

## Objetivo da fase
Nesta fase eu removi a exposição da interface gráfica e passei a executar o Frigate em modo headless por padrão.

## O que foi alterado
Eu adicionei `FRIGATE_HEADLESS=true` como comportamento padrão no bootstrap da API e alterei o roteamento para expor apenas rotas operacionais/headless quando essa flag está ativa.
Eu removi a inclusão das rotas de UI/visualização no bootstrap headless e desativei o `WebSocketClient` usado pela UI.
Eu também removi a cópia dos assets do frontend no Docker final para não empacotar a web UI na imagem headless.

## Decisões técnicas tomadas
Eu optei por não reescrever o pipeline de detecção existente.
Eu centralizei a decisão de modo headless no `create_fastapi_app()` e no `FrigateApp.init_dispatcher()` para reduzir risco de regressão.

## Impacto no sistema
O motor mantém detecção/tracking/eventos e deixa de expor o frontend no modo padrão.
A distribuição de eventos para consumidores externos passa a ser priorizada por API/SSE/MQTT.

## Limitações atuais
A camada Nginx ainda existe na imagem base por compatibilidade operacional.

## Próximos passos
Remover completamente o caminho de proxy `/ws` e rotas de static serving do Nginx em uma imagem dedicada somente API.
