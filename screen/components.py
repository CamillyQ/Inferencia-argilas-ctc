from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QPushButton, QLabel, QHBoxLayout, QSizePolicy
from PySide6.QtGui import QFont

HEX_SURFACE      = "#FFFFFF"
HEX_SURFACE_PRES = "#EBEEF2"
HEX_BORDER       = "#D1D1CD"
HEX_TEXT         = "#212121"
HEX_ACTION       = "#2E5284"
HEX_ACTION_PRES  = "#1F375B"

class SCADAButton(QPushButton):
    def __init__(self, text, is_primary=False, parent=None):
        super().__init__(text, parent)
        self.is_primary = is_primary
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMinimumHeight(64)  
        
        self.setFont(QFont("Sans-Serif", 11, QFont.Bold))
        
        self.setProperty("is_primary", str(is_primary).lower())


class StatusPill(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(8)

        self.led = QLabel("●")
        self.led.setFont(QFont("Sans-Serif", 14, QFont.Bold))
   
        self.label = QLabel("SISTEMA PRONTO")
        self.label.setFont(QFont("Courier New", 10, QFont.Bold))
        
        layout.addWidget(self.led)
        layout.addWidget(self.label)
        layout.addStretch() 
        
        self.set_status("SISTEMA PRONTO", "#6B6B6B")

    def set_status(self, text, color_hex):
        
        self.label.setText(text.upper())
        self.label.setStyleSheet(f"color: {HEX_TEXT};")
        self.led.setStyleSheet(f"color: {color_hex};")

from typing import Optional, Sequence, Tuple

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

COR_FUNDO = "#EDEDED"
COR_PAINEL = "#F7F7F7"
COR_BORDA = "#C7C7C7"
COR_TEXTO = "#2B2B2B"
COR_TEXTO_SECUNDARIO = "#6B6B6B"
COR_PONTOS = "#4A4A4A"      
COR_RETA_PRE = "#0B6FA4"   
COR_RETA_POS = "#B3261E"    
COR_PONTO_CMC = "#2E7D32"   


class GraficoCondutividade(QWidget):

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._construir_ui()
        self.limpar()

    # ------------------------------------------------------------------
    def _construir_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._figura = Figure(figsize=(4, 2.2), dpi=100)
        self._figura.patch.set_facecolor(COR_PAINEL)

        self._eixo = self._figura.add_subplot(111)
        self._eixo.set_facecolor("white")

        self._canvas = FigureCanvas(self._figura)
        self._canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._canvas)

        self._figura.tight_layout()

    # ------------------------------------------------------------------
    def plotar(
        self,
        concentracoes: Sequence[float],
        omegas: Sequence[float],
        reta_pre: Optional[Tuple[float, float]] = None,
        reta_pos: Optional[Tuple[float, float]] = None,
        ponto_cmc: Optional[Tuple[Optional[float], Optional[float]]] = None,
    ) -> None:
       
        self._eixo.clear()
        self._eixo.set_facecolor("white")

        concentracoes = np.asarray(concentracoes, dtype=float)
        omegas = np.asarray(omegas, dtype=float)

        if concentracoes.size == 0 or omegas.size == 0:
            self._mostrar_placeholder("Sem dados para exibir.")
            return

        self._eixo.scatter(
            concentracoes, omegas,
            color=COR_PONTOS, s=28, zorder=3, label="Dados do ensaio",
        )

        x_min, x_max = float(concentracoes.min()), float(concentracoes.max())
        margem = (x_max - x_min) * 0.05 or 1e-6

        if reta_pre is not None:
            a, b = reta_pre
            x_reta = np.linspace(x_min - margem, x_max, 50)
            self._eixo.plot(
                x_reta, a * x_reta + b,
                color=COR_RETA_PRE, linestyle="--", linewidth=1.5,
                zorder=2, label="Reta pré-micelização",
            )

        if reta_pos is not None:
            a, b = reta_pos
            x_reta = np.linspace(x_min, x_max + margem, 50)
            self._eixo.plot(
                x_reta, a * x_reta + b,
                color=COR_RETA_POS, linestyle="--", linewidth=1.5,
                zorder=2, label="Reta pós-micelização",
            )

        if ponto_cmc is not None and ponto_cmc[0] is not None and ponto_cmc[1] is not None:
            x_cmc, y_cmc = ponto_cmc
            self._eixo.scatter(
                [x_cmc], [y_cmc],
                color=COR_PONTO_CMC, s=90, marker="X", zorder=4,
                edgecolors="white", linewidths=1.2,
                label=f"CMC = {x_cmc:.6f} mol/L",
            )

        self._eixo.set_xlabel("Concentração molar (mol/L)", color=COR_TEXTO)
        self._eixo.set_ylabel("Condutividade molar (S·cm²/mol)", color=COR_TEXTO)
        self._eixo.tick_params(colors=COR_TEXTO_SECUNDARIO)
        for spine in self._eixo.spines.values():
            spine.set_color(COR_BORDA)
        self._eixo.grid(True, linestyle=":", linewidth=0.6, color=COR_BORDA, alpha=0.7)
        self._eixo.legend(
            loc="best", fontsize=8, framealpha=0.9, facecolor="white",
            edgecolor=COR_BORDA,
        )

        self._figura.tight_layout()
        self._canvas.draw_idle()

    def limpar(self) -> None:
        """Volta o gráfico ao estado inicial, sem dados."""
        self._eixo.clear()
        self._mostrar_placeholder("Nenhum ensaio selecionado.")

    def _mostrar_placeholder(self, mensagem: str) -> None:
        self._eixo.clear()
        self._eixo.set_facecolor("white")
        self._eixo.axis("off")
        self._eixo.text(
            0.5, 0.5, mensagem,
            ha="center", va="center", color=COR_TEXTO_SECUNDARIO,
            fontsize=11, transform=self._eixo.transAxes,
        )
        self._figura.tight_layout()
        self._canvas.draw_idle()