# Headless Installer CLI Screen

## Objetivo

Este documento descreve como o setup assistido do Frigate deve ser exibido no terminal, usando o CLI oficial:

```bash
python -m frigate install
```

O foco aqui nao e o contrato HTTP, e sim a experiencia do operador no shell durante o primeiro provisionamento.

## Comandos disponiveis

```bash
python -m frigate install
python -m frigate install wizard
python -m frigate install status
python -m frigate install profile
python -m frigate install scan 192.168.1.0/24
python -m frigate install connect --all
```

O comando sem subcomando entra direto no wizard interativo.

## Experiencia esperada

O CLI deve transmitir:

- seguranca operacional
- clareza no que sera alterado
- leitura facil em SSH
- baixo atrito para ambientes sem frontend

## Fluxo completo no terminal

### 1. Abertura do assistente

Tela esperada:

```text
$ python -m frigate install

== Status do Instalador ==
Habilitado: sim
Cameras configuradas: 0
Restart pendente: não
Ultimo scan: hosts=0, alcancados=0, candidatos=0
```

Se ja houver cameras configuradas:

```text
$ python -m frigate install

== Status do Instalador ==
Habilitado: sim
Cameras configuradas: 4
Restart pendente: não

O assistente so pode ser usado antes da configuracao inicial das cameras.
```

### 2. Levantamento do hardware

Tela esperada:

```text
== Perfil do Hardware ==
Host: frigate-edge-01
CPU: 16 logicas / 8 fisicas
Memoria efetiva: 24.0 GiB
Disco livre: 512.0 GiB
Decode: nvidia
Tier sugerido: edge_robust
Capacidade estimada: 720p@5=20, 1080p@5=12, 1080p@10=7
Observacoes:
- Estimativa heuristica baseada em CPU, RAM e decode
```

Objetivo dessa etapa:

- dar contexto de capacidade antes do scan
- reduzir erro de dimensionamento
- justificar recomendacoes automaticas por camera

### 3. Sugestao de redes e coleta de credenciais

Tela esperada:

```text
Redes sugeridas para scan:
- 192.168.1.0/24
- 10.0.0.0/24

Alvos para o scan (separe por virgula) [192.168.1.0/24,10.0.0.0/24]:
Usuario RTSP/ONVIF [admin]:
Senha RTSP/ONVIF:
```

Comportamento esperado:

- sugerir redes privadas locais quando possivel
- permitir entrada manual de host, faixa ou CIDR
- nao exibir senha em claro

Exemplos validos de alvo:

```text
192.168.1.0/24
192.168.1.20
192.168.1.10-40
192.168.1.0/24,10.0.0.0/24
```

### 4. Execucao da descoberta

Tela esperada:

```text
Executando descoberta de cameras e NVR...

== Resumo da Descoberta ==
Hosts escaneados: 42
Hosts alcancados: 3
Devices ONVIF: 2
Candidatos validados: 6
```

Se nada for encontrado:

```text
Executando descoberta de cameras e NVR...

== Resumo da Descoberta ==
Hosts escaneados: 42
Hosts alcancados: 1
Devices ONVIF: 0
Candidatos validados: 0

Nenhum candidato encontrado.
Nenhuma camera/NVR foi validada com os parametros informados.

Nenhuma camera validada. Revise rede, credenciais e portas antes de tentar novamente.
```

### 5. Exibicao dos candidatos

Tela esperada:

```text
== Candidatos Encontrados ==
[1] nvr_192_168_1_40_ch01 | host=192.168.1.40 | origem=onvif
    2560x1440 | codec=h265 | fps=15.0 | audio=sim
    onvif=Acme/NVR-Pro
    sugestao: detect_fps=5, record=on, audio=on, hwaccel=preset-vaapi

[2] nvr_192_168_1_40_ch02 | host=192.168.1.40 | origem=onvif
    1920x1080 | codec=h264 | fps=10.0 | audio=não
    onvif=Acme/NVR-Pro
    sugestao: detect_fps=5, record=on, audio=off, hwaccel=preset-vaapi

[3] cam_192_168_1_55 | host=192.168.1.55 | origem=rtsp-pattern
    1280x720 | codec=h264 | fps=8.0 | audio=sim
    sugestao: detect_fps=6, record=on, audio=on, hwaccel=auto
```

