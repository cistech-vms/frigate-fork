# Fase 08 - Limpeza Final da Camada Web

## Objetivo da fase
Nesta fase eu finalizei a limpeza da camada web/interface para manter o projeto operando apenas como runtime headless.

## O que foi alterado
Eu removi a pasta `web/` completamente.
Eu removi os módulos legados de interface em runtime: `frigate/output/` e `frigate/comms/ws.py`.
Eu removi referências de build frontend no Docker (`web-build`, cópia de assets e dependências de Node para web build).
Eu removi a dependência `ws4py` da lista de wheels do runtime headless.
Eu removi o volume `./web/dist:/opt/frigate/web` do `docker-compose.yml`.
Eu removi o passo de geração de `.env` do frontend no `Makefile`.
Eu removi jobs de CI específicos do frontend no workflow de pull request.
Eu alterei o Nginx para não servir raiz estática (`location /`) e bloquear rotas de websocket/live da interface (`/ws`, `/live/jsmpeg/`) com `404`.

## Decisões técnicas tomadas
Eu mantive o core de detecção e event pipeline sem reescrita estrutural.
Eu priorizei remoção de superfície de interface e de dependências diretas de frontend para deixar o runtime coerente com o perfil headless.

## Impacto no sistema
A camada de interface não é mais servida no projeto atual.
A imagem/container não depende mais de assets do frontend para o caminho principal de execução headless.

## Limitações atuais
Como consequência da remoção total da camada visual, funcionalidades relacionadas a birdseye/jsmpeg/websocket UI deixaram de existir nesta distribuição.

## Próximos passos
1. Enxugar configuração de Nginx para um perfil API-only.
2. Publicar uma imagem dedicada `frigate-headless` sem componentes legados opcionais.
