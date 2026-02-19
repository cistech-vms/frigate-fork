# Fase 12 - Consistência e Reconciliação de Storage por Configuração Dinâmica

## Objetivo da fase
Nesta fase eu garanto consistência operacional quando a configuração de storage muda em runtime via API, sem interromper o core de detecção.

## O que eu vou alterar
- Versionar configuração efetiva de storage por tenant (`storage_config_version`).
- Aplicar mudanças com estratégia segura:
  - validar
  - preparar destino
  - ativar escrita nova
  - drenar pendências antigas
- Implementar fila de replicação com retry/backoff e dead-letter para falhas permanentes.
- Criar reconciliador periódico para reprocessar itens pendentes.
- Expor endpoint de observabilidade de sincronização:
  - backlog
  - throughput
  - falhas por destino
  - última sincronização bem-sucedida

## Decisões técnicas tomadas
- Eu vou separar plano de controle (config) do plano de dados (replicação de mídia).
- Eu vou garantir idempotência por chave determinística de objeto.
- Eu vou manter política explícita para conflito de versão e rollback de configuração.

## Impacto no sistema
A troca de configuração recebida por API deixa de ser arriscada para integridade dos dados, mesmo com rede intermitente e mudanças frequentes de destino.

## Limitações atuais
Em ambientes extremamente restritos, backlog prolongado pode exigir política de descarte por prioridade para preservar operação local.

## Próximos passos
Após esta fase, eu fecho critérios de aceitação por tenant para rollout seguro em produção.
