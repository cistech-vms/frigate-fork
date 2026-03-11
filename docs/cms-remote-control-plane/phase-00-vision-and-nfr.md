# Fase 00 - Visao e NFR

## Objetivo da fase
Definir contrato macro, riscos, requisitos nao funcionais e criterio de pronto para iniciar implementacao.

## O que vou definir
- Papel do Frigate: data-plane headless sob controle remoto.
- Papel do CMS: control-plane de configuracao e licenciamento.
- NFR de disponibilidade, seguranca, latencia de sync e resiliencia offline.

## Entregaveis
- Documento de contrato macro CMS <-> Frigate.
- Lista de requisitos obrigatorios de bootstrap.
- Matriz de risco inicial (autenticacao, licenca, config invalida, CMS indisponivel).

## Decisoes tecnicas
- `fail-closed` para operacoes criticas quando licenca invalida.
- `last_known_good` como fallback para indisponibilidade temporaria.
- Toda configuracao remota deve ser versionada e auditavel.

## Criterios de aceite
- Fluxo de ponta a ponta definido do boot ao ready.
- NFR minimo definido:
  - RTO de reconexao ao CMS.
  - limite de idade maxima de configuracao local.
  - politica de grace period para licenca.
- Riscos com mitigacao inicial documentados.

## Definicao de pronto para avancar
- Entradas e saidas de cada fase mapeadas.
- Stakeholders de operacao e seguranca alinhados.
