# Fase 05 - Rate Limit Distribuído e Controle de Abuso

## Objetivo da fase
Nesta fase eu reforço proteção contra abuso em ambiente com múltiplas instâncias, evitando bypass de limite por distribuição de tráfego.

## O que eu vou alterar
- Padronizar chave de limitação por tenant + principal + rota crítica.
- Implementar estratégia de limite coordenado entre instâncias.
- Adicionar bloqueio temporário progressivo para abuso repetido.
- Registrar eventos de segurança para auditoria.

## Decisões técnicas tomadas
- Eu vou manter fallback local seguro quando o backend de coordenação estiver indisponível.
- Eu vou priorizar proteção de endpoints de escrita/configuração.
- Eu vou expor métricas de throttle e rejeição por motivo.

## Impacto no sistema
A API deixa de depender apenas de proteção in-memory por processo e ganha comportamento previsível sob ataque distribuído.

## Limitações atuais
Ainda falta validar recuperação sob falhas reais de processo e rede com testes de caos.

## Próximos passos
Eu avanço para auto-recuperação e caos controlado na Fase 06.

## Implementação aplicada
- Chave de limitação padronizada por `tenant + principal + route_scope + method + path`.
- Estratégia coordenada entre instâncias usando estado compartilhado em arquivo (`/config/headless_rate_limit.json`) com fallback local seguro se houver falha de IO.
- Bloqueio temporário progressivo por abuso repetido (`2^n` sobre janela base, limitado por teto configurável).
- Auditoria de segurança para rejeições de limite (`rate_limit_rejected`) disponível em API para inspeção operacional.

## Arquivos principais alterados
- `frigate/headless/rate_limit.py`
- `frigate/headless/security.py`
- `frigate/api/fastapi_app.py`
- `frigate/api/headless.py`

## Configuração de ambiente
- `FRIGATE_API_RATE_LIMIT_PER_MIN`: limite base por chave.
- `FRIGATE_API_RATE_LIMIT_BLOCK_BASE_SEC`: janela base de bloqueio por reincidência.
- `FRIGATE_API_RATE_LIMIT_BLOCK_MAX_SEC`: teto máximo de bloqueio.
- `FRIGATE_RATE_LIMIT_STATE_PATH`: caminho do estado coordenado (default `/config/headless_rate_limit.json`).

## Operação e auditoria
- Endpoint de inspeção de auditoria: `GET /v1/security/audit`.
- Requisição bloqueada retorna `429` com:
  - `reason`
  - `retry_after_sec`
