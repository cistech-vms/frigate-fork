# Fase 11 - Estrategia de Testes e Gates de Release

## Objetivo da fase
Nesta fase eu estabeleco qualidade obrigatoria para promover versoes sem regressao funcional ou operacional.

## O que eu vou alterar
- Definir piramide de testes:
  - unitarios (dominio e validacoes)
  - integracao (Prisma + banco)
  - contrato (OpenAPI/eventos)
  - e2e (fluxos editoriais)
- Incluir testes de carga para endpoints criticos.
- Exigir cobertura minima por pacote estrategico.
- Bloquear merge/release quando gate falhar.

## Decisoes tecnicas tomadas
- Eu vou tratar contrato quebrado como incidente de release.
- Eu vou executar suite rapida por PR e suite completa por branch de release.
- Eu vou versionar fixtures de teste para repetibilidade.

## Criterios de aceite
- Pipeline CI reprovando automaticamente regressao critica.
- Evidencias de teste anexadas por release.
- Baseline de performance comparavel entre versoes.

## Impacto no sistema
O processo de entrega fica previsivel e resistente a regressao.

## Limitacoes atuais
Fluxo de deploy e migracao ainda sem automacao completa.

## Proximos passos
Eu estruturo CI/CD, migracoes e rollback na Fase 12.
