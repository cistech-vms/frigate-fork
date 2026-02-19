# Planning - 100 Câmeras por Nó (Arquitetura Horizontal Edge-First)

## 1) Objetivo
Definir um plano técnico viável para operar **100 câmeras por nó** usando a arquitetura horizontal edge-first já desenhada, com opções de hardware baseadas em:
- Intel Xeon
- AMD Ryzen

Este plano considera operação local por cliente (condomínio, escola, empresa), com control-plane em nuvem e data-plane no edge.

---

## 2) Premissas obrigatórias (para bater 100 câmeras/nó)

## 2.1 Perfil de vídeo
- Uso de **substream para detecção**.
- Detecção em **5 FPS por câmera** (baseline).
- Stream principal reservado para gravação/consulta quando necessário.

## 2.2 Perfil de carga
- Cenário de movimento moderado.
- Regras/triggers com complexidade média.
- Sem uso extremo simultâneo de recursos de IA adicionais por todas as câmeras.

## 2.3 Operação
- Headroom operacional mínimo de 25-30%.
- Observabilidade ativa (latência, filas, drops, CPU/GPU).
- Rollout de configuração versionada via control-plane.

---

## 3) Meta de throughput por nó
Para 100 câmeras com 5 FPS de detecção:

`fps_total_detect = 100 x 5 = 500 FPS`

Com margem de segurança de 30%, o nó precisa sustentar aproximadamente:

`fps_sustentavel_no >= 500 / 0.70 ≈ 715 FPS`

Meta recomendada de engenharia:
- **700-800 FPS sustentáveis** no benchmark do nó.

---

## 4) Requisitos mínimos recomendados por plataforma

## 4.1 Opção Intel (família Xeon)
### Perfil recomendado (100 câmeras/nó)
- CPU: **Xeon Silver/Gold** com 16-24 cores físicos
- RAM: **64-128 GB**
- GPU: **RTX 4070 / RTX A4000** (ou superior equivalente)
- Disco:
  - SO + runtime: NVMe 1 TB
  - retenção: NVMe/SATA adicional conforme política (mín. 4 TB recomendado)
- Rede: **2.5 GbE** (mínimo) / 10 GbE preferível em ambiente denso
- SHM: 8 GB (ajustar após benchmark)

Faixa esperada (com tuning correto):
- **90-130 câmeras por nó**

## 4.2 Opção AMD (família Ryzen)
### Perfil recomendado (100 câmeras/nó)
- CPU: **Ryzen 9 7900/7950X** (12-16 cores de alta frequência)
- RAM: **64-128 GB DDR5**
- GPU: **RTX 4070 / RTX 4080 / RTX A4000**
- Disco:
  - SO + runtime: NVMe 1 TB
  - retenção: 4 TB+ em NVMe/SATA conforme política
- Rede: **2.5 GbE** (mínimo) / 10 GbE preferível
- SHM: 8 GB (ajustar por resolução e perfil)

Faixa esperada (com tuning correto):
- **85-125 câmeras por nó**

Observação:
- Ryzen tende a performar muito bem em clock/single-thread; Xeon tende a oferecer robustez de plataforma/IO e previsibilidade em perfil server-grade.

---

## 5) Tabela comparativa rápida (target 100 câmeras)

| Item | Xeon (recomendado) | Ryzen (recomendado) |
|---|---|---|
| CPU | 16-24 cores server-grade | 12-16 cores high-clock |
| RAM | 64-128 GB | 64-128 GB |
| GPU | RTX 4070 / RTX A4000 | RTX 4070 / 4080 / A4000 |
| Rede | 2.5/10 GbE | 2.5/10 GbE |
| SHM inicial | 8 GB | 8 GB |
| Faixa típica | 90-130 | 85-125 |
| Perfil de uso | robustez contínua | alta performance/custo |

---

## 6) Requisitos de armazenamento por política de gravação

## 6.1 Gravação contínua
- Alto consumo de disco.
- Recomendado separar volume de mídia do volume de sistema.

## 6.2 Gravação por movimento/objeto
- Menor pressão de IOPS e capacidade.
- Mais adequado para buscar 100 câmeras/nó com custo controlado.

## 6.3 Diretriz prática
- Começar com **4 TB úteis por nó** para retenção moderada.
- Ajustar após medição real de bitrate e janelas de retenção.

---

## 7) Requisitos de rede para 100 câmeras
- Switches e uplinks devem suportar tráfego agregado sem congestionamento.
- VLAN dedicada para câmeras é recomendada.
- Para 100 câmeras, **2.5 GbE é piso**; **10 GbE** reduz risco operacional.
- QoS e segmentação ajudam estabilidade do ingest.

---

## 8) Plano de benchmark e aceite (go/no-go)

## 8.1 Etapas
1. Teste com 25 câmeras
2. Escalar para 50
3. Escalar para 75
4. Escalar para 100

## 8.2 Critérios de aceite em 100 câmeras
- p95 inferência dentro do SLO definido
- fila de detecção estável (sem crescimento contínuo)
- drop de frames abaixo do limite acordado
- CPU/GPU sem saturação sustentada
- gravação sem atraso anormal de segmentos

## 8.3 Critério de reprovação
- backlog crescente por mais de 30 min
- p95/p99 degradando continuamente
- reinícios frequentes de captura/detector

---

## 9) SLO sugerido para operação em 100 câmeras/nó
- Disponibilidade do nó: >= 99.5%
- Latência de inferência p95: limite definido por perfil (ex: <= 250 ms)
- Drop rate de frames: abaixo do limite interno (ex: < 2-3%)
- Entrega de eventos críticos: >= 99%

---

## 10) Estratégia de implantação por cliente

## 10.1 Condomínio (100 câmeras)
- 1 nó robusto + 1 nó de contingência (recomendado)
- distribuição por blocos/perímetro

## 10.2 Escola (100 câmeras)
- 1 nó principal + reserva de capacidade
- distribuição por prédio/setor

## 10.3 Empresa (100 câmeras)
- 1 nó principal + plano de failover
- integração de eventos com SIEM/automação local

---

## 11) Riscos e mitigação
- Risco: câmeras sem substream adequado
  - Mitigação: padronização de perfil de stream
- Risco: hardware subdimensionado de GPU
  - Mitigação: benchmark com carga real antes de produção
- Risco: retenção configurada acima da capacidade
  - Mitigação: política por tier e monitoramento de storage
- Risco: rede local congestionada
  - Mitigação: segmentação + uplink 10GbE em cenários densos

---

## 12) Conclusão executiva
É viável atingir **100 câmeras por nó** na arquitetura edge-first, desde que:
- o nó tenha GPU adequada e CPU compatível;
- a detecção use substream com 5 FPS;
- haja margem operacional de 25-30%;
- o ambiente passe por benchmark progressivo com critérios claros de aceite.

Tanto **Xeon** quanto **Ryzen** são viáveis. A escolha deve considerar padrão do cliente (server-grade vs custo/performance), disponibilidade local e resultados de benchmark real.
