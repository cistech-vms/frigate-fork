# Fase 22 - Validação de Carga e Caos

## Objetivo da fase
Nesta fase eu valido robustez com cenários de carga realista e falhas induzidas antes de promover versão para produção.

## O que eu vou alterar
- Definir perfis de carga por faixa de câmeras por nó.
- Medir latência, perda de evento, backlog e recuperação.
- Rodar cenários de caos (rede intermitente, restart, storage lento).
- Transformar resultados em gate objetivo de release.

## Decisões técnicas tomadas
- Eu vou usar cenários reproduzíveis e comparáveis entre versões.
- Eu vou reprovar release que degrade métricas críticas acima do limite.
- Eu vou documentar baseline de performance por hardware.

## Impacto no sistema
A robustez deixa de ser percepção e passa a ser comprovada por experimento repetível.

## Limitações atuais
Sem ambiente de teste representativo, resultados podem não refletir totalmente a produção.

## Próximos passos
Eu consolido revisão contínua das fases para manter robustez ao longo da evolução do produto.

## Implementação aplicada
- Registro de resultados de carga/caos por perfil com métricas críticas.
- Sumário com gate objetivo (`gate_passed`) por latência, perda, backlog e recuperação.
- Endpoint operacional para histórico incremental e decisão de promoção.

## Evidência de operação
- `POST /v1/resilience/load-chaos/record`
- `GET /v1/resilience/load-chaos/summary`
