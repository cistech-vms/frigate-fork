# Fase 07 - Reconciliacao Periodica e Offline Mode

## Objetivo da fase
Garantir convergencia continua com o CMS e operacao resiliente durante indisponibilidade remota.

## Reconciliacao
- Loop de sync periodico (polling).
- Backoff exponencial com jitter em falhas.
- Reconciliacao por versao para detectar drift.

## Offline mode
- Sem CMS: operar com `last_known_good` dentro de janela permitida.
- Expirada a janela: modo restrito conforme politica de licenca.

## Entregaveis
- Worker de sync com controle de estado.
- Indicadores de staleness da configuracao.
- Mecanismo manual `force-sync` via API.

## Decisoes tecnicas
- Nao bloquear camera pipeline por falha transitiva de rede.
- Separar erro de conectividade de erro de contrato.

## Criterios de aceite
- Reconexao automatica apos queda do CMS.
- Sem perda de configuracao ativa na reconexao.
- Estado `stale_config` quando idade maxima for excedida.

## Definicao de pronto para avancar
- Operacao estavel em cenarios online/offline.
