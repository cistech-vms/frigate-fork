# Fase 14 - Gestão de Segredos e Rotação de Chaves

## Objetivo da fase
Nesta fase eu endureço a segurança operacional com rotação planejada de segredos e controle de exposição de credenciais.

## O que eu vou alterar
- Definir ciclo de vida para chaves HMAC/JWT e credenciais de storage.
- Implementar política de dupla chave durante rotação.
- Bloquear logs com dados sensíveis e revisar mascaramento.
- Documentar procedimento de revogação emergencial.

## Decisões técnicas tomadas
- Eu vou adotar rotação sem downtime quando possível.
- Eu vou manter trilha de auditoria para trocas de segredo.
- Eu vou limitar escopo de credencial por tenant/serviço.

## Impacto no sistema
A superfície de risco por vazamento de segredo reduz e a resposta a incidente fica mais rápida.

## Limitações atuais
A maturidade depende de disciplina contínua de operação e revisão periódica de permissões.

## Próximos passos
Eu formalizo versionamento de contrato de API e eventos.

## Implementação aplicada
- Rotação com dupla chave (`active` + `previous`) e revogação explícita de chave anterior.
- Masking de segredo na visualização operacional.
- Trilha de auditoria persistida para eventos de rotação e revogação.

## Evidência de operação
- `POST /v1/resilience/secrets/rotate`
- `POST /v1/resilience/secrets/revoke/{name}`
- `GET /v1/resilience/secrets/status`
