# Documentação do Software — Determinação Automatizada de CTC em Argilas Bentoníticas

> **Status:** documento em construção junto com o desenvolvimento do software.
> Seções marcadas com `🔲 [A PREENCHER]` ainda precisam de detalhes técnicos específicos do código.
> Última atualização: 20/09/2026.

---

## 1. Visão Geral

**Título do projeto (PIBIC):** Técnicas e ferramentas computacionais para classificação e inferência de propriedades de argilas bentoníticas via aprendizado de máquina, banco de dados e interface de usuário.

**Objetivo do software:** automatizar a determinação da Capacidade de Troca Catiônica (CTC/CEC) de argilas bentoníticas por titulação condutimétrica com azul de metileno (método CMC), substituindo a leitura manual(a olho nu) do ponto de viragem por detecção algorítmica em tempo real, com registro em banco de dados e posterior análise por aprendizado de máquina.

**Referência metodológica:** dissertação de Silva Neto (2023, UFPB/LAPAMA) — base para o algoritmo de detecção de CMC e para a Equação I de cálculo da CTC.


## 2. Arquitetura do Sistema

```
┌─────────────────────────────────────────────────────────┐
│                    Raspberry Pi 3 (64-bit)                │
│                   Display touchscreen 800×480             │
│                                                             │
│  ┌──────────────┐      ┌─────────────────────────────┐   │
│  │   Arduino     │─────▶│  Interface PySide6 (SCADA)   │   │
│  │ (sensor TDS)  │ USB  │  medicao.py / interface/     │   │
│  │ CH340 driver  │      └───────────┬───────────────────┘   │
│  └──────────────┘                  │                       │
│                                     ▼                       │
│                         ┌───────────────────────┐          │
│                         │  SQLite local          │          │
│                         │  argilas.db            │          │
│                         │  (banco_local.py)       │          │
│                         └───────────┬───────────┘          │
│                                     │ sync a cada 5 min     │
│                                     │ (systemd timer)        │
└─────────────────────────────────────┼───────────────────────┘
                                      ▼
                    ┌──────────────────────────────┐
                    │  Cloudflare Workers + D1       │
                    │  sync-worker-argilas           │
                    └──────────────┬────────────────┘
                                   ▼
                    ┌──────────────────────────────┐
                    │  DuckDB (análise offline)      │
                    │  pibic_dados.duckdb            │
                    │  tabela: atributos_ctc         │
                    │  (analise_ml_argilas.py)       │
                    └──────────────────────────────┘
```

---

## 3. Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Interface (UI) | Python + PySide6 (estilo SCADA touchscreen) |
| Hardware | Raspberry Pi 3 (64-bit) + Arduino (CH340, VID=0x1A86) + sensor DFRobot GravityTDS |
| Banco local (operacional) | SQLite (`argilas.db`) |
| Banco analítico | DuckDB (`pibic_dados.duckdb`, tabela `atributos_ctc`) |
| Sincronização remota | Cloudflare Workers + Cloudflare D1 |
| Agendamento de sync | systemd timer |
| Acesso remoto | Tailscale (SSH) |
| ML | scikit-learn, joblib (inferência local no Pi) |
| Análise/visualização | pandas, matplotlib, seaborn |
| Outros dados | Parquet/CSV (dataset de referência Kaufhold & Dohrmann 2008, ~38 amostras) |

**Requisitos:** 🔲 [A PREENCHER] — colar aqui o conteúdo final de `requirements.txt` quando fechado.

---

## 4. Constantes e Parâmetros do Método

| Constante | Valor | Descrição |
|---|---|---|
| `cT` | 3.7 g/L | Concentração do titulante (azul de metileno) |
| `N` | 0.01 N | Normalidade do titulante |
| `MM` | 319.85 g/mol | Massa molar do azul de metileno |
| `limiar_linearidade` | 10.0 | Limiar de tolerância usado no algoritmo de detecção do CMC |


---

## 5. Módulos do Software

