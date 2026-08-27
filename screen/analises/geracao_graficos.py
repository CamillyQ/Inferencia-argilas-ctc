import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from sklearn.base import clone
from sklearn.model_selection import LeaveOneOut
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
from sklearn.neighbors import KNeighborsRegressor, KNeighborsClassifier
from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.svm import SVR, SVC
from sklearn.neural_network import MLPRegressor, MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, confusion_matrix
)
from sklearn.metrics.pairwise import euclidean_distances


def gerar_tabela_detalhada_fases(nomes_amostra, Y_real, previsoes_por_modelo, alvos_fases):
    """
    Gera uma tabela consolidada (DataFrame) comparando o valor Real vs Previsto
    e o Erro Absoluto de cada modelo para todas as fases minerais.
    """
    colunas_fases = [f.replace("pct_drx_", "") for f in alvos_fases]
    linhas = []
    
    for i, amostra in enumerate(nomes_amostra):
        for j, fase in enumerate(colunas_fases):
            val_real = Y_real[i, j]
            linha = {
                'Amostra': amostra,
                'Fase Mineral': fase,
                'Real (%)': round(val_real, 2)
            }
            
            for nome_modelo, Y_pred in previsoes_por_modelo.items():
                val_pred = Y_pred[i, j]
                erro_abs = abs(val_real - val_pred)
                linha[f'Pred {nome_modelo} (%)'] = round(val_pred, 2)
                linha[f'Erro {nome_modelo} (%)'] = round(erro_abs, 2)
                
            linhas.append(linha)
            
    return pd.DataFrame(linhas)


def gerar_tabela_detalhada_single_target(nomes_amostra, dict_y_real, dict_previsoes_por_alvo, alvos):
    """
    Gera uma tabela consolidada (DataFrame) comparando Real vs Previsto
    para todos os alvos de granulometria.
    """
    linhas = []
    
    for alvo in alvos:
        y_real = dict_y_real[alvo]
        previsoes_por_modelo = dict_previsoes_por_alvo[alvo]
        
        for i, amostra in enumerate(nomes_amostra):
            val_real = y_real[i]
            linha = {
                'Amostra': amostra,
                'Alvo': alvo,
                'Real': round(val_real, 2)
            }
            
            for nome_modelo, y_pred in previsoes_por_modelo.items():
                val_pred = y_pred[i]
                erro_abs = abs(val_real - val_pred)
                linha[f'Pred {nome_modelo}'] = round(val_pred, 2)
                linha[f'Erro {nome_modelo}'] = round(erro_abs, 2)
                
            linhas.append(linha)
            
    return pd.DataFrame(linhas)
