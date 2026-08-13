from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDoubleSpinBox, QMessageBox
from PySide6.QtCore import Slot, Qt, QTimer
from PySide6.QtGui import QFont

from components import SCADAButton

HEX_BG          = "#F5F5F3"
HEX_SURFACE     = "#FFFFFF"
HEX_BORDER      = "#D1D1CD"
HEX_TEXT        = "#212121"
HEX_TEXT_MUTED  = "#6B6B6B"
HEX_ACCENT      = "#0288D1"


class CalibracaoDialog(QDialog):

    def __init__(self, arduino_service, parent=None):
        super().__init__(parent)
        self.arduino = arduino_service
        self.calibracao_em_andamento = False

        self.setWindowTitle("Calibração do Sensor")
        self.setModal(True)
        self.setFixedSize(350, 360)
        self.setStyleSheet(f"background-color: {HEX_BG};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        self.label = QLabel(
            "1. Coloque o sensor na solução padrão.\n"
            "2. Clique em 'Iniciar' para começar."
        )
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Sans-Serif", 10))
        self.label.setStyleSheet(f"color: {HEX_TEXT};")
        layout.addWidget(self.label)

        rotulo_ao_vivo = QLabel("LEITURA ATUAL DO SENSOR:")
        rotulo_ao_vivo.setFont(QFont("Sans-Serif", 8, QFont.Bold))
        rotulo_ao_vivo.setStyleSheet(f"color: {HEX_TEXT_MUTED};")
        layout.addWidget(rotulo_ao_vivo)

        self.lbl_leitura_ao_vivo = QLabel("-- ppm")
        self.lbl_leitura_ao_vivo.setFont(QFont("Sans-Serif", 18, QFont.Bold))
        self.lbl_leitura_ao_vivo.setAlignment(Qt.AlignCenter)
        self.lbl_leitura_ao_vivo.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; "
            f"border-radius: 6px; padding: 6px; color: {HEX_ACCENT};"
        )
        layout.addWidget(self.lbl_leitura_ao_vivo)

        self.btn_iniciar = SCADAButton("▶ Iniciar Calibração", is_primary=True)
        self.btn_iniciar.clicked.connect(self.iniciar_processo)
        layout.addWidget(self.btn_iniciar)

        rotulo_valor = QLabel("VALOR DA SOLUÇÃO PADRÃO (ppm)")
        rotulo_valor.setFont(QFont("Sans-Serif", 8, QFont.Bold))
        rotulo_valor.setStyleSheet(f"color: {HEX_TEXT_MUTED};")
        rotulo_valor.setVisible(False)
        self.rotulo_valor = rotulo_valor
        layout.addWidget(rotulo_valor)

        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setDecimals(1)
        self.spin_valor.setRange(0.0, 100000.0)
        self.spin_valor.setSuffix(" ppm")
        self.spin_valor.setValue(707.0)
        self.spin_valor.setAlignment(Qt.AlignCenter)
        self.spin_valor.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; "
            "border-radius: 4px; padding: 6px; font-size: 16px;"
        )
        self.spin_valor.setMinimumHeight(40)
        self.spin_valor.setVisible(False)
        layout.addWidget(self.spin_valor)

        self.btn_confirmar = SCADAButton("✓ Confirmar Valor", is_primary=True)
        self.btn_confirmar.setVisible(False)
        self.btn_confirmar.clicked.connect(self.confirmar_valor)
        layout.addWidget(self.btn_confirmar)

        self.btn_cancelar = SCADAButton("✕ Cancelar", is_primary=False)
        self.btn_cancelar.clicked.connect(self._on_cancelar_clicado)
        layout.addWidget(self.btn_cancelar)


        self.timer_ao_vivo = QTimer(self)
        self.timer_ao_vivo.timeout.connect(self._atualizar_leitura_ao_vivo)
        self.timer_ao_vivo.start(100)

    @Slot()
    def _atualizar_leitura_ao_vivo(self):
        """Lê os dados da serial e atualiza o display de ppm ao vivo."""
        if hasattr(self.arduino, "conectado") and not self.arduino.conectado:
            self.lbl_leitura_ao_vivo.setText("Offline")
            return

        self.arduino.ler()

        valor_ppm = self.arduino.ppm
        if valor_ppm is not None:
            self.lbl_leitura_ao_vivo.setText(f"{valor_ppm:.1f} ppm")
        else:
            self.lbl_leitura_ao_vivo.setText("Aguardando...")

    @Slot()
    def iniciar_processo(self):
        if self.arduino.enviar_comando_calibracao("ENTER"):
            self.calibracao_em_andamento = True
            self.label.setText(
                "Aguarde a leitura estabilizar.\n"
                "Em seguida, confirme o valor da solução:"
            )
            self.btn_iniciar.setVisible(False)
            self.rotulo_valor.setVisible(True)
            self.spin_valor.setVisible(True)
            self.btn_confirmar.setVisible(True)
        else:
            QMessageBox.critical(self, "Erro", "Não foi possível conectar ao Arduino.")

    @Slot()
    def confirmar_valor(self):
        valor = self.spin_valor.value()

        if self.arduino.enviar_comando_calibracao(f"CAL:{valor:.1f}"):
            self.arduino.enviar_comando_calibracao("EXIT")
            self.calibracao_em_andamento = False
            self.timer_ao_vivo.stop()
            QMessageBox.information(self, "Sucesso", "Calibração efetuada!")
            self.accept()
        else:
            QMessageBox.warning(self, "Erro", "Falha ao enviar valor. Tente novamente.")

    @Slot()
    def _on_cancelar_clicado(self):
        self._sair_do_modo_calibracao()
        self.reject()

    def _sair_do_modo_calibracao(self):
        self.timer_ao_vivo.stop()
        if self.calibracao_em_andamento:
            self.arduino.enviar_comando_calibracao("EXIT")
            self.calibracao_em_andamento = False

    def closeEvent(self, event):
        self._sair_do_modo_calibracao()
        event.accept()