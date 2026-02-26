# Fase 12 - CI/CD, Migracoes e Rollback

## Objetivo da fase
Nesta fase eu torno o ciclo de entrega automatizado, seguro e reversivel.

## O que eu vou alterar
- Montar pipeline CI/CD por ambiente (dev, stage, prod).
- Automatizar build, scan de seguranca e publicacao de imagem.
- Aplicar estrategia de migracao Prisma com checkpoint e backup.
- Definir rollback aplicacional e rollback de banco por tipo de mudanca.
- Introduzir deploy progressivo (canary/blue-green).

## Decisoes tecnicas tomadas
- Eu vou bloquear deploy com vulnerabilidade critica sem mitigacao.
- Eu vou separar rollout de codigo e rollout de schema quando necessario.
- Eu vou exigir plano de rollback antes de cada release.

## Criterios de aceite
- Pipeline completo executando sem passos manuais criticos.
- Migracoes com validacao pre e pos deploy.
- Rollback ensaiado e documentado.

## Impacto no sistema
A entrega em producao fica mais segura e com menor MTTR.

## Limitacoes atuais
Playbooks operacionais e topologia final ainda podem evoluir.

## Proximos passos
Eu consolido topologia e runbooks SRE na Fase 13.