def configurar_estilo_cientifico():
    """Define padronização estética para publicação científica."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 13,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False
    })

def plot_real_vs_predito_fases_minerais(Y_real, dict_previsoes, alvos_fases, caminho_saida):
    """
    Gera gráficos de dispersão (Real vs Previsto) com linha de identidade y=x
    para cada fase mineral (% DRX), comparando todos os modelos.
    """
    n_fases = len(alvos_fases)
    fig, eixos = plt.subplots(n_fases, 1, figsize=(10, 3.5 * n_fases))
    if n_fases == 1:
        eixos = [eixos]

    cores = plt.cm.tab10(np.linspace(0, 1, len(dict_previsoes)))

    for i, fase in enumerate(alvos_fases):
        ax = eixos[i]
        y_r = Y_real[:, i]

        # Linha de identidade (y = x)
        v_min, v_max = min(y_r) - 5, max(y_r) + 5
        ax.plot([v_min, v_max], [v_min, v_max], color='red', linestyle='--', alpha=0.7, label='Ideal (y = x)', zorder=1)

        for idx, (nome_modelo, Y_pred) in enumerate(dict_previsoes.items()):
            y_p = Y_pred[:, i]
            mae = mean_absolute_error(y_r, y_p)
            ax.scatter(y_r, y_p, label=f'{nome_modelo} (MAE: {mae:.1f}%)',
                       color=cores[idx], edgecolors = 'none', s=70, alpha=0.85, zorder=2)

        ax.set_title(f'Fase Mineral: {fase.replace("pct_drx_", "")}', fontweight='bold')
        ax.set_xlabel('Valor Real (%)')
        ax.set_ylabel('Valor Previsto (%)')
        ax.set_xlim(v_min, v_max)
        ax.set_ylim(v_min, v_max)
        ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', frameon=True)

    fig.tight_layout()
    fig.savefig(caminho_saida, bbox_inches='tight', dpi=300)
    plt.close(fig)

def plot_heatmap_metricas(df_metricas, col_alvo, col_mae, col_rmse, col_r2, titulo_prefixo, caminho_saida):
    """Gera heatmaps das métricas MAE, RMSE e R2 cruzando Modelos x Alvos."""
    fig, eixos = plt.subplots(1, 3, figsize=(18, 6))
    
    pivot_mae = df_metricas.pivot(index='modelo', columns=col_alvo, values=col_mae)
    pivot_rmse = df_metricas.pivot(index='modelo', columns=col_alvo, values=col_rmse)
    pivot_r2 = df_metricas.pivot(index='modelo', columns=col_alvo, values=col_r2)

    sns.heatmap(pivot_mae, annot=True, fmt=".2f", cmap="YlOrRd", ax=eixos[0], cbar_kws={'label': col_mae})
    eixos[0].set_title(f'Erro Médio Absoluto ({col_mae})')
    eixos[0].set_ylabel('Modelo')
    eixos[0].set_xlabel('')

    sns.heatmap(pivot_rmse, annot=True, fmt=".2f", cmap="YlOrRd", ax=eixos[1], cbar_kws={'label': col_rmse})
    eixos[1].set_title(f'Raiz do Erro Quadrático Médio ({col_rmse})')
    eixos[1].set_ylabel('')
    eixos[1].set_xlabel('')

    sns.heatmap(pivot_r2, annot=True, fmt=".2f", cmap="Blues", ax=eixos[2], vmin=-1, vmax=1, cbar_kws={'label': 'R²'})
    eixos[2].set_title('Coeficiente de Determinação (R²)')
    eixos[2].set_ylabel('')
    eixos[2].set_xlabel('')

    for ax in eixos:
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")

    fig.suptitle(f'{titulo_prefixo} — Avaliação de Métricas de Desempenho', fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(caminho_saida, bbox_inches='tight')
    plt.close(fig)


def plot_real_vs_predito_dispersao(y_real, dict_previsoes, titulo, unidade, caminho_saida):
    """Gera gráficos de dispersão (Real vs Previsto) com a linha de identidade y=x."""
    n_modelos = len(dict_previsoes)
    cols = 3
    rows = (n_modelos + cols - 1) // cols
    fig, eixos = plt.subplots(rows, cols, figsize=(14, 4 * rows))
    eixos = eixos.flatten()

    for idx, (nome_modelo, y_pred) in enumerate(dict_previsoes.items()):
        ax = eixos[idx]
        ax.scatter(y_real, y_pred, color='#1f77b4', edgecolors='none', s=60, alpha=0.8, zorder=3)
        
        # Linha de identidade (y = x)
        val_min = min(np.min(y_real), np.min(y_pred))
        val_max = max(np.max(y_real), np.max(y_pred))
        ax.plot([val_min, val_max], [val_min, val_max], 'r--', label='Ideal (y = x)', zorder=2)
        
        r2 = r2_score(y_real, y_pred)
        mae = mean_absolute_error(y_real, y_pred)
        
        ax.set_title(f'{nome_modelo}\nR² = {r2:.2f} | MAE = {mae:.2f} {unidade}')
        ax.set_xlabel(f'Valor Real ({unidade})')
        ax.set_ylabel(f'Valor Previsto ({unidade})')
        ax.legend(loc='upper left')

    # Desativa eixos vazios excedentes
    for i in range(idx + 1, len(eixos)):
        fig.delaxes(eixos[i])

    fig.suptitle(f'Comparativo Real vs. Previsto: {titulo}', fontweight='bold', y=1.02)
    fig.tight_layout()
    fig.savefig(caminho_saida, bbox_inches='tight')
    plt.close(fig)


def plot_composicao_fases(nomes_amostra, Y_real, previsoes_por_modelo, alvos, caminho_saida):
    """Gera barras empilhadas horizontais comparando composição real vs predita por modelo."""
    modelos = list(previsoes_por_modelo.keys())
    n_amostras = len(nomes_amostra)
    fig, eixos = plt.subplots(n_amostras, 1, figsize=(11, 2.8 * n_amostras), sharex=True)
    if n_amostras == 1:
        eixos = [eixos]

    for i, nome_amostra in enumerate(nomes_amostra):
        ax = eixos[i]
        dados_amostra = [Y_real[i]] + [previsoes_por_modelo[m][i] for m in modelos]
        rotulos = ['Real'] + modelos
        df_amostra = pd.DataFrame(dados_amostra, index=rotulos, columns=alvos)
        
        df_amostra.plot(kind='barh', stacked=True, ax=ax, colormap='Spectral', edgecolor='black', linewidth=0.5)
        ax.set_title(f'Amostra: {nome_amostra}', fontsize=11, fontweight='bold', loc='left')
        ax.set_xlim(0, 100)
        ax.set_xlabel('Porcentagem das Fases (%)')
        ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', frameon=True)

    fig.tight_layout()
    fig.savefig(caminho_saida, bbox_inches='tight')
    plt.close(fig)


def plot_matriz_confusao_e_distancias(y_real, y_pred, X_scaled, nomes_amostras, caminho_saida):
    """Gera Matriz de Confusão e Mapa de Calor da Matriz de Distância Euclidiana Padronizada."""
    fig, eixos = plt.subplots(1, 2, figsize=(15, 6))
    
    # 1. Matriz de Confusão
    classes = sorted(list(set(y_real)))
    cm = confusion_matrix(y_real, y_pred, labels=classes)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', xticklabels=classes, yticklabels=classes, ax=eixos[0], cbar=False)
    eixos[0].set_title('Matriz de Confusão — Identificação 1-NN (LOOCV)', fontweight='bold')
    eixos[0].set_xlabel('Amostra Prevista / Identificada')
    eixos[0].set_ylabel('Amostra Real')
    plt.setp(eixos[0].get_xticklabels(), rotation=45, ha="right")

    # 2. Mapa de Calor da Matriz de Distâncias Par a Par
    matriz_dist = euclidean_distances(X_scaled, X_scaled)
    df_dist = pd.DataFrame(matriz_dist, index=nomes_amostras, columns=nomes_amostras)
    
    sns.heatmap(df_dist, annot=True, fmt=".2f", cmap="viridis", ax=eixos[1], cbar_kws={'label': 'Distância Euclidiana (Z-Score)'})
    eixos[1].set_title('Matriz de Distância Multidimensional (Fingerprint)', fontweight='bold')
    eixos[1].set_xlabel('Amostra de Referência')
    eixos[1].set_ylabel('Amostra de Referência')
    plt.setp(eixos[1].get_xticklabels(), rotation=45, ha="right")

    fig.tight_layout()
    fig.savefig(caminho_saida, bbox_inches='tight')
    plt.close(fig)