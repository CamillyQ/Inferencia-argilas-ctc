import sys
import os
import csv
import pandas as pd
from datetime import datetime
from time import perf_counter
from analises.modelos_rpi.inferencia_rpi import PredictorRPi5
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import QApplication, QMainWindow, QStackedWidget, QMessageBox

from services.arduino import ArduinoService
from services.analises import (
    calcular_concentracao_molar,
    detectar_cmc_joao_original,
    cmc_para_ctc,
    classificar_tipo_argila,
)
from interface.home import HomeScreen
from interface.medicao import MedicaoScreen
from interface.historico import TelaHistorico
from interface.configuracao import CalibracaoDialog


def configurar_ambiente_rpi():
    os.environ["QT_QPA_EGLFS_HIDECURSOR"] = "1"
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"


class ScadaApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("SCADA - Estação de Medição")
        self.setFixedSize(800, 480)

        # Estado do ensaio em andamento
        self.coletando = False
        self.pontos = []                 # (tempo, condutividade) -- gráfico ao vivo
        self.titulacao = []              # [{'volume_acumulado_mL', 'concentracao_molar', 'condutividade'}]
        self.volume_acumulado_mL = 0.0
        self.massa_amostra_g = None      # definida pelo usuário no Estado Inicial
        self.inicio = 0.0

        self.arduino = ArduinoService()

        self.screen_manager = QStackedWidget()
        self.setCentralWidget(self.screen_manager)

        self.medicao_screen = MedicaoScreen(app_instance=self)
        self.home_screen = HomeScreen(app_instance=self)
        self.historico_screen = TelaHistorico(app_instance=self)

        self.screen_manager.addWidget(self.home_screen)
        self.screen_manager.addWidget(self.medicao_screen)
        self.screen_manager.addWidget(self.historico_screen)
        self.predictor = PredictorRPi5(caminho_pasta_modelos="analises/modelos_rpi")
        self.setup_timers()

        if not self.arduino.conectado:
            QTimer.singleShot(300, self._notificar_arduino_ausente)

    def _notificar_arduino_ausente(self):
        QMessageBox.warning(
            self,
            "Arduino Não Conectado",
            "Nenhum Arduino foi detectado na porta USB.\n\n"
            "O sistema abrirá normalmente em modo de visualização, "
            "mas as leituras e ensaios estarão desabilitados."
        )

    def setup_timers(self):
        self.timer_tick = QTimer(self)
        self.timer_tick.timeout.connect(self._tick)
        self.timer_tick.start(1000)

        self.timer_serial = QTimer(self)
        self.timer_serial.timeout.connect(self.receber_dados)
        self.timer_serial.start(50)

        self._tick()

        # ── Salvamento de Dados ─────────────────────────────────────────────
    def salvar_dados_csv(self, resultado, ctc_final, tipo_argila):
        """Gera um arquivo CSV com o resumo do ensaio e os pontos de titulação."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        nome_arquivo = f"ensaio_{timestamp}.csv"

        try:
            with open(nome_arquivo, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")

                # Metadados do Ensaio
                writer.writerow(["--- RESUMO DO ENSAIO ---"])
                writer.writerow(["Data/Hora", datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
                writer.writerow(["Massa da Amostra (g)", self.massa_amostra_g])
                writer.writerow(["CMC (mol/L)", resultado.get("cmc", "")])
                writer.writerow(["Volume no Corte (mL)", resultado.get("volume_cmc_mL", "")])
                writer.writerow(["CTC (cmolc/kg)", ctc_final])
                writer.writerow(["Tipo de Argila", tipo_argila])
                writer.writerow([])

                # Dados da Titulação
                writer.writerow(["--- DADOS DA TITULAÇÃO ---"])
                writer.writerow(["Volume Acumulado (mL)", "Concentração Molar (mol/L)", "Condutividade (uS/cm)"])

                for linha in self.titulacao:
                    writer.writerow([
                        f"{linha['volume_acumulado_mL']:.2f}",
                        f"{linha['concentracao_molar']:.6f}",
                        f"{linha['condutividade']:.2f}"
                    ])

            print(f"[EXPORTAÇÃO] Dados salvos com sucesso em: {nome_arquivo}")

        except Exception as e:
            print(f"[EXPORTAÇÃO] Erro ao salvar arquivo CSV: {e}")

    @Slot()
    def _tick(self):
        data_hora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.home_screen.clock_lbl.setText(data_hora_str)

    @Slot()
    def receber_dados(self):
        """Coleta contínua para o gráfico ao vivo -- só roda no Estado Coleta."""
        if not self.coletando:
            return

        leitura = self.arduino.ler()
        if leitura is None:
            return

        ppm, condutividade = leitura
        tempo = perf_counter() - self.inicio

        self.pontos.append((tempo, condutividade))
        total_amostras = len(self.pontos)

        self.medicao_screen.lbl_condutividade.setText(f"{condutividade:.2f} µS/cm")
        self.medicao_screen.lbl_leituras_recebidas.setText(str(total_amostras))
        self.medicao_screen.add_point(tempo, condutividade)
        print(f"PPM={leitura[0]} | CONDUTIVIDADE={leitura[1]} uS/cm")

    # ── Titulação manual (botão "Registrar Adição", só existe no Estado Coleta) ─
    @Slot(float)
    def registrar_adicao(self, volume_mL):
        if volume_mL <= 0 or not self.coletando:
            return

        self.volume_acumulado_mL += volume_mL
        concentracao_molar = calcular_concentracao_molar(self.volume_acumulado_mL)
        condutividade_atual = self.pontos[-1][1] if self.pontos else 0.0

        self.titulacao.append({
            "volume_acumulado_mL": self.volume_acumulado_mL,
            "concentracao_molar": concentracao_molar,
            "condutividade": condutividade_atual,
        })

        self.medicao_screen.atualizar_volume_total(self.volume_acumulado_mL)
        print(
            f"[TITULAÇÃO] Volume total: {self.volume_acumulado_mL:.2f} mL | "
            f"Concentração: {concentracao_molar:.6f} mol/L | "
            f"Condutividade: {condutividade_atual:.2f} µS/cm"
        )

    @Slot()
    def detectar_cmc(self):
        if self.massa_amostra_g is None:
            print("[PROCESSAMENTO] Massa da amostra não definida.")
            return

        try:
            resultado = detectar_cmc_joao_original(self.titulacao)

            ctc_final = cmc_para_ctc(
                volume_no_corte_mL=resultado["volume_cmc_mL"],
                massa_amostra_g=self.massa_amostra_g,
                normalidade_titulante=0.01,
            )

            df_input = pd.DataFrame([{'ctc_consenso_meq_100g': ctc_final}])

            predicoes = self.predictor.prever(df_input)
            df_granulo = predicoes["granulometria"]
            df_fases = predicoes["fases_minerais"]

            # Atualizações da interface gráfica
            self.medicao_screen.plotar_resultado_cmc(resultado)
            self.medicao_screen.atualizar_resultado(
                resultado["cmc"], ctc_final, df_granulo, df_fases
            )

            # Salvamento consolidado no CSV
            self.salvar_dados_csv(resultado, ctc_final, df_granulo, df_fases)

        except Exception as erro:
            print(f"[PROCESSAMENTO] Erro ao processar CMC/CTC/Inferência: {erro}")
            QMessageBox.critical(
                self, "Erro ao processar",
                f"Não foi possível calcular ou prever os dados desta amostra.\n\nDetalhe: {erro}"
            )
            return

    # ── Transições de estado ────────────────────────────────────────────
    @Slot(float)
    def iniciar_teste(self, massa_amostra_g):
        """Estado Inicial -> Estado Coleta (aquisição real começa aqui)."""
        if not self.arduino.conectado:
            QMessageBox.critical(
                self,
                "Erro de Conexão",
                "Não é possível iniciar o teste sem um Arduino conectado."
            )
            return
        self.massa_amostra_g = massa_amostra_g
        self.coletando = True
        self.pontos = []
        self.titulacao = []
        self.volume_acumulado_mL = 0.0
        self.inicio = perf_counter()

        self.arduino.limpar_buffer()
        self.arduino.enviar("START")

        self.home_screen.status_pill.set_status("COLETANDO", "#B78103")
        self.medicao_screen.reiniciar_graficos()
        self.medicao_screen.mostrar_estado_coleta()

    @Slot()
    def parar_teste(self):
        """Estado Coleta -> Estado Finalizado."""
        self.coletando = False
        self.arduino.enviar("STOP")
        self.home_screen.status_pill.set_status("PARADO", "#6B6B6B")
        self.medicao_screen.mostrar_estado_finalizado()

    @Slot()
    def novo_ensaio(self):
        """Estado Finalizado -> Estado Inicial (para uma nova amostra)."""
        self.massa_amostra_g = None
        self.pontos = []
        self.titulacao = []
        self.volume_acumulado_mL = 0.0
        self.medicao_screen.mostrar_estado_inicial()

    # ── Navegação do Sistema SCADA ───────────────────────────────────────
    @Slot()
    def acao_iniciar_medicao(self):
        self.screen_manager.setCurrentWidget(self.medicao_screen)
        self.medicao_screen.mostrar_estado_inicial()

    @Slot()
    def acao_historico(self):
        self.screen_manager.setCurrentWidget(self.historico_screen)
        print("[NAVEGAÇÃO] Mudando para tela de Histórico")

    @Slot()
    def acao_configuracoes(self):
        """Abre o diálogo de calibração (CalibracaoDialog cuida do fluxo
        completo: ENTER -> CAL:valor -> EXIT -- ver interface/configuracao.py)."""
        print("[NAVEGAÇÃO] Abrindo tela de Calibração")
        dialog = CalibracaoDialog(self.arduino, self)
        dialog.exec()

    @Slot()
    #definir aqui o qlialog
    def voltar_home(self):
        self.screen_manager.setCurrentWidget(self.home_screen)

    def closeEvent(self, event):
        if hasattr(self, "arduino") and self.arduino:
            print("[SHUTDOWN] Fechando conexão serial de forma segura...")
            self.arduino.fechar()
        event.accept()


if __name__ == "__main__":
    configurar_ambiente_rpi()
    app = QApplication(sys.argv)
    scada_sistema = ScadaApp()
    scada_sistema.show()
    sys.exit(app.exec())