Cada item deve comunicar:

- nome sugerido
- host
- origem da descoberta
- resolucao, codec e fps
- audio detectado
- fabricante e modelo ONVIF quando houver
- recomendacao automatica aplicada no staging

### 6. Selecao interativa

Tela esperada:

```text
Selecione candidatos por indice (ex: 1,2,4-6) ou 'all' [all]:
Prefixo dos nomes das cameras [cam]:
Habilitar detect? [s]:
Habilitar record? [s]:
```

Entradas aceitas na selecao:

```text
all
1
1,2,3
1,3-5
2-4
```

Se a selecao for invalida:

```text
Selecao invalida: Faixa fora da lista de candidatos
```

### 7. Confirmacao final

Tela esperada:

```text
Resumo da confirmacao:
- candidatos selecionados: 3
- prefixo: cam
- detect: on
- record: on

Aplicar staging agora? [s]:
```

Se o operador cancelar:

```text
Operacao cancelada.
```

### 8. Resultado do staging

Tela esperada:

```text
== Configuracao Preparada ==
Cameras descobertas foram preparadas para o proximo boot do Frigate
Tenant: default
Restart pendente: sim
Cameras:
- cam_nvr_192_168_1_40_ch01
- cam_nvr_192_168_1_40_ch02
- cam_cam_192_168_1_55
Streams go2rtc:
- cam_nvr_192_168_1_40_ch01
- cam_nvr_192_168_1_40_ch02
- cam_cam_192_168_1_55

Proximo passo: reiniciar o Frigate para aplicar as cameras staged.
```

## Experiencia dos subcomandos

### `status`

```text
$ python -m frigate install status

== Status do Instalador ==
Habilitado: sim
Cameras configuradas: 0
Restart pendente: não
Ultimo scan: hosts=0, alcancados=0, candidatos=0
```

### `profile`

```text
$ python -m frigate install profile

== Perfil do Hardware ==
Host: frigate-edge-01
CPU: 16 logicas / 8 fisicas
Memoria efetiva: 24.0 GiB
Disco livre: 512.0 GiB
Decode: vaapi
Tier sugerido: edge_medium
Capacidade estimada: 720p@5=14, 1080p@5=8, 1080p@10=5
```

### `scan`

```text
$ python -m frigate install scan 192.168.1.0/24 --username admin

== Resumo da Descoberta ==
Hosts escaneados: 42
Hosts alcancados: 3
Devices ONVIF: 2
Candidatos validados: 6

== Candidatos Encontrados ==
[1] nvr_192_168_1_40_ch01 | host=192.168.1.40 | origem=onvif
...
```

### `connect`

```text
$ python -m frigate install connect --all

== Configuracao Preparada ==
Cameras descobertas foram preparadas para o proximo boot do Frigate
Tenant: default
Restart pendente: sim
Cameras:
- cam_nvr_192_168_1_40_ch01
- cam_nvr_192_168_1_40_ch02
```

## Variante em JSON

Para automacao ou integracao:

```bash
python -m frigate install status --json
python -m frigate install profile --json
python -m frigate install scan 192.168.1.0/24 --json
```

Saida esperada:

```json
{
  "enabled": true,
  "pending_restart": false,
  "cameras_configured": 0,
  "last_scan_summary": {
    "hosts_scanned": 0,
    "hosts_reachable": 0,
    "candidates_found": 0
  }
}
```

## Diretrizes de UX no terminal

- usar blocos curtos e escaneaveis
- evitar ruido visual
- sempre mostrar o que foi detectado antes de alterar configuracao
- sempre pedir confirmacao antes do staging
- deixar claro que as cameras entram no proximo boot, nao imediatamente
- manter tudo funcional via SSH e shell sem recursos graficos

## Resultado esperado

Ao final do wizard, o operador deve sentir que:

- o ambiente foi inspecionado com criterio
- as cameras foram descobertas com base tecnica
- as sugestoes aplicadas sao justificaveis
- nenhuma alteracao relevante foi feita sem confirmacao
- o processo foi confiavel, previsivel e profissional