### 5.1 `medicao.py` / `interface/medicao.py` — Interface de medição
- Interface principal em PySide6, com três estados: **Estado Inicial → Estado Coleta → Estado Finalizado**
- Duas visualizações de gráfico (condutividade × volume titulante)
- Botões de rodapé com gerenciamento de estado
- Detecção de CMC em tempo real integrada à coleta
- 🔲 [A PREENCHER] Fluxo detalhado de eventos/sinais (signals/slots) entre telas

### 5.2 `analise.py` — Algoritmo de análise CMC/CTC
- Implementa `identificar_trechos_lineares`: expande uma janela linear a partir do final dos dados, usando `limiar_linearidade`; o CMC é sempre o ponto mais à esquerda da maior janela válida (nunca interpolado — é sempre um ponto medido diretamente)
- Implementa o cálculo da CTC via Equação I da dissertação de referência
- 🔲 [A PREENCHER] Assinatura da função principal, parâmetros de entrada/saída, exemplo de chamada

### 5.3 `banco_local.py` — Camada de persistência local
- SQLite offline-first: todas as medições são gravadas localmente antes de qualquer tentativa de sync
- Colunas de controle de sincronização: `uuid_sync`, `sincronizado`
- 🔲 [A PREENCHER] Esquema completo das tabelas (colunas, tipos, chaves)

### 5.4 `historico.py` — Histórico de medições
- 🔲 [A PREENCHER] Descrição funcional (listagem, filtros, exportação?)

### 5.5 `analise_ml_argilas.py` — Pipeline de Machine Learning
- Lê da tabela `atributos_ctc` (DuckDB)
- Modelos de regressão avaliados: Linear Regression, Ridge, KNN (k=2), Decision Tree, Random Forest, SVR, MLP — 🔲 [A PREENCHER] status de validação de cada um
- PCA + K-Means já validados em 6 amostras comerciais brasileiras (Bentogel, Brasgel, Chocobofe, Chocolate, Closite, Verde Lodo): 3 componentes PCA (89,8% de variância explicada), k=4 selecionado por silhueta
- Modelo final roda inferência localmente no Pi via `.pkl`/joblib — sem chamada remota em tempo de inferência
- 🔲 [A PREENCHER] Nome do arquivo do modelo serializado e como é carregado

### 5.6 `sync-worker-argilas` — Worker Cloudflare
- Recebe dados do Pi via SQLite → D1
- 🔲 [A PREENCHER] Endpoints, autenticação (API key em `/etc/sync-argilas.env` e como secret no Worker), payload esperado

### 5.7 `main.py`
- 🔲 [A PREENCHER] Ponto de entrada da aplicação — o que ele orquestra

---

## 6. Fluxo de Dados

1. Arduino lê condutividade (µS/cm) e ppm via sensor GravityTDS
2. `medicao.py` recebe os dados em tempo real e alimenta o gráfico
3. `analise.py` detecta o ponto de CMC durante a titulação (algoritmo de janela linear)
4. CTC é calculada pela Equação I e exibida na tela
5. Medição é persistida no SQLite local (`banco_local.py`) — **sempre**, mesmo sem internet
6. A cada 5 minutos, um timer systemd tenta sincronizar os registros não sincronizados (`sincronizado = 0`) com o Cloudflare D1
7. Dados sincronizados alimentam o DuckDB para análise offline e treinamento/validação dos modelos de ML

---

## 7. Decisões de Design e Princípios

- **Offline-first é inegociável**: internet do laboratório é instável; perder uma medição de titulação (não repetível) é inaceitável.
- **Separação de dados estáticos vs. operacionais**: dataset de referência (Kaufhold & Dohrmann 2008) fica em Parquet/CSV, fora do SQLite operacional; DuckDB faz o papel de camada de junção/consulta entre as duas fontes.
- **Sem interpolação no CMC**: o ponto de CMC é sempre um ponto medido diretamente, nunca inferido por interpolação.
- **Prevenção de vazamento de dados (data leakage)**: variáveis de cátions trocáveis não podem ser usadas como preditoras nos modelos supervisionados (Random Forest/MLP); CTC pode ser usada em clustering (EDA), mas não como preditor downstream.
- **Inferência local**: o Pi roda o modelo `.pkl`/joblib localmente — nenhuma chamada remota é necessária para gerar uma predição.
- **UI segue ISA-101 / ISO 9241**: fundo cinza neutro dominante, cor reservada só para estado/ação, alvos de toque mínimos de 56px, redundância ícone+texto para acessibilidade a daltonismo.
- **Secrets fora do versionamento**: chaves de API mantidas via `.env` / `EnvironmentFile`, nunca commitadas.

