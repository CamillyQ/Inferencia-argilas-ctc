from __future__ import annotations

from datetime import datetime, date
from typing import Optional

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDateEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QFrame, QMessageBox, QFileDialog,
)
from services import banco_local as db
from components import SCADAButton


COR_FUNDO = "#EDEDED"
COR_PAINEL = "#F7F7F7"
COR_BORDA = "#C7C7C7"
COR_TEXTO = "#2B2B2B"
COR_TEXTO_SECUNDARIO = "#6B6B6B"
COR_DESTAQUE = "#0B6FA4"     
COR_PERIGO = "#B3261E"      
COR_SUCESSO = "#2E7D32"      

ALTURA_MINIMA_TOQUE = 64     
MARGEM_PADRAO = 8           
ESPACAMENTO_PADRAO = 8


class _CartaoMetrica(QFrame):
   

    def __init__(self, rotulo: str, cor: str = "#0B6FA4", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame {{ background-color: white; border: 1px solid {COR_BORDA}; "
            f"border-radius: 6px; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(2)

        self._rotulo = QLabel(rotulo)
        self._rotulo.setStyleSheet(f"color: {COR_TEXTO_SECUNDARIO}; font-size: 10px;")

        self._valor = QLabel("—")
        self._valor.setStyleSheet(f"color: {cor}; font-weight: 700; font-size: 13px;")

        layout.addWidget(self._rotulo)
        layout.addWidget(self._valor)

    def definir_valor(self, valor: str) -> None:
        self._valor.setText(valor)


class TelaHistorico(QWidget):

    ensaio_selecionado = Signal(dict)

    def __init__(self, app_instance=None, parent=None):
        super().__init__(parent)
        self.app = app_instance
        self._ensaio_atual: Optional[dict] = None
        self._construir_ui()
        self.atualizar_lista()

    def _construir_ui(self) -> None:
        self.setStyleSheet(f"background-color: {COR_FUNDO};")

        layout_principal = QVBoxLayout(self)
        layout_principal.setContentsMargins(
            MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO
        )
        layout_principal.setSpacing(ESPACAMENTO_PADRAO)

        layout_principal.addWidget(self._criar_cabecalho())
        layout_principal.addWidget(self._criar_barra_filtros())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._criar_painel_lista())
        splitter.addWidget(self._criar_painel_detalhes())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout_principal.addWidget(splitter, stretch=1)

        layout_principal.addWidget(self._criar_barra_acoes())

        self._mostrar_detalhes(None)

    def _criar_cabecalho(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ESPACAMENTO_PADRAO)

        botao_voltar = SCADAButton("← Voltar", is_primary=False)
        botao_voltar.setFixedWidth(120)
        botao_voltar.clicked.connect(self._voltar)

        titulo = QLabel("Histórico de Ensaios")
        fonte = QFont()
        fonte.setPointSize(14)
        fonte.setBold(True)
        titulo.setFont(fonte)
        titulo.setStyleSheet(f"color: {COR_TEXTO};")

        layout.addWidget(botao_voltar)
        layout.addWidget(titulo, stretch=1)
        return container

    def _voltar(self) -> None:
        if self.app is not None and hasattr(self.app, "voltar_home"):
            self.app.voltar_home()

    def _criar_barra_filtros(self) -> QWidget:
        painel = QFrame()
        painel.setStyleSheet(
            f"QFrame {{ background-color: {COR_PAINEL}; "
            f"border: 1px solid {COR_BORDA}; border-radius: 8px; }}"
        )
        layout = QHBoxLayout(painel)
        layout.setContentsMargins(MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO)
        layout.setSpacing(ESPACAMENTO_PADRAO)

        rotulo_busca = QLabel("Amostra:")
        rotulo_busca.setStyleSheet(f"color: {COR_TEXTO};")
        self.campo_busca = QLineEdit()
        self.campo_busca.setPlaceholderText("Buscar por nome da amostra...")
        self.campo_busca.setMinimumHeight(ALTURA_MINIMA_TOQUE)
        self.campo_busca.textChanged.connect(self._on_filtro_alterado)

        rotulo_de = QLabel("De:")
        rotulo_de.setStyleSheet(f"color: {COR_TEXTO};")
        self.data_inicio = QDateEdit(calendarPopup=True)
        self.data_inicio.setDate(QDate.currentDate().addMonths(-3))
        self.data_inicio.setMinimumHeight(ALTURA_MINIMA_TOQUE)
        self.data_inicio.dateChanged.connect(self._on_filtro_alterado)

        rotulo_ate = QLabel("Até:")
        rotulo_ate.setStyleSheet(f"color: {COR_TEXTO};")
        self.data_fim = QDateEdit(calendarPopup=True)
        self.data_fim.setDate(QDate.currentDate())
        self.data_fim.setMinimumHeight(ALTURA_MINIMA_TOQUE)
        self.data_fim.dateChanged.connect(self._on_filtro_alterado)

        botao_limpar = SCADAButton("Limpar filtros", is_primary=False)
        botao_limpar.clicked.connect(self._limpar_filtros)

        layout.addWidget(rotulo_busca)
        layout.addWidget(self.campo_busca, stretch=1)
        layout.addWidget(rotulo_de)
        layout.addWidget(self.data_inicio)
        layout.addWidget(rotulo_ate)
        layout.addWidget(self.data_fim)
        layout.addWidget(botao_limpar)

        return painel

    def _criar_painel_lista(self) -> QWidget:
        painel = QFrame()
        painel.setStyleSheet(
            f"QFrame {{ background-color: {COR_PAINEL}; "
            f"border: 1px solid {COR_BORDA}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO)

        self.tabela = QTableWidget(0, 5)
        self.tabela.setHorizontalHeaderLabels(
            ["Data/Hora", "Amostra", "CTC (mEq/100g)", "CMC (mol/L)", "Massa (g)"]
        )
        self.tabela.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeToContents
        )
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        for col in (2, 3, 4):
            self.tabela.horizontalHeader().setSectionResizeMode(
                col, QHeaderView.ResizeToContents
            )
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tabela.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela.verticalHeader().setDefaultSectionSize(ALTURA_MINIMA_TOQUE)
        self.tabela.itemSelectionChanged.connect(self._on_selecao_alterada)
        self.tabela.setStyleSheet(
            f"QTableWidget {{ background-color: white; color: {COR_TEXTO}; "
            f"gridline-color: {COR_BORDA}; }}"
        )

        layout.addWidget(self.tabela)
        return painel

    def _criar_painel_detalhes(self) -> QWidget:
        painel = QFrame()
        painel.setStyleSheet(
            f"QFrame {{ background-color: {COR_PAINEL}; "
            f"border: 1px solid {COR_BORDA}; border-radius: 8px; }}"
        )
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO, MARGEM_PADRAO)
        layout.setSpacing(ESPACAMENTO_PADRAO)

        rotulo = QLabel("Detalhes do ensaio")
        fonte = QFont()
        fonte.setBold(True)
        rotulo.setFont(fonte)
        rotulo.setStyleSheet(f"color: {COR_TEXTO};")
        layout.addWidget(rotulo)

        linha_pills = QHBoxLayout()
        self.pill_ctc = _CartaoMetrica("CTC", cor=COR_DESTAQUE)
        self.pill_cmc = _CartaoMetrica("CMC", cor=COR_DESTAQUE)
        self.pill_classificacao = _CartaoMetrica("Classificação", cor=COR_SUCESSO)
        linha_pills.addWidget(self.pill_ctc)
        linha_pills.addWidget(self.pill_cmc)
        linha_pills.addWidget(self.pill_classificacao)
        layout.addLayout(linha_pills)

        self.rotulo_resumo = QLabel()
        self.rotulo_resumo.setWordWrap(True)
        self.rotulo_resumo.setStyleSheet(f"color: {COR_TEXTO};")
        self.rotulo_resumo.setTextFormat(Qt.RichText)
        layout.addWidget(self.rotulo_resumo)
        layout.addStretch(1)

        self.rotulo_sem_selecao = QLabel(
            "Selecione um ensaio na lista à esquerda para ver os detalhes."
        )
        self.rotulo_sem_selecao.setStyleSheet(f"color: {COR_TEXTO_SECUNDARIO};")
        self.rotulo_sem_selecao.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rotulo_sem_selecao)

        return painel

    def _criar_barra_acoes(self) -> QWidget:
        painel = QFrame()
        layout = QHBoxLayout(painel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(ESPACAMENTO_PADRAO)

        self.botao_atualizar = SCADAButton("↻ Atualizar lista", is_primary=False)
        self.botao_atualizar.clicked.connect(self.atualizar_lista)

        self.botao_exportar_csv = SCADAButton("⬇ Exportar CSV", is_primary=True)
        self.botao_exportar_csv.setEnabled(False)
        self.botao_exportar_csv.clicked.connect(self._exportar_csv)
        self.botao_excluir = SCADAButton("🗑 Excluir ensaio", is_primary=False)
        self.botao_excluir.setStyleSheet(
            f"QPushButton {{ background-color: {COR_PERIGO}; color: white; "
            f"border: none; border-radius: 6px; }}"
            f"QPushButton:disabled {{ background-color: #D9B8B5; color: #F2E6E5; }}"
        )
        self.botao_excluir.setEnabled(False)
        self.botao_excluir.clicked.connect(self._excluir_ensaio)

        layout.addWidget(self.botao_atualizar)
        layout.addStretch(1)
        layout.addWidget(self.botao_exportar_csv)
        layout.addWidget(self.botao_excluir)

        return painel

    def atualizar_lista(self) -> None:
        """Recarrega a tabela com os ensaios do banco, aplicando os
        filtros atualmente definidos na barra de busca."""
        texto = self.campo_busca.text().strip() or None
        data_ini = self.data_inicio.date().toPython()
        data_fim = self.data_fim.date().toPython()

        try:
            ensaios = db.listar_ensaios( 
                filtro_texto=texto, data_inicio=data_ini, data_fim=data_fim
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao carregar histórico",
                f"Não foi possível carregar os ensaios salvos.\n\nDetalhe: {exc}"
            )
            ensaios = []

        self._preencher_tabela(ensaios)
        self._mostrar_detalhes(None)

    def _preencher_tabela(self, ensaios: list[dict]) -> None:
        self.tabela.setRowCount(0)
        for ensaio in ensaios:
            linha = self.tabela.rowCount()
            self.tabela.insertRow(linha)

            data_hora = ensaio.get("data_hora")
            if isinstance(data_hora, (datetime, date)):
                data_hora_txt = data_hora.strftime("%d/%m/%Y %H:%M")
            else:
                data_hora_txt = str(data_hora or "—")

            valores = [
                data_hora_txt,
                str(ensaio.get("amostra", "—")),
                f"{ensaio.get('ctc', 0):.2f}",
                f"{ensaio.get('cmc', 0):.6f}",
                f"{ensaio.get('massa_g', 0):.4f}",
            ]
            for col, valor in enumerate(valores):
                item = QTableWidgetItem(valor)
                item.setTextAlignment(Qt.AlignCenter)
                if col == 0:
                    
                    item.setData(Qt.UserRole, ensaio.get("id"))
                self.tabela.setItem(linha, col, item)

    def _on_filtro_alterado(self, *_args) -> None:
        self.atualizar_lista()

    def _limpar_filtros(self) -> None:
        self.campo_busca.blockSignals(True)
        self.campo_busca.clear()
        self.campo_busca.blockSignals(False)
        self.data_inicio.setDate(QDate.currentDate().addMonths(-3))
        self.data_fim.setDate(QDate.currentDate())
        self.atualizar_lista()

    def _on_selecao_alterada(self) -> None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            self._mostrar_detalhes(None)
            return

        linha = linhas[0].row()
        ensaio_id = self.tabela.item(linha, 0).data(Qt.UserRole)
        try:
            ensaio = db.obter_ensaio(ensaio_id) 
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao abrir ensaio",
                f"Não foi possível carregar os detalhes deste ensaio.\n\nDetalhe: {exc}"
            )
            self._mostrar_detalhes(None)
            return

        self._mostrar_detalhes(ensaio)
        if ensaio is not None:
            self.ensaio_selecionado.emit(ensaio)

    def _mostrar_detalhes(self, ensaio: Optional[dict]) -> None:
        self._ensaio_atual = ensaio
        tem_ensaio = ensaio is not None

        self.botao_exportar_csv.setEnabled(tem_ensaio)
        self.botao_excluir.setEnabled(tem_ensaio)
        self.rotulo_resumo.setVisible(tem_ensaio)
        self.rotulo_sem_selecao.setVisible(not tem_ensaio)

        if not tem_ensaio:
            self.pill_ctc.definir_valor("—")
            self.pill_cmc.definir_valor("—")
            self.pill_classificacao.definir_valor("—")
            return

        self.pill_ctc.definir_valor(f"{ensaio.get('ctc', 0):.2f} mEq/100g")
        self.pill_cmc.definir_valor(f"{ensaio.get('cmc', 0):.6f} mol/L")
        self.pill_classificacao.definir_valor(str(ensaio.get("classificacao", "—")))

        self.rotulo_resumo.setText(
            f"<b>Amostra:</b> {ensaio.get('amostra', '—')}<br>"
            f"<b>Massa:</b> {ensaio.get('massa_g', 0):.4f} g<br><br>"
            f"<b>Granulometria</b><br>"
            f"d10: {ensaio.get('d10_um', 0):.2f} µm &nbsp; "
            f"d50: {ensaio.get('d50_um', 0):.2f} µm &nbsp; "
            f"d90: {ensaio.get('d90_um', 0):.2f} µm &nbsp; "
            f"médio: {ensaio.get('diametro_medio_um', 0):.2f} µm<br><br>"
            f"<b>Fases minerais</b><br>"
            f"Montmorilonita: {ensaio.get('montmorilonita_pct', 0):.2f}% &nbsp; "
            f"Caulinita: {ensaio.get('caulinita_pct', 0):.2f}%<br>"
            f"Quartzo: {ensaio.get('quartzo_pct', 0):.2f}% &nbsp; "
            f"Cristobalita: {ensaio.get('cristobalita_pct', 0):.2f}% &nbsp; "
            f"Nontronita: {ensaio.get('nontronita_pct', 0):.2f}%"
        )

    def _exportar_csv(self) -> None:
        if self._ensaio_atual is None:
            return

        nome_sugerido = (
            f"ensaio_{self._ensaio_atual.get('amostra', 'amostra')}_"
            f"{self._ensaio_atual.get('id', '')}.csv"
        )
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Exportar ensaio como CSV", nome_sugerido, "CSV (*.csv)"
        )
        if not caminho:
            return

        try:
            db.exportar_ensaio_csv(self._ensaio_atual["id"], caminho)  # ADAPTAR
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao exportar",
                f"Não foi possível exportar o ensaio.\n\nDetalhe: {exc}"
            )
            return

        QMessageBox.information(
            self, "Exportação concluída", f"Ensaio salvo em:\n{caminho}"
        )

    def _excluir_ensaio(self) -> None:
        if self._ensaio_atual is None:
            return

        resposta = QMessageBox.question(
            self,
            "Excluir ensaio",
            "Esta ação não pode ser desfeita. Deseja realmente excluir "
            f"o ensaio da amostra \"{self._ensaio_atual.get('amostra', '—')}\"?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            db.excluir_ensaio(self._ensaio_atual["id"])  # ADAPTAR
        except Exception as exc:
            QMessageBox.critical(
                self, "Erro ao excluir",
                f"Não foi possível excluir o ensaio.\n\nDetalhe: {exc}"
            )
            return

        self.atualizar_lista()