#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PySide6.QtCore import Qt, Slot, QRectF
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QSizePolicy, QStackedWidget, QDoubleSpinBox,
    QFileDialog, QMessageBox
)
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QPdfWriter, QPageSize
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis, QScatterSeries
from datetime import datetime

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
    

    ESTADO_INICIAL     = 0
    ESTADO_COLETA      = 1
    ESTADO_FINALIZADO  = 2

    def __init__(self, app_instance, parent=None):
        super().__init__(parent)
        self.app_app = app_instance
        self.massa_amostra_g = None
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
        self.stack_estados.addWidget(self._build_pagina_inicial())
        self.stack_estados.addWidget(self._build_pagina_coleta())
        self.stack_estados.addWidget(self._build_pagina_finalizado())
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

        self.btn_parar.clicked.connect(self.app_app.parar_teste)
        self.btn_processar.clicked.connect(self.app_app.detectar_cmc)
        self.btn_voltar.clicked.connect(self.app_app.voltar_home)
        self.btn_iniciar.clicked.connect(self._on_iniciar_clicado)
        self.btn_salvar.clicked.connect(self.exportar_relatorio)

        main_layout.addLayout(footer_layout)
        self.setStyleSheet(f"background-color: {HEX_BG};")

        self.mostrar_estado_inicial()

    def _build_pagina_inicial(self):
        
        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(16)

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
        self.spin_massa_amostra.setRange(0, 1.0)
        self.spin_massa_amostra.setSingleStep(0.1)
        self.spin_massa_amostra.setSuffix(" g")
        self.spin_massa_amostra.setFixedSize(300,60)
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

    def _on_iniciar_coleta_clicado(self):
        """
        Clique em 'Iniciar Coleta' (página inicial): só salva a massa
        informada e leva o usuário para a tela de coleta, em modo
        'aguardando'. A aquisição real (Arduino, timers) só começa
        quando o botão 'Iniciar' do rodapé for pressionado.
        """
        self.massa_amostra_g = self.spin_massa_amostra.value()
        self.mostrar_estado_coleta_aguardando()

    def _on_iniciar_clicado(self):
        """
        Clique em 'Iniciar' (rodapé): aqui sim dispara o início real
        da aquisição, usando a massa salva no passo anterior.
        """
        self.app_app.iniciar_teste(self.massa_amostra_g)

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
        self
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

    def _on_registrar_adicao(self):
        volume_mL = self.spin_volume_adicao.value()
        self.app_app.registrar_adicao(volume_mL)

    def _build_pagina_finalizado(self):
        pagina = QWidget()
        body_layout = QHBoxLayout(pagina)
        body_layout.setContentsMargins(12, 12, 12, 12)
        body_layout.setSpacing(12)

        left_panel = QVBoxLayout()
        left_panel.setSpacing(10)

        self.card_cmc = self.create_numeric_card("CMC", "-- (aperte Processar)", "16px")
        self.card_ctc = self.create_numeric_card("CTC", "-- mEq/100g", "24px")
        self.card_tipo = self.create_numeric_card("TIPO DE ARGILA", "--", "18px")

        left_panel.addWidget(self.card_cmc)
        left_panel.addWidget(self.card_ctc)
        left_panel.addWidget(self.card_tipo)

        btn_novo_ensaio = QPushButton("Nova Amostra")
        btn_novo_ensaio.setFixedHeight(48)
        btn_novo_ensaio.setFont(QFont("Sans-Serif", 9, QFont.Bold))
        btn_novo_ensaio.setStyleSheet(self.get_button_style())
        btn_novo_ensaio.clicked.connect(self.app_app.novo_ensaio)
        left_panel.addWidget(btn_novo_ensaio)
        left_panel.addStretch(1)

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
        self.axis_molar_y.setTitleText("Condutividade molar Ω (µS·cm²/mol)")
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

        body_layout.addLayout(left_panel, stretch=35)
        body_layout.addWidget(chart_frame, stretch=65)
        return pagina

    def mostrar_estado_inicial(self):
        self.stack_estados.setCurrentIndex(self.ESTADO_INICIAL)
        self.btn_parar.setEnabled(False)
        self.btn_processar.setEnabled(False)
        self.btn_salvar.setEnabled(False)
        self.btn_iniciar.setEnabled(False)

    def mostrar_estado_coleta_aguardando(self):
        """Troca pra tela de coleta, mas aquisição ainda NÃO começou."""
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
        self.btn_parar.setEnabled(False)
        self.btn_processar.setEnabled(True)
        self.btn_salvar.setEnabled(True)

    def create_numeric_card(self, title, initial_value, font_size):
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

        setattr(self, f"lbl_{title.lower().replace(' ', '_').replace('çã', 'ca')}", val_lbl)
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

        self.lbl_volume_total_adicionado.setText("0.00 mL")
        self.lbl_leituras_recebidas.setText("0")
        self.lbl_cmc.setText("-- (aperte Processar)")
        self.lbl_ctc.setText("-- mEq/100g")
        self.lbl_tipo_de_argila.setText("--")

    def atualizar_volume_total(self, volume_mL):
        self.lbl_volume_total_adicionado.setText(f"{volume_mL:.2f} mL")

    def plotar_resultado_cmc(self, resultado):
        """
        Atualiza o gráfico de Condutividade Molar × Concentração Molar
        com o resultado de detectar_cmc_joao_original(): TODOS os pontos
        medidos, os pontos que fazem parte do trecho linear identificado
        (destacados em verde) e a reta única ajustada nesse trecho
        (linha tracejada).

        Isso substitui o antigo plotar_ajuste_cmc_joao(), que esperava
        DUAS retas (pré/pós-micelização) -- o método fiel ao João só
        ajusta UMA reta, no trecho final da curva (ver
        services/analises.py: detectar_cmc_joao_original).
        """
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

        # Desenha a reta ao longo de todo o trecho linear identificado
        c_ini = float(x_trecho[0])
        c_fim = float(x_trecho[-1])
        self.series_ajuste_rls.append(c_ini, a * c_ini + b)
        self.series_ajuste_rls.append(c_fim, a * c_fim + b)

        self.axis_molar_x.setRange(0, float(concentracoes.max()) * 1.1)
        self.axis_molar_y.setRange(0, float(omegas.max()) * 1.1)

    def atualizar_resultado(self, cmc, ctc, tipo_argila):
        self.lbl_cmc.setText(f"{cmc:.6f} mol/L")
        self.lbl_ctc.setText(f"{ctc:.2f} mEq/100g")
        self.lbl_tipo_de_argila.setText(tipo_argila)

        # Guarda pra usar no cabeçalho do relatório exportado (exportar_relatorio)
        self._ultimo_cmc = cmc
        self._ultimo_ctc = ctc
        self._ultimo_tipo = tipo_argila

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
        """
        Exporta o gráfico de CMC (Condutividade Molar × Concentração
        Molar) junto com os valores calculados -- parecido com o
        relatório que o equipamento do João gerava (Apêndice C da
        dissertação: "Modelo de Relatório Criado pelo Dispositivo de
        Monitoramento"). Suporta PNG (imagem simples do gráfico) ou
        PDF (relatório com cabeçalho: data, massa, CMC, CTC, tipo).

        NOTA: não tenho o layout exato do Apêndice C (é uma figura na
        dissertação, não texto que eu tenha em mãos) -- montei um
        cabeçalho equivalente e razoável. Se você tiver o modelo real,
        me manda que eu ajusto o layout do PDF pra bater certinho.
        """
        if self.stack_estados.currentIndex() != self.ESTADO_FINALIZADO:
            QMessageBox.warning(
                self, "Nada para exportar",
                "Processe um ensaio (botão 'Processar') antes de exportar o relatório."
            )
            return

        if not hasattr(self, "_ultimo_cmc"):
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
        except Exception as erro:
            QMessageBox.critical(self, "Erro ao exportar", f"Não foi possível salvar o relatório.\n\nDetalhe: {erro}")
            return

        QMessageBox.information(self, "Exportado", f"Relatório salvo em:\n{caminho}")

    def _exportar_png(self, caminho):
        """Exporta só a imagem do gráfico, sem cabeçalho."""
        pixmap = self.chart_view_molar.grab()
        if not pixmap.save(caminho, "PNG"):
            raise IOError(f"Falha ao salvar PNG em {caminho}")

    def _exportar_pdf(self, caminho):
        """Exporta um relatório em PDF: cabeçalho com os valores calculados + o gráfico."""
        writer = QPdfWriter(caminho)
        writer.setPageSize(QPageSize(QPageSize.A4))
        writer.setResolution(150)

        painter = QPainter(writer)
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
                f"Massa da amostra: {self.massa_amostra_g:.1f} g" if self.massa_amostra_g else "Massa da amostra: --",
                f"CMC: {self._ultimo_cmc:.6f} mol/L",
                f"CTC: {self._ultimo_ctc:.2f} mEq/100g",
                f"Classificação: {self._ultimo_tipo}",
            ]
            espacamento_linha = int(fonte_corpo.pointSize() * 2.6)
            for linha in linhas_cabecalho:
                painter.drawText(margem, y, linha)
                y += espacamento_linha

            y += margem // 2

            # Desenha o gráfico logo abaixo do cabeçalho, ocupando o
            # restante da página, mantendo a proporção original.
            pixmap = self.chart_view_molar.grab()
            area_disponivel = QRectF(
                margem, y,
                largura_pagina - 2 * margem,
                altura_pagina - y - margem,
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
                largura_final, altura_final,
            )
            painter.drawPixmap(destino, pixmap, QRectF(pixmap.rect()))
        finally:
            painter.end()