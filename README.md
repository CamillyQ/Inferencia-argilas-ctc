# Inferência e Classificação de Argilas (CTC)

> **Projeto de Iniciação Científica:** *Técnicas computacionais e ferramentas para classificação e inferência de propriedades de argilas com aprendizado de máquina, banco de dados e interface de usuário.*

---

## Sobre o Projeto

Este sistema foi desenvolvido para automação, aquisição e processamento de ensaios de titulação condutimétrica. Ele realiza:
* **Aquisição contínua:** Coleta de dados via comunicação serial (Arduino).
* **Processamento de CMC:** Identificação automática da Concentração Micelar Crítica.
* **Cálculo da CTC:** Determinação da Capacidade de Troca Catiônica da amostra.
* **Classificação:** Inferência do tipo de mineral de argila (ex: Caulinita, Ilita, Esmectita/Bentonita).
* **Exportação:** Geração de relatórios e exportação dos dados brutos em formato CSV.

---

## Pré-requisitos

Antes de iniciar, certifique-se de ter os seguintes recursos instalados no computador:
* [Python 3.x](https://www.python.org/downloads/)
* [Git](https://git-scm.com/) (ou GitHub Desktop)

## DEVELOPMENT MODE


* Para rodar este programa no seu computador, siga os passos abaixo:


* Etapa 1  - Clone o repositório usando git bash ou github desktop
* Etapa 2 - Abra o terminal (em uma IDE ou no próprio SO) e navegue até a pasta do projeto
* Etapa 3 - Crie um ambiente virtual na pasta do projeto seguindo estes passos:

* ------Windows------
* 1 - Digite python -m venv venv
* 2 - Ative com venv/Scripts/Activate.bat (para o prompt de comando) ou /Activate.ps1 (para powershell)

* -------Linux-------

* 1 - Digite python -m venv venv
* 2 - Digite source venv/bin/activate

* Etapa 4 - Instale os pacotes necessários com o comando pip install -r requirements.txt

* Etapa 5 - Navegue até /screen e execute python main.py
