# Fase 21 - Hardening de Supply Chain e Imagem Docker

## Objetivo da fase
Nesta fase eu reduzo risco de segurança na cadeia de build e distribuição da aplicação.

## O que eu vou alterar
- Gerar SBOM por build e publicar artefato.
- Aplicar scan de vulnerabilidade em dependências e imagem.
- Assinar imagem e validar proveniência.
- Reduzir superfície da imagem base (mínimo necessário).

## Decisões técnicas tomadas
- Eu vou bloquear release com vulnerabilidade crítica sem mitigação.
- Eu vou manter rastreabilidade entre commit, imagem e deploy.
- Eu vou revisar periodicamente dependências de alto risco.

## Impacto no sistema
A chance de comprometimento por dependência vulnerável ou imagem adulterada reduz de forma relevante.

## Limitações atuais
Hardening exige manutenção contínua; não é tarefa de execução única.

## Próximos passos
Eu fecho com validação de carga e caos como gate final de robustez.

## Implementação aplicada
- Geração de SBOM simplificada por build com digest de manifesto de arquivos.
- Registro de scan de vulnerabilidade com bloqueio de release em severidade crítica.
- Assinatura lógica de imagem para rastreabilidade operacional.

## Evidência de operação
- `POST /v1/resilience/supply-chain/sbom`
- `POST /v1/resilience/supply-chain/scan`
- `POST /v1/resilience/supply-chain/sign`
- `GET /v1/resilience/supply-chain/status`
