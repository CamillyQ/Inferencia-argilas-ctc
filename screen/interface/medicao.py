import numpy as np
import os
import pandas as pd
from datetime import datetime
from PySide6.QtCore import Qt, Slot, QRectF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QStackedWidget, QDoubleSpinBox,
    QFileDialog, QMessageBox, QScrollArea, QLineEdit
)
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QPdfWriter, QPageSize
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QScatterSeries

from services.analises import detectar_cmc_joao_original, cmc_para_ctc
from services.banco_local import salvar_ensaio

HEX_BG           = "#F5F5F3"
HEX_SURFACE      = "#FFFFFF"
HEX_BORDER       = "#D1D1CD"
HEX_TEXT         = "#212121"
HEX_TEXT_MUTED   = "#6B6B6B"
HEX_ACTION       = "#2E5284"
HEX_ALARM        = "#C62828"
HEX_OK           = "#2E7D32"
HEX_SURFACE_PRES = "#2E5284"


class MedicaoScreen(QWidget):

    # Mesma ordem em que as páginas são adicionadas ao stack em init_ui()
    ESTADO_INICIAL     = 0
    ESTADO_COLETA      = 1
    ESTADO_FINALIZADO  = 2

    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app_app = app_instance
        self.massa_amostra_g = None
        self.nome_amostra = None
        self._maior_trecho_cmc_visto = 0
        self._ultimo_cmc = None
        self._ultimo_ctc = None
        self._ensaio_salvo = False
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header_frame = QFrame()
        header_frame.setFixedHeight(48)
        header_frame.setStyleSheet("background-color: #202225; border: none;")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title_lbl = QLabel("MEDIÇÃO DE CTC")
        title_lbl.setFont(QFont("Sans-Serif", 11, QFont.Bold))
        title_lbl.setStyleSheet("color: #FFFFFF;")

        self.status_arduino = QLabel("ARDUINO CONECTADO")
        self.status_arduino.setFont(QFont("Courier New", 10, QFont.Bold))
        self.status_arduino.setStyleSheet(f"color: {HEX_OK};")
        self.status_arduino.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        header_layout.addWidget(title_lbl)
        header_layout.addWidget(self.status_arduino)
        main_layout.addWidget(header_frame)

        self.stack_estados = QStackedWidget()
        self.stack_estados.addWidget(self._build_pagina_inicial())     # 0
        self.stack_estados.addWidget(self._build_pagina_coleta())      # 1
        self.stack_estados.addWidget(self._build_pagina_finalizado())  # 2
        main_layout.addWidget(self.stack_estados, stretch=1)

        footer_layout = QHBoxLayout()
        footer_layout.setContentsMargins(12, 0, 12, 12)
        footer_layout.setSpacing(8)

        self.btn_parar = QPushButton("Parar")
        self.btn_processar = QPushButton("Processar")
        self.btn_salvar = QPushButton("Salvar")
        self.btn_voltar = QPushButton("Voltar")
        self.btn_iniciar = QPushButton("Iniciar")

        for btn in (self.btn_iniciar, self.btn_parar, self.btn_processar, self.btn_salvar, self.btn_voltar):
            btn.setFixedHeight(54)
            btn.setFont(QFont("Sans-Serif", 10, QFont.Bold))
            btn.setStyleSheet(self.get_button_style())
            footer_layout.addWidget(btn)

        # "Parar" agora também dispara o processamento (CMC -> CTC -> modelo)
        self.btn_parar.clicked.connect(self._parar_e_processar)
        self.btn_processar.clicked.connect(self.processar)
        self.btn_voltar.clicked.connect(self._on_voltar_clicado)
        self.btn_iniciar.clicked.connect(self._on_iniciar_clicado)
        self.btn_salvar.clicked.connect(self.exportar_relatorio)

        main_layout.addLayout(footer_layout)
        self.setStyleSheet(f"background-color: {HEX_BG};")

        self.mostrar_estado_inicial()

    # ────────────────────────────────────────────────────────────────
    # Páginas
    # ────────────────────────────────────────────────────────────────
    def _build_pagina_inicial(self):
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

        rotulo_nome = QLabel("NOME/IDENTIFICAÇÃO DA AMOSTRA")
        rotulo_nome.setFont(QFont("Sans-Serif", 9, QFont.Bold))
        rotulo_nome.setStyleSheet(f"color: {HEX_TEXT_MUTED};")
        rotulo_nome.setAlignment(Qt.AlignCenter)

        self.campo_nome_amostra = QLineEdit()
        self.campo_nome_amostra.setPlaceholderText("ex: Verde Lodo, Brasgel...")
        self.campo_nome_amostra.setFixedSize(300, 48)
        self.campo_nome_amostra.setAlignment(Qt.AlignCenter)
        self.campo_nome_amostra.setStyleSheet(f"""
            QLineEdit {{
                background-color: {HEX_SURFACE};
                border: 1px solid {HEX_BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 16px;
            }}
        """)

        layout.addWidget(rotulo_nome, alignment=Qt.AlignCenter)
        layout.addWidget(self.campo_nome_amostra, alignment=Qt.AlignCenter)
        layout.addSpacing(12)

        titulo = QLabel("Nova Medição de CTC")
        titulo.setFont(QFont("Sans-Serif", 16, QFont.Bold))
        titulo.setStyleSheet(f"color: {HEX_TEXT};")
        titulo.setAlignment(Qt.AlignCenter)

        subtitulo = QLabel("Informe a massa seca da amostra de argila antes de iniciar")
        subtitulo.setFont(QFont("Sans-Serif", 10))
        subtitulo.setStyleSheet(f"color: {HEX_TEXT_MUTED};")
        subtitulo.setAlignment(Qt.AlignCenter)

        rotulo_massa = QLabel("MASSA DA AMOSTRA (g)")
        rotulo_massa.setFont(QFont("Sans-Serif", 9, QFont.Bold))
        rotulo_massa.setStyleSheet(f"color: {HEX_TEXT_MUTED};")
        rotulo_massa.setAlignment(Qt.AlignCenter)

        self.spin_massa_amostra = QDoubleSpinBox()
        self.spin_massa_amostra.setDecimals(1)
        self.spin_massa_amostra.setRange(0.1, 10)
        self.spin_massa_amostra.setSingleStep(0.1)
        self.spin_massa_amostra.setSuffix(" g")
        self.spin_massa_amostra.setFixedSize(300, 60)
        self.spin_massa_amostra.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {HEX_SURFACE};
                border: 1px solid {HEX_BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 20px;
            }}
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {{
                width: 40px;
            }}
        """)
        self.spin_massa_amostra.setAlignment(Qt.AlignCenter)

        btn_iniciar_coleta = QPushButton("Iniciar Coleta")
        btn_iniciar_coleta.setFixedSize(220, 56)
        btn_iniciar_coleta.setFont(QFont("Sans-Serif", 11, QFont.Bold))
        btn_iniciar_coleta.setStyleSheet(self.get_button_style(is_action=True))
        btn_iniciar_coleta.clicked.connect(self._on_iniciar_coleta_clicado)

        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(20)
        layout.addWidget(rotulo_massa, alignment=Qt.AlignCenter)
        layout.addWidget(self.spin_massa_amostra, alignment=Qt.AlignCenter)
        layout.addSpacing(20)
        layout.addWidget(btn_iniciar_coleta, alignment=Qt.AlignCenter)
        return pagina

    def _build_pagina_coleta(self):
        pagina = QWidget()
        body_layout = QHBoxLayout(pagina)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(8)

        self.card_cond = self.create_numeric_card("CONDUTIVIDADE", "0.00 µS/cm", "26px")
        self.card_leituras = self.create_numeric_card("LEITURAS RECEBIDAS", "0", "22px")
        self.card_volume = self.create_numeric_card("VOLUME TOTAL ADICIONADO", "0.00 mL", "22px")

        left_panel.addWidget(self.card_cond)
        left_panel.addWidget(self.card_leituras)
        left_panel.addWidget(self.card_volume)

        titulacao_frame = QFrame()
        titulacao_frame.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; border-radius: 4px;"
        )
        titulacao_layout = QVBoxLayout(titulacao_frame)
        titulacao_layout.setContentsMargins(8, 6, 8, 6)
        titulacao_layout.setSpacing(4)

        titulacao_titulo = QLabel("VOLUME DESTA ADIÇÃO (mL)")
        titulacao_titulo.setFont(QFont("Sans-Serif", 8, QFont.Bold))
        titulacao_titulo.setStyleSheet(f"color: {HEX_TEXT_MUTED}; border: none;")

        self.spin_volume_adicao = QDoubleSpinBox()
        self.spin_volume_adicao.setDecimals(2)
        self.spin_volume_adicao.setRange(0.01, 100.0)
        self.spin_volume_adicao.setValue(2.00)
        self.spin_volume_adicao.setSingleStep(0.5)
        self.spin_volume_adicao.setStyleSheet(f"""
            QDoubleSpinBox {{
                background-color: {HEX_BG};
                border: 1px solid {HEX_BORDER};
                border-radius: 6px;
                padding: 8px;
                font-size: 20px;
            }}
            QDoubleSpinBox::up-button,
            QDoubleSpinBox::down-button {{
                width: 40px;
            }}
        """)

        btn_registrar_adicao = QPushButton("Registrar Adição")
        btn_registrar_adicao.setFixedHeight(60)
        btn_registrar_adicao.setFont(QFont("Sans-Serif", 9, QFont.Bold))
        btn_registrar_adicao.setStyleSheet(self.get_button_style(is_action=True))
        btn_registrar_adicao.clicked.connect(self._on_registrar_adicao)

        titulacao_layout.addWidget(titulacao_titulo)
        titulacao_layout.addWidget(self.spin_volume_adicao)
        titulacao_layout.addWidget(btn_registrar_adicao)

        left_panel.addWidget(titulacao_frame)
        left_panel.addStretch(1)

        chart_frame = QFrame()
        chart_frame.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; border-radius: 4px;"
        )
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(4, 4, 4, 4)

        self.series = QLineSeries()
        self.chart_tempo = QChart()
        self.chart_tempo.addSeries(self.series)
        self.chart_tempo.legend().hide()
        self.chart_tempo.setTitle("Gráfico Condutividade × Tempo")
        self.chart_tempo.setTitleFont(QFont("Sans-Serif", 10, QFont.Bold))
        self.chart_tempo.setBackgroundVisible(False)

        self.axis_x = QValueAxis()
        self.axis_x.setTitleText("Tempo (s)")
        self.axis_x.setLabelFormat("%.1f")
        self.chart_tempo.addAxis(self.axis_x, Qt.AlignBottom)
        self.series.attachAxis(self.axis_x)

        self.axis_y = QValueAxis()
        self.axis_y.setTitleText("Condutividade (µS/cm)")
        self.axis_y.setLabelFormat("%.2f")
        self.chart_tempo.addAxis(self.axis_y, Qt.AlignLeft)
        self.series.attachAxis(self.axis_y)

        chart_view_tempo = QChartView(self.chart_tempo)
        chart_view_tempo.setRenderHint(QPainter.Antialiasing)
        chart_layout.addWidget(chart_view_tempo)

        body_layout.addLayout(left_panel, stretch=35)
        body_layout.addWidget(chart_frame, stretch=65)
        return pagina

    def _build_pagina_finalizado(self):
        pagina = QWidget()
        body_layout = QHBoxLayout(pagina)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)

        # painel esquerdo (conteúdo que vai rolar)
        left_content = QWidget()
        left_panel = QVBoxLayout(left_content)
        left_panel.setContentsMargins(0, 0, 0, 0)
        left_panel.setSpacing(10)

        self.card_cmc = self.create_numeric_card("CMC", "-- (aperte Processar)", "16px")
        self.card_ctc = self.create_numeric_card("CTC", "-- mEq/100g", "16px")
        self.card_d10 = self.create_numeric_card("d10 (μm)", "----", "16px", attr_name="d10")
        self.card_d50 = self.create_numeric_card("d50 (μm)", "----", "16px", attr_name="d50")
        self.card_d90 = self.create_numeric_card("d90 (μm)", "----", "16px", attr_name="d90")
        self.card_diametroMedio = self.create_numeric_card("diametro médio (μm)", "----", "16px", attr_name="diametro_medio")
        self.card_mont = self.create_numeric_card("Montmorilonita (%)", "----", "16px", attr_name="montmorilonita")
        self.card_cau  = self.create_numeric_card("Caulinita (%)", "----", "16px", attr_name="caulinita")
        self.card_qua  = self.create_numeric_card("Quartzo (%)", "----", "16px", attr_name="quartzo")
        self.card_non  = self.create_numeric_card("Nontronita (%)", "----", "16px", attr_name="nontronita")
        self.card_cris = self.create_numeric_card("Cristobalita (%)", "----", "16px", attr_name="cristobalita")

        layout_d10_d50 = QHBoxLayout()
        layout_d10_d50.setContentsMargins(0, 0, 0, 0)
        layout_d10_d50.setSpacing(10)
        layout_d10_d50.addWidget(self.card_d10)
        layout_d10_d50.addWidget(self.card_d50)

        layout_d90_dm = QHBoxLayout()
        layout_d90_dm.setContentsMargins(0, 0, 0, 0)
        layout_d90_dm.setSpacing(10)
        layout_d90_dm.addWidget(self.card_d90)
        layout_d90_dm.addWidget(self.card_diametroMedio)

        left_panel.addWidget(self.card_cmc)
        left_panel.addWidget(self.card_ctc)
        left_panel.addLayout(layout_d10_d50)
        left_panel.addLayout(layout_d90_dm)
        left_panel.addWidget(self.card_mont)
        left_panel.addWidget(self.card_cau)
        left_panel.addWidget(self.card_qua)
        left_panel.addWidget(self.card_non)
        left_panel.addWidget(self.card_cris)
        left_panel.addStretch(1)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setWidget(left_content)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setProperty("touchScroll", True)

        # gráfico (fixo, fora do scroll)
        chart_frame = QFrame()
        chart_frame.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; border-radius: 4px;"
        )
        chart_layout = QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(4, 4, 4, 4)

        self.series_titulacao_todos = QScatterSeries()
        self.series_titulacao_todos.setName("Dados")
        self.series_titulacao_todos.setMarkerSize(10)
        self.series_titulacao_todos.setColor(QColor(HEX_ACTION))

        self.series_titulacao_linear = QScatterSeries()
        self.series_titulacao_linear.setName("Trecho Linear")
        self.series_titulacao_linear.setMarkerSize(10)
        self.series_titulacao_linear.setColor(QColor(HEX_OK))

        self.series_ajuste_rls = QLineSeries()
        self.series_ajuste_rls.setName("Ajuste RLS")
        pen = QPen(QColor(HEX_ALARM))
        pen.setStyle(Qt.DashLine)
        pen.setWidth(2)
        self.series_ajuste_rls.setPen(pen)

        self.chart_molar = QChart()
        self.chart_molar.addSeries(self.series_titulacao_todos)
        self.chart_molar.addSeries(self.series_titulacao_linear)
        self.chart_molar.addSeries(self.series_ajuste_rls)
        self.chart_molar.legend().setVisible(True)
        self.chart_molar.setTitle("CMC: Condutividade Molar × Concentração Molar")
        self.chart_molar.setTitleFont(QFont("Sans-Serif", 10, QFont.Bold))
        self.chart_molar.setBackgroundVisible(False)

        self.axis_molar_x = QValueAxis()
        self.axis_molar_x.setTitleText("Concentração molar (mol/L)")
        self.axis_molar_x.setLabelFormat("%.5f")
        self.axis_molar_x.setRange(0, 1)
        self.chart_molar.addAxis(self.axis_molar_x, Qt.AlignBottom)

        self.axis_molar_y = QValueAxis()
        self.axis_molar_y.setTitleText("Condutividade molar Ω (S·cm²/mol)")
        self.axis_molar_y.setLabelFormat("%.1f")
        self.axis_molar_y.setRange(0, 1)
        self.chart_molar.addAxis(self.axis_molar_y, Qt.AlignLeft)

        for serie in (self.series_titulacao_todos, self.series_titulacao_linear, self.series_ajuste_rls):
            serie.attachAxis(self.axis_molar_x)
            serie.attachAxis(self.axis_molar_y)

        chart_view_molar = QChartView(self.chart_molar)
        chart_view_molar.setRenderHint(QPainter.Antialiasing)
        self.chart_view_molar = chart_view_molar
        chart_layout.addWidget(chart_view_molar)

        body_layout.addWidget(left_scroll, stretch=35)
        body_layout.addWidget(chart_frame, stretch=65)
        return pagina

    # ────────────────────────────────────────────────────────────────
    # Ações dos botões
    # ────────────────────────────────────────────────────────────────
    def _on_iniciar_coleta_clicado(self):
        """Salva nome e massa e leva para a tela de coleta (modo 'aguardando').
        A aquisição real só começa quando o botão 'Iniciar' do rodapé é pressionado."""
        self.massa_amostra_g = self.spin_massa_amostra.value()
        self.nome_amostra = self.campo_nome_amostra.text().strip() or None
        self.mostrar_estado_coleta_aguardando()

    def _on_iniciar_clicado(self):
        self.app_app.iniciar_teste(self.massa_amostra_g)

    def _parar_e_processar(self):
        """Para a coleta e roda CMC -> CTC -> modelo -> salvar.
        Se o CMC ainda não for detectável, avisa antes de encerrar."""
        try:
            detectar_cmc_joao_original(self.app_app.titulacao)
        except Exception as erro:
            resposta = QMessageBox.question(
                self,
                "CMC não detectado",
                "Ainda não foi possível detectar o CMC com os pontos registrados.\n\n"
                f"Detalhe: {erro}\n\n"
                "Se parar agora, não será possível continuar esta titulação.\n"
                "Deseja parar mesmo assim?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                return 
            self.app_app.parar_teste() 
            return

        self.app_app.parar_teste()
        self.processar()

    def _on_voltar_clicado(self):
        # Na tela inicial não tem nada em andamento -- sai direto
        if self.stack_estados.currentIndex() == self.ESTADO_INICIAL:
            self.app_app.voltar_home()
            return

        resposta = QMessageBox.question(
            self,
            "Descartar medição?",
            "Você tem uma medição em andamento (ou recém-concluída) que ainda "
            "não foi salva/exportada.\n\n"
            "Se voltar agora, todos os dados desta medição serão perdidos.\n\n"
            "Deseja realmente descartar e voltar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        # Só para o Arduino (sem processar/salvar nada, pois a medição está sendo descartada)
        if self.app_app.coletando:
            self.app_app.parar_teste()

        self.app_app.novo_ensaio()
        self.app_app.voltar_home()

    def _on_registrar_adicao(self):
        volume_mL = self.spin_volume_adicao.value()
        self.app_app.registrar_adicao(volume_mL)
        self._verificar_cmc_tempo_real()

    def _verificar_cmc_tempo_real(self):
        """
        A cada adição registrada, roda a detecção de CMC. Quando acha um trecho
        linear MAIOR que o último já avisado, pergunta se deve parar a coleta.
        Se o usuário responder 'Sim', para a coleta E já processa (modelo roda).
        Se responder 'Não', só volta a perguntar quando aparecer um trecho ainda maior.
        """
        if self.massa_amostra_g is None:
            return
        try:
            resultado = detectar_cmc_joao_original(self.app_app.titulacao)
        except ValueError:
            # Ainda não há pontos suficientes para um trecho linear: esperado
            return
        except Exception as erro:
            print(f"[CMC tempo real] erro inesperado na detecção: {erro}")
            return

        tamanho_trecho = len(resultado["x_trecho"])
        if tamanho_trecho <= self._maior_trecho_cmc_visto:
            return

        self._maior_trecho_cmc_visto = tamanho_trecho

        cmc = resultado["cmc"]
        volume_cmc = resultado["volume_cmc_mL"]
        resposta = QMessageBox.question(
            self,
            "Ponto de CMC encontrado",
            f"Um trecho linear maior foi identificado na curva.\n\n"
            f"Concentração no ponto de corte: {cmc:.6f} mol/L\n"
            f"Volume acumulado no ponto de corte: {volume_cmc:.2f} mL\n"
            f"Pontos no trecho linear: {tamanho_trecho}\n\n"
            "Deseja parar a coleta e processar agora?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,  # padrão seguro -- nunca para sozinho
        )
        if resposta == QMessageBox.Yes:
            self._parar_e_processar()

    def processar(self):
        if self.massa_amostra_g is None:
            print("[PROCESSAMENTO] Massa da amostra não definida.")
            return
        try:
            resultado = detectar_cmc_joao_original(self.app_app.titulacao)
            ctc_final = cmc_para_ctc(
                volume_no_corte_mL=resultado["volume_cmc_mL"],
                massa_amostra_g=self.massa_amostra_g,
                normalidade_titulante=0.01,
            )

            # O modelo foi treinado só com CTC
            df_input = pd.DataFrame([{'ctc_consenso_meq_100g': ctc_final}])
            predicoes = self.app_app.predictor.prever(df_input)
            df_granulo = predicoes["granulometria"]
            df_fases = predicoes["fases_minerais"]

            self.plotar_resultado_cmc(resultado)
            self.atualizar_resultado(resultado["cmc"], ctc_final, df_granulo, df_fases)
            if not self._ensaio_salvo:
                self.app_app.salvar_dados_csv(resultado, ctc_final, df_granulo, df_fases)
                salvar_ensaio(
                    resultado={**resultado, "massa_amostra_g": self.massa_amostra_g},
                    ctc_final=ctc_final,
                    df_granulo=df_granulo,
                    df_fases=df_fases,
                    amostra_nome=self.nome_amostra,
                )
                self._ensaio_salvo = True

        except Exception as erro:
            print(f"[PROCESSAMENTO] Erro ao processar CMC/CTC/Inferência: {erro}")
            QMessageBox.critical(
                self, "Erro ao processar",
                f"Não foi possível calcular ou prever os dados desta amostra.\n\nDetalhe: {erro}"
            )

    # ────────────────────────────────────────────────────────────────
    # Estados da tela
    # ────────────────────────────────────────────────────────────────
    def mostrar_estado_inicial(self):
        self.stack_estados.setCurrentIndex(self.ESTADO_INICIAL)
        self.btn_parar.setEnabled(False)
        self.btn_processar.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.btn_iniciar.setEnabled(False)

    def mostrar_estado_coleta_aguardando(self):
        """Troca pra tela de coleta, mas a aquisição ainda NÃO começou."""
        self.stack_estados.setCurrentIndex(self.ESTADO_COLETA)
        self.btn_iniciar.setEnabled(True)
        self.btn_parar.setEnabled(False)
        self.btn_processar.setEnabled(False)
        self.btn_salvar.setEnabled(False)

    def mostrar_estado_coleta(self):
        """Chamado por app_instance.iniciar_teste() -- aquisição já começou."""
        self.stack_estados.setCurrentIndex(self.ESTADO_COLETA)
        self.btn_iniciar.setEnabled(False)
        self.btn_parar.setEnabled(True)
        self.btn_processar.setEnabled(False)
        self.btn_salvar.setEnabled(False)

    def mostrar_estado_finalizado(self):
        self.stack_estados.setCurrentIndex(self.ESTADO_FINALIZADO)
        self.btn_iniciar.setEnabled(False)
        self.btn_parar.setEnabled(False)
        self.btn_processar.setEnabled(True)
        self.btn_salvar.setEnabled(True)

    # ────────────────────────────────────────────────────────────────
    # Widgets auxiliares e atualização de telas
    # ────────────────────────────────────────────────────────────────
    def create_numeric_card(self, title, initial_value, font_size, attr_name=None):
        frame = QFrame()
        frame.setStyleSheet(
            f"background-color: {HEX_SURFACE}; border: 1px solid {HEX_BORDER}; border-radius: 4px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        title_lbl = QLabel(title)
        title_lbl.setFont(QFont("Sans-Serif", 9, QFont.Bold))
        title_lbl.setStyleSheet(f"color: {HEX_TEXT_MUTED}; border: none;")

        val_lbl = QLabel(initial_value)
        val_lbl.setFont(QFont("Courier New", int(font_size.replace("px", "")), QFont.Bold))
        val_lbl.setStyleSheet(f"color: {HEX_TEXT}; border: none;")
        val_lbl.setAlignment(Qt.AlignCenter)
        val_lbl.setWordWrap(True)

        layout.addWidget(title_lbl)
        layout.addWidget(val_lbl)

        nome_attr = attr_name or title.lower().replace(' ', '_')
        setattr(self, f"lbl_{nome_attr}", val_lbl)
        return frame

    @Slot(float, float)
    def add_point(self, tempo, condutividade):
        self.series.append(tempo, condutividade)
        if self.series.count() == 1:
            self.axis_x.setRange(0, max(tempo, 1))
            self.axis_y.setRange(0, condutividade + 10)
        else:
            if tempo > self.axis_x.max():
                self.axis_x.setMax(tempo * 1.1)
            if condutividade > self.axis_y.max():
                self.axis_y.setMax(condutividade * 1.1)

    def reiniciar_graficos(self):
        self.series.clear()
        self.axis_x.setRange(0, 10)
        self.axis_y.setRange(0, 10)

        self.series_titulacao_todos.clear()
        self.series_titulacao_linear.clear()
        self.series_ajuste_rls.clear()
        self._maior_trecho_cmc_visto = 0
        self._ultimo_cmc = None
        self._ultimo_ctc = None
        self._ensaio_salvo = False


        self.lbl_volume_total_adicionado.setText("0.00 mL")
        self.lbl_leituras_recebidas.setText("0")
        self.lbl_cmc.setText("-- (aperte Processar)")
        self.lbl_ctc.setText("-- mEq/100g")
        for lbl in (
            self.lbl_d10, self.lbl_d50, self.lbl_d90, self.lbl_diametro_medio,
            self.lbl_montmorilonita, self.lbl_caulinita, self.lbl_quartzo,
            self.lbl_nontronita, self.lbl_cristobalita,
        ):
            lbl.setText("----")

    def atualizar_volume_total(self, volume_mL):
        self.lbl_volume_total_adicionado.setText(f"{volume_mL:.2f} mL")

    def plotar_resultado_cmc(self, resultado):
        """Atualiza o gráfico Condutividade Molar × Concentração Molar:
        todos os pontos, o trecho linear (verde) e a reta ajustada (tracejada)."""
        concentracoes = resultado["concentracoes"]
        omegas = resultado["omegas"]
        x_trecho = resultado["x_trecho"]
        y_trecho = resultado["y_trecho"]
        a, b = resultado["reta"]

        self.series_titulacao_todos.clear()
        self.series_titulacao_linear.clear()
        self.series_ajuste_rls.clear()

        for c, o in zip(concentracoes, omegas):
            self.series_titulacao_todos.append(float(c), float(o))

        for c, o in zip(x_trecho, y_trecho):
            self.series_titulacao_linear.append(float(c), float(o))

        c_ini = float(x_trecho[0])
        c_fim = float(x_trecho[-1])
        self.series_ajuste_rls.append(c_ini, a * c_ini + b)
        self.series_ajuste_rls.append(c_fim, a * c_fim + b)

        self.axis_molar_x.setRange(0, float(np.max(concentracoes)) * 1.1)
        self.axis_molar_y.setRange(0, float(np.max(omegas)) * 1.1)

    def atualizar_resultado(self, cmc, ctc, df_granulo, df_fases):
        self.lbl_cmc.setText(f"{cmc:.6f} mol/L")
        self.lbl_ctc.setText(f"{ctc:.2f} mEq/100g")

        g = df_granulo.iloc[0]
        self.lbl_d10.setText(f"{g['d10_um_com']:.2f}")
        self.lbl_d50.setText(f"{g['d50_um_com']:.2f}")
        self.lbl_d90.setText(f"{g['d90_um_com']:.2f}")
        self.lbl_diametro_medio.setText(f"{g['diametro_medio_um_com']:.2f}")

        f = df_fases.iloc[0]

        def fase_pct(val):
            v = float(val)
            if 0 < v <= 1.0:
                v *= 100.0
            return f"{v:.2f}%"

        self.lbl_montmorilonita.setText(fase_pct(f['Montmorilonita']))
        self.lbl_caulinita.setText(fase_pct(f['Caulinita']))
        self.lbl_quartzo.setText(fase_pct(f['Quartzo']))
        self.lbl_nontronita.setText(fase_pct(f['Nontronita']))
        self.lbl_cristobalita.setText(fase_pct(f['Cristobalita']))

        self._ultimo_cmc = cmc
        self._ultimo_ctc = ctc

    def get_button_style(self, is_action=False):
        if is_action:
            return f"""
                QPushButton {{ background-color: {HEX_ACTION}; color: white; border: 1px solid #1F375B; border-radius: 4px; }}
                QPushButton:pressed {{ background-color: #1F375B; }}
                QPushButton:disabled {{ background-color: #9AA7B5; border: 1px solid #8A97A5; }}
            """
        return f"""
            QPushButton {{ background-color: {HEX_SURFACE}; color: {HEX_TEXT}; border: 1px solid {HEX_BORDER}; border-radius: 4px; }}
            QPushButton:pressed {{ background-color: {HEX_SURFACE_PRES}; }}
            QPushButton:disabled {{ color: #B0B0B0; background-color: #EDEDEB; }}
        """

    # ────────────────────────────────────────────────────────────────
    # Exportação de relatório (botão "Salvar")
    # ────────────────────────────────────────────────────────────────
    def exportar_relatorio(self):
        if self.stack_estados.currentIndex() != self.ESTADO_FINALIZADO:
            QMessageBox.warning(
                self, "Exportação indisponível",
                "Processe um ensaio (botão 'Processar') antes de exportar o relatório."
            )
            return

        if self._ultimo_cmc is None:
            QMessageBox.warning(
                self, "Nada para exportar",
                "Ainda não há um resultado calculado nesta amostra."
            )
            return

        nome_sugerido = f"ensaio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        caminho, filtro = QFileDialog.getSaveFileName(
            self, "Exportar relatório do ensaio", nome_sugerido,
            "Relatório PDF (*.pdf);;Imagem PNG (*.png)"
        )
        if not caminho:
            return

        try:
            if caminho.lower().endswith(".png") or "PNG" in filtro:
                if not caminho.lower().endswith(".png"):
                    caminho += ".png"
                self._exportar_png(caminho)
            else:
                if not caminho.lower().endswith(".pdf"):
                    caminho += ".pdf"
                self._exportar_pdf(caminho)

        except PermissionError:
            self._limpar_arquivo_corrompido(caminho)
            QMessageBox.critical(
                self, "Erro de permissão",
                f"Não foi possível salvar em:\n{caminho}\n\n"
                "Verifique se o arquivo já está aberto em outro programa ou a pasta possui permissão de escrita"
            )
            return
        except OSError as e:
            self._limpar_arquivo_corrompido(caminho)
            QMessageBox.critical(
                self, "Erro de Armazenamento",
                f"Falha de gravação no sistema de arquivos do Raspberry Pi.\n\nDetalhes: {e}"
            )
            return
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível salvar o relatório.\n\nDetalhe: {erro}")
            return

        QMessageBox.information(self, "Exportado", f"Relatório salvo em:\n{caminho}")

    def _exportar_png(self, caminho):
        """Exporta só a imagem do gráfico, sem cabeçalho."""
        pixmap = self.chart_view_molar.grab()
        if not pixmap.save(caminho, "PNG"):
            raise IOError(f"Falha ao salvar PNG em {caminho}")

    def _limpar_arquivo_corrompido(self, caminho):
        """Garante que nenhum arquivo zerado ou incompleto permaneça no disco."""
        if os.path.exists(caminho) and os.path.getsize(caminho) == 0:
            try:
                os.remove(caminho)
            except OSError:
                pass

    def _exportar_pdf(self, caminho):
        pixmap = self.chart_view_molar.grab()
        if pixmap.isNull() or pixmap.width() == 0:
            raise RuntimeError("Não foi possível renderizar a imagem do gráfico.")

        writer = QPdfWriter(caminho)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(150)

        painter = QPainter()
        if not painter.begin(writer):
            raise OSError("Falha ao inicializar o motor de impressão PDF no arquivo de destino.")

        try:
            largura_pagina = painter.viewport().width()
            altura_pagina = painter.viewport().height()
            margem = int(largura_pagina * 0.06)
            y = margem

            fonte_titulo = QFont("Sans-Serif", 16, QFont.Bold)
            painter.setFont(fonte_titulo)
            painter.drawText(margem, y, "Relatório de Ensaio -- CTC via CMC")
            y += int(fonte_titulo.pointSize() * 3.0)

            fonte_corpo = QFont("Sans-Serif", 11)
            painter.setFont(fonte_corpo)
            linhas_cabecalho = [
                f"Data/hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}",
                f"Amostra: {self.nome_amostra}" if self.nome_amostra else "Amostra: --",
                f"Massa da amostra: {self.massa_amostra_g:.1f} g" if self.massa_amostra_g else "Massa da amostra: --",
                f"CMC: {self._ultimo_cmc:.6f} mol/L",
                f"CTC: {self._ultimo_ctc:.2f} mEq/100g",
            ]
            espacamento_linha = int(fonte_corpo.pointSize() * 2.6)
            for linha in linhas_cabecalho:
                painter.drawText(margem, y, linha)
                y += espacamento_linha

            y += margem // 2

            area_disponivel = QRectF(
                margem, y,
                largura_pagina - 2 * margem,
                altura_pagina - y - margem
            )
            proporcao_pixmap = pixmap.width() / pixmap.height()
            proporcao_area = area_disponivel.width() / area_disponivel.height()

            if proporcao_pixmap > proporcao_area:
                largura_final = area_disponivel.width()
                altura_final = largura_final / proporcao_pixmap
            else:
                altura_final = area_disponivel.height()
                largura_final = altura_final * proporcao_pixmap

            destino = QRectF(
                area_disponivel.left(), area_disponivel.top(),
                largura_final, altura_final
            )
            painter.drawPixmap(destino, pixmap, QRectF(pixmap.rect()))
        finally:
            painter.end()