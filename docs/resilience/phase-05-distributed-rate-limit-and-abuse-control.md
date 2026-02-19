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