---

## 8. Problemas Conhecidos

| Problema | Status | Observação |
|---|---|---|
| Pontos de condutividade não monotônicos (ruído de sensor/bolhas) | Requer remoção manual | Afeta amostras Verde Lodo e Cloisite Na+ |
| Leituras seriais duplicadas do Arduino em `closite2.csv` causando detecção errada de CMC | 🔲 Não corrigido | Pré-filtro de sanidade foi proposto, ainda não implementado |
| Incompatibilidade PySide6 em ARM 32-bit no Pi 3 | ✅ Resolvido | Solução: reinstalar com Raspberry Pi OS 64-bit |
| Erro de transcrição na Tabela 6 de Silva Neto (2023) — CTC do Brasgel (67,68 mEq/100g) corresponde ao método manual, não ao automatizado | Documentado | Pode afetar posicionamento no espaço PCA |
| Colunas de percentual de DRX no CSV — fração decimal (0–1) ou percentual (0–100)? | 🔲 Em aberto | Precisa ser resolvido antes de finalizar figuras do relatório |

---

## 9. Instalação e Execução

🔲 [A PREENCHER] — preencher com os passos reais assim que estiverem estabilizados. Estrutura sugerida:

```bash
# 1. Clonar o repositório
git clone <url-do-repo>
cd <projeto>

# 2. Criar ambiente virtual
python3 -m venv venv
source venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente (API key do sync)
cp .env.example /etc/sync-argilas.env
# editar com os valores reais

# 5. Rodar a aplicação
python main.py
```

**Acesso remoto (manutenção):** Pi acessível via Tailscale (IP virtual 100.x.x.x), SSH com autenticação por chave, login por senha desabilitado.

---

## 10. Estado Atual do Projeto

- ✅ Interface de medição funcional (três estados)
- ✅ Algoritmo de detecção de CMC validado contra Apêndices B1–B8 da dissertação de referência
- ✅ Sync offline-first Pi → Cloudflare D1 funcionando (timer de 5 min)
- ✅ PCA + K-Means validado em 6 amostras comerciais
- ✅ Acesso remoto seguro (Tailscale + SSH por chave) configurado
- 🔄 Pipeline de regressão ML (`analise_ml_argilas.py`) em validação
- 🔲 Pré-filtro de sanidade para leituras duplicadas do Arduino — pendente
- 🔲 `.gitignore` e `requirements.txt` — finalização pendente

---

## 11. Roadmap / Próximos Passos

- [ ] Completar e validar os modelos de regressão (Linear Regression, Ridge, KNN, Decision Tree, Random Forest, SVR, MLP)
- [ ] Implementar filtro de sanidade para leituras seriais duplicadas do Arduino
- [ ] Resolver formato das colunas de percentual XRD (decimal vs. percentual)
- [ ] Finalizar `.gitignore` (definir nome da pasta de imagens) e `requirements.txt`
- [ ] Decidir: orientador usa conta Tailscale compartilhada ou chave própria autorizada no Pi
- [ ] Gerar versão em texto plano/PDF do relatório para o campo 1.2 do SIGAA (não aceita tabelas/figuras/equações)

---

## 12. Changelog

| Data | Mudança |
|---|---|
| 20/09/2026 | Criação da documentação inicial, estruturada a partir do estado conhecido do projeto |

> Ao fazer mudanças relevantes no código, adicione uma linha aqui com data e resumo da mudança.

---

## 13. Glossário

- **CTC / CEC**: Capacidade de Troca Catiônica (Cation Exchange Capacity)
- **CMC**: Concentração Micelar Crítica — ponto de viragem detectado na titulação condutimétrica
- **SCADA**: Supervisory Control and Data Acquisition — estilo de interface usado, com foco em monitoramento/controle em tempo real
- **PIBIC**: Programa Institucional de Bolsas de Iniciação Científica