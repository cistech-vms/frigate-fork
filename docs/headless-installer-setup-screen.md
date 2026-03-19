# Headless Installer Setup Screen

## Objetivo

Este documento descreve a tela headless de instalacao que deve ser apresentada durante o primeiro setup do Frigate, com base no fluxo atual ja implementado na API.

O instalador so deve aparecer quando:

- `FRIGATE_INSTALLER_ENABLED=true`
- ainda nao existem cameras configuradas
- o modo headless esta ativo

Endpoints usados pelo wizard:

- `GET /install/status`
- `POST /install/hardware/profile`
- `POST /install/discovery/scan`
- `GET /install/discovery/candidates`
- `POST /install/discovery/connect`

## Modos de uso

O fluxo agora pode ser consumido de duas formas:

- por interface web headless, usando os endpoints de instalacao
- por terminal, via CLI oficial:

```bash
python -m frigate install
```

Comandos principais do CLI:

```bash
python -m frigate install status
python -m frigate install profile
python -m frigate install scan 192.168.1.0/24
python -m frigate install connect --all
python -m frigate install wizard
```

O comando sem subcomando entra direto no wizard interativo.

## Fluxo da Tela

### Etapa 1. Status do instalador

Objetivo:

- confirmar que o assistente esta habilitado
- verificar se ainda nao houve configuracao inicial
- informar se existe patch pendente de restart

Fonte:

- `GET /install/status`

Campos exibidos:

- `enabled`
- `pending_restart`
- `cameras_configured`
- `last_scan_summary`

Wireframe:

```text
+-------------------------------------------------------------+
| Frigate Setup Assistido                                     |
+-------------------------------------------------------------+
| Status do instalador: ATIVO                                 |
| Cameras ja configuradas: 0                                  |
| Reinicio pendente: NAO                                      |
| Ultimo scan: nenhum                                         |
|                                                             |
| [Continuar]                                                 |
+-------------------------------------------------------------+
```

### Etapa 2. Perfil do hardware

Objetivo:

- detectar CPU, memoria, disco e aceleracao de decode
- estimar capacidade inicial do servidor
- orientar o operador antes de conectar varias cameras

Fonte:

- `POST /install/hardware/profile`

Campos exibidos:

- hostname
- CPUs logicas e fisicas
- memoria efetiva
- disco livre
- aceleracao detectada: `software`, `vaapi` ou `nvidia`
- estimativa de capacidade:
  - `720p_5fps`
  - `1080p_5fps`
  - `1080p_10fps`
- observacoes heuristicas

Wireframe:

```text
+-------------------------------------------------------------+
| Etapa 1 de 4 - Capacidade do Servidor                       |
+-------------------------------------------------------------+
| Host: frigate-edge-01                                       |
| CPU: 16 logicas / 8 fisicas                                 |
| Memoria efetiva: 24 GiB                                     |
| Disco livre: 500 GiB                                        |
| Decode: nvidia                                              |
|                                                             |
| Estimativa de capacidade                                    |
| - 720p @ 5fps: 20 cameras                                   |
| - 1080p @ 5fps: 12 cameras                                  |
| - 1080p @ 10fps: 7 cameras                                  |
|                                                             |
| Observacoes                                                 |
| - Estimativa heuristica baseada em CPU, RAM e decode        |
|                                                             |
| [Voltar]                             [Avancar para Descoberta]|
+-------------------------------------------------------------+
```

### Etapa 3. Descoberta de NVR e cameras

Objetivo:

- informar a rede que sera analisada
- testar ONVIF e RTSP
- enumerar devices, canais e streams validos

Fonte:

- `POST /install/discovery/scan`

Payload sugerido da tela:

```json
{
  "targets": ["192.168.1.0/24"],
  "username": "admin",
  "password": "******",
  "rtsp_ports": [554, 8554],
  "onvif_ports": [80, 8000, 8080, 8899],
  "profiles": ["hikvision", "dahua", "reolink", "uniview", "generic"],
  "max_hosts": 256,
  "max_channels": 16,
  "max_candidates": 128,
  "timeout_sec": 2.0
}
```

Campos de entrada:

- alvo da rede
- usuario e senha
- portas RTSP
- portas ONVIF
- perfis conhecidos
- limites de scan

Campos exibidos no resultado:

- `hardware_profile`
- `targets_scanned`
- `reachable_hosts`
- `onvif_devices`
- `candidates`
- `summary`
- `connect_prompt`

Wireframe:

```text
+-------------------------------------------------------------+
| Etapa 2 de 4 - Descoberta de Cameras e NVR                  |
+-------------------------------------------------------------+
| Rede alvo                                                   |
| [ 192.168.1.0/24                                  ]         |
| Usuario [ admin                          ]                  |
| Senha   [ ********                       ]                  |
|                                                             |
| Perfis                                                       |
| [x] Hikvision  [x] Dahua  [x] Reolink  [x] Uniview  [x] Gen |
|                                                             |
| Portas RTSP: 554, 8554                                      |
| Portas ONVIF: 80, 8000, 8080, 8899                          |
|                                                             |
| [Executar Scan]                                             |
+-------------------------------------------------------------+
```

### Etapa 4. Revisao dos dispositivos encontrados

Objetivo:

- apresentar ao operador tudo que foi detectado
- mostrar se a descoberta veio por ONVIF ou por padrao RTSP
- sugerir configuracao inicial por camera

Cada candidato deve exibir:

- nome sugerido
- host e porta
- origem: `onvif` ou `rtsp-pattern`
- tipo: `camera` ou `nvr_channel`
- resolucao
- codec
- fps detectado
- audio detectado
- metadata ONVIF quando existir:
  - fabricante
  - modelo
  - token/perfil
- recomendacao:
  - `detect_fps`
  - `record_enabled`
  - `audio_enabled`
  - `hwaccel_args`
  - `input_preset`

Wireframe:

```text
+-------------------------------------------------------------+
| Etapa 3 de 4 - Revisao do Levantamento                      |
+-------------------------------------------------------------+
| Resumo                                                      |
| - Hosts escaneados: 42                                      |
| - Hosts alcancados: 3                                       |
| - Devices ONVIF: 2                                          |
| - Candidatos validados: 6                                   |
|                                                             |
| [x] nvr_192_168_1_40_ch01                                   |
|     Origem: ONVIF                                           |
|     Modelo: NVR-Pro                                         |
|     Stream: 2560x1440 / h265 / 15fps / audio sim            |
|     Sugestao: detect_fps=5, record=on, audio=on             |
|     HWAccel: preset-vaapi                                   |
|                                                             |
| [x] nvr_192_168_1_40_ch02                                   |
|     Origem: ONVIF                                           |
|     Stream: 1920x1080 / h264 / 10fps / audio nao            |
|     Sugestao: detect_fps=5, record=on, audio=off            |
|                                                             |
| [ ] cam_192_168_1_55                                        |
|     Origem: RTSP Pattern                                    |
|     Stream: 1280x720 / h264 / 8fps / audio sim              |
|     Sugestao: detect_fps=6, record=on, audio=on             |
|                                                             |
| [Voltar]                               [Conectar Selecionadas]|
+-------------------------------------------------------------+
```

### Etapa 5. Confirmacao e staging

Objetivo:

- transformar os candidatos selecionados em patch de configuracao
- persistir `cameras` e `go2rtc`
- informar que o setup foi preparado para o proximo boot

Fonte:

- `POST /install/discovery/connect`

Payload sugerido da tela:

```json
{
  "candidate_ids": [
    "192.168.1.40-onvif-profile1",
    "192.168.1.40-onvif-profile2"
  ],
  "connect_all": false,
  "camera_name_prefix": "cam",
  "detect_enabled": true,
  "record_enabled": true
}
```

Resposta esperada:

- `staged`
- `pending_restart`
- `message`
- `tenant_id`
- `cameras`
- `go2rtc_streams`

Wireframe:

```text
+-------------------------------------------------------------+
| Etapa 4 de 4 - Configuracao Preparada                       |
+-------------------------------------------------------------+
| Cameras selecionadas foram preparadas com sucesso.          |
|                                                             |
| Cameras criadas                                             |
| - cam_nvr_192_168_1_40_ch01                                 |
| - cam_nvr_192_168_1_40_ch02                                 |
|                                                             |
| Streams go2rtc                                              |
| - cam_nvr_192_168_1_40_ch01                                 |
| - cam_nvr_192_168_1_40_ch02                                 |
|                                                             |
| Reinicio pendente: SIM                                      |
|                                                             |
| [Revisar]                                 [Reiniciar Frigate]|
+-------------------------------------------------------------+
```

## Regras de comportamento da UI

- O assistente deve bloquear a instalacao se `cameras_configured > 0`.
- O assistente deve esconder a etapa de descoberta se o instalador estiver desabilitado.
- A tela deve permitir desmarcar candidatos antes do `connect`.
- As recomendacoes automaticas devem vir preenchidas por padrao, mas a UI pode permitir override antes da confirmacao.
- O texto final deve deixar claro que a conexao das cameras fica staged para o proximo boot, e nao hot-add imediato.

## Estrutura visual sugerida

- Barra superior com status do host e etapa atual
- Card principal para o formulario ativo
- Painel lateral com:
  - resumo de capacidade do hardware
  - contagem de devices encontrados
  - status de restart pendente
- Tabela ou lista expansivel para candidatos detectados
- CTA final sempre explicito: `Conectar selecionadas` ou `Reiniciar Frigate`

## Observacoes de produto

- Hoje o backend suporta bem um wizard web em `React` ou `Next.js`.
- O scan atual aceita alvo manual por rede, faixa ou host.
- O valor default atual de `targets` ainda esta fixado em `192.168.1.0/24`; idealmente a UI deve sugerir a rede, nao assumir silenciosamente.
- A descoberta ONVIF melhora bastante a qualidade do onboarding, mas alguns fabricantes podem responder parcialmente; nesse caso o fallback RTSP continua valido.

## Resultado esperado da experiencia

Ao final da instalacao, o operador deve conseguir:

1. entender a capacidade aproximada do servidor
2. localizar NVRs e cameras disponiveis na rede
3. revisar canais e streams validados
4. aceitar recomendacoes automaticas por camera
5. preparar a configuracao inicial com o menor numero possivel de campos manuais
