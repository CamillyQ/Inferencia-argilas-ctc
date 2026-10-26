"""
Pipeline de análise de Machine Learning para propriedades de argilas
bentoníticas -- treino/avaliação via Leave-One-Out CV (adequado para
bases de dados pequenas, como as ~6-40 amostras deste projeto) e
geração de todas as visualizações de resultados (correlação,
dispersão de pares, heatmaps de métricas, real vs. predito).

Uso típico:
    df = carregar_dados_duckdb(CAMINHO_DB, tabela="atributos_ctc")
    executar_analise_completa(df, pasta_saida="resultados_ml")
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import duckdb
from pathlib import Path

from sklearn.base import clone
from sklearn.model_selection import LeaveOneOut
from sklearn.multioutput import MultiOutputRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.svm import SVR
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


# ──────────────────────────────────────────────────────────────────
# Definição dos modelos
# ──────────────────────────────────────────────────────────────────

def obter_modelos_regressao_simples(seed=42):
    """Modelos para regressão de alvo único (ex: cada variável de
    granulometria separadamente). Todos suportam saída 1D nativamente."""
    return {
        'Regressão Linear': LinearRegression(),
        'Ridge': Ridge(alpha=1.0, random_state=seed),
        'KNN (k=2)': KNeighborsRegressor(n_neighbors=2),
        'Árvore de Decisão': DecisionTreeRegressor(random_state=seed, max_depth=2),
        'Random Forest': RandomForestRegressor(
            n_estimators=200, random_state=seed, max_depth=2
        ),
        'SVR (kernel linear)': make_pipeline(
            StandardScaler(), SVR(kernel='linear')
        ),
        'Rede Neural (MLP)': make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(16, 8),
                activation='relu',
                max_iter=5000,
                random_state=seed,
            ),
        ),
    }


def obter_modelos_regressao_multialvo(seed=42):
    """Modelos para regressão multi-saída (ex: as 5 frações de fase
    mineral simultaneamente). LinearRegression, Ridge, KNN, árvores e
    Random Forest suportam multioutput nativamente no scikit-learn.
    SVR não suporta -- precisa ser envolvido em MultiOutputRegressor,
    que treina um SVR independente por alvo. MLPRegressor já suporta
    multioutput nativamente."""
    return {
        'Regressão Linear': LinearRegression(),
        'Ridge': Ridge(alpha=1.0, random_state=seed),
        'KNN (k=2)': KNeighborsRegressor(n_neighbors=2),
        'Árvore de Decisão': DecisionTreeRegressor(random_state=seed, max_depth=2),
        'Random Forest': RandomForestRegressor(
            n_estimators=200, random_state=seed, max_depth=2
        ),
        'SVR (kernel linear)': MultiOutputRegressor(
            make_pipeline(StandardScaler(), SVR(kernel='linear'))
        ),
        'Rede Neural (MLP)': make_pipeline(
            StandardScaler(),
            MLPRegressor(
                hidden_layer_sizes=(16, 8),
                activation='relu',
                max_iter=5000,
                random_state=seed,
            ),
        ),
    }


# ──────────────────────────────────────────────────────────────────
# LOOCV -- alvo único (ex: cada variável de granulometria)
# ──────────────────────────────────────────────────────────────────

def normalizar_porcentagens(y_pred):
    y_clip = np.clip(y_pred, 0, None)
    somas = y_clip.sum(axis=1, keepdims=True)
    somas[somas == 0] = 1.0
    return (y_clip / somas) * 100.0


def loocv_regressao_granulometria(df, features, alvo, modelos):
    dados = df.dropna(subset=features + [alvo]).reset_index(drop=True)
    X = dados[features].values
    y = dados[alvo].values
    nomes_amostra = dados['amostra'].values

    loo = LeaveOneOut()
    resultados = []
    previsoes_por_modelo = {}

    for nome_modelo, modelo_base in modelos.items():
        y_pred = np.zeros_like(y, dtype=float)
        for i_treino, i_teste in loo.split(X):
            modelo = clone(modelo_base)
            modelo.fit(X[i_treino], y[i_treino])
            y_pred[i_teste] = modelo.predict(X[i_teste]).ravel()

        mae = mean_absolute_error(y, y_pred)
        rmse = np.sqrt(mean_squared_error(y, y_pred))
        r2 = r2_score(y, y_pred)
        resultados.append({
            'modelo': nome_modelo, 'alvo': alvo,
            'MAE': mae, 'RMSE': rmse, 'R2': r2,
        })
        previsoes_por_modelo[nome_modelo] = y_pred

    return pd.DataFrame(resultados), nomes_amostra, y, previsoes_por_modelo


def loocv_regressao_multialvo_fases(df, features, alvos, modelos):
    dados = df.dropna(subset=features + alvos).reset_index(drop=True)
    X = dados[features].values
    Y_real = dados[alvos].values * 100.0
    nomes_amostra = dados['amostra'].values

    loo = LeaveOneOut()
    resultados = []
    previsoes_por_modelo = {}

    for nome_modelo, modelo_base in modelos.items():
        Y_pred = np.zeros_like(Y_real, dtype=float)
        for i_treino, i_teste in loo.split(X):
            modelo = clone(modelo_base)
            modelo.fit(X[i_treino], Y_real[i_treino])
            Y_pred[i_teste] = modelo.predict(X[i_teste])

        Y_pred_norm = normalizar_porcentagens(Y_pred)
        previsoes_por_modelo[nome_modelo] = Y_pred_norm

        for idx, alvo in enumerate(alvos):
            y_r = Y_real[:, idx]
            y_p = Y_pred_norm[:, idx]
            mae = mean_absolute_error(y_r, y_p)
            rmse = np.sqrt(mean_squared_error(y_r, y_p))
            r2 = r2_score(y_r, y_p)
            resultados.append({
                'modelo': nome_modelo,
                'fase_mineral': alvo,
                'MAE (%)': mae,
                'RMSE (%)': rmse,
                'R2': r2,
            })

    return pd.DataFrame(resultados), nomes_amostra, Y_real, previsoes_por_modelo


# ──────────────────────────────────────────────────────────────────
# Visualização: correlação (Pearson / Spearman)
# ──────────────────────────────────────────────────────────────────

def plot_correlacao(df, colunas, metodo='pearson', caminho_saida=None):
    """metodo: 'pearson' ou 'spearman'."""
    corr = df[colunas].corr(method=metodo)
    mask_diagonal = np.eye(len(corr), dtype=bool)

    fig, ax = plt.subplots(figsize=(1.1 * len(colunas), 1.0 * len(colunas)))
    sns.heatmap(
        corr, mask=mask_diagonal, annot=True, fmt=".2f",
        cmap="RdBu_r", vmin=-1, vmax=1, square=True,
        cbar_kws={'label': 'coeficiente de correlação'}, ax=ax,
    )
    titulo = "Pearson" if metodo == "pearson" else "Spearman"
    ax.set_title(f"Correlação de {titulo} entre propriedades das argilas")
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()
    return corr


def plot_dispersao_pares_top(df, colunas, coluna_rotulo, metodo='pearson',
                              n_pares=9, caminho_saida=None):
    """Identifica os N pares de colunas mais correlacionados (em valor
    absoluto) e plota um grid de dispersão com r, p-valor e rótulos
    de cada ponto (nome da amostra)."""
    from scipy.stats import pearsonr, spearmanr
    func_corr = pearsonr if metodo == 'pearson' else spearmanr

    pares = []
    for i, c1 in enumerate(colunas):
        for c2 in colunas[i + 1:]:
            sub = df[[c1, c2]].dropna()
            if len(sub) < 3:
                continue
            r, p = func_corr(sub[c1], sub[c2])
            pares.append((abs(r), r, p, c1, c2, len(sub)))

    pares.sort(key=lambda x: x[0], reverse=True)
    pares_top = pares[:n_pares]

    n_cols = 3
    n_rows = int(np.ceil(len(pares_top) / n_cols))
    fig, eixos = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
    eixos = np.array(eixos).reshape(-1)

    for ax, (_, r, p, c1, c2, n) in zip(eixos, pares_top):
        sub = df[[c1, c2, coluna_rotulo]].dropna()
        ax.scatter(sub[c1], sub[c2], s=90, color="tab:blue", edgecolor="k", zorder=3)
        for _, linha in sub.iterrows():
            ax.annotate(str(linha[coluna_rotulo]), (linha[c1], linha[c2]),
                        fontsize=8, xytext=(4, 4), textcoords="offset points")
        ax.set_xlabel(c1)
        ax.set_ylabel(c2)
        ax.set_title(f"r={r:.2f}  p={p:.3f}  (n={n})")

    for ax in eixos[len(pares_top):]:
        ax.axis("off")

    fig.suptitle(f"Pares de propriedades mais correlacionados ({metodo.capitalize()})",
                 fontsize=14)
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()
    return pares_top


# ──────────────────────────────────────────────────────────────────
# Visualização: heatmap de métricas (MAE / RMSE / R²)
# ──────────────────────────────────────────────────────────────────

def plot_heatmap_metricas(df_resultados, coluna_alvo, titulo_geral,
                           caminho_saida=None):
    """df_resultados precisa ter colunas: 'modelo', coluna_alvo,
    'MAE'/'MAE (%)', 'RMSE'/'RMSE (%)', 'R2'."""
    col_mae = "MAE (%)" if "MAE (%)" in df_resultados.columns else "MAE"
    col_rmse = "RMSE (%)" if "RMSE (%)" in df_resultados.columns else "RMSE"

    pivot_mae = df_resultados.pivot(index='modelo', columns=coluna_alvo, values=col_mae)
    pivot_rmse = df_resultados.pivot(index='modelo', columns=coluna_alvo, values=col_rmse)
    pivot_r2 = df_resultados.pivot(index='modelo', columns=coluna_alvo, values='R2')

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(22, 6))

    sns.heatmap(pivot_mae, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax1,
                cbar_kws={'label': col_mae})
    ax1.set_title(f"Erro Médio Absoluto ({col_mae})")

    sns.heatmap(pivot_rmse, annot=True, fmt=".2f", cmap="YlOrRd", ax=ax2,
                cbar_kws={'label': col_rmse})
    ax2.set_title(f"Raiz do Erro Quadrático Médio ({col_rmse})")

    sns.heatmap(pivot_r2, annot=True, fmt=".2f", cmap="Blues", ax=ax3,
                vmin=-1, vmax=1, cbar_kws={'label': 'R²'})
    ax3.set_title("Coeficiente de Determinação (R²)")

    for ax in (ax1, ax2, ax3):
        ax.set_ylabel("Modelo")
        ax.set_xlabel("")
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")

    fig.suptitle(titulo_geral, fontsize=15, fontweight="bold")
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()


# ──────────────────────────────────────────────────────────────────
# Visualização: Real vs. Predito -- grid por modelo (alvo único)
# ──────────────────────────────────────────────────────────────────

def plot_real_vs_predito_grid(y_real, previsoes_por_modelo, titulo_geral,
                               unidade="", caminho_saida=None):
    n_modelos = len(previsoes_por_modelo)
    n_cols = 3
    n_rows = int(np.ceil(n_modelos / n_cols))
    fig, eixos = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows))
    eixos = np.array(eixos).reshape(-1)

    lim_min = min(y_real.min(), min(p.min() for p in previsoes_por_modelo.values()))
    lim_max = max(y_real.max(), max(p.max() for p in previsoes_por_modelo.values()))
    margem = (lim_max - lim_min) * 0.05

    for ax, (nome_modelo, y_pred) in zip(eixos, previsoes_por_modelo.items()):
        mae = mean_absolute_error(y_real, y_pred)
        r2 = r2_score(y_real, y_pred)

        ax.scatter(y_real, y_pred, s=70, color="tab:blue", edgecolor="k", zorder=3)
        ax.plot([lim_min - margem, lim_max + margem],
                [lim_min - margem, lim_max + margem],
                "r--", label="Ideal (y = x)")
        ax.set_xlim(lim_min - margem, lim_max + margem)
        ax.set_ylim(lim_min - margem, lim_max + margem)
        ax.set_xlabel(f"Valor Real ({unidade})" if unidade else "Valor Real")
        ax.set_ylabel(f"Valor Previsto ({unidade})" if unidade else "Valor Previsto")
        ax.set_title(f"{nome_modelo}\nR² = {r2:.2f} | MAE = {mae:.2f} {unidade}")
        ax.legend(fontsize=8)
        ax.grid(alpha=0.3)

    for ax in eixos[n_modelos:]:
        ax.axis("off")

    fig.suptitle(titulo_geral, fontsize=15, fontweight="bold")
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()


# ──────────────────────────────────────────────────────────────────
# Visualização: Real vs. Predito por fase mineral (multi-alvo,
# um painel por fase, todos os modelos sobrepostos e coloridos)
# ──────────────────────────────────────────────────────────────────

def plot_real_vs_predito_por_fase(Y_real, previsoes_por_modelo, alvos,
                                   caminho_saida_prefixo=None):
    cores = plt.cm.tab10(np.linspace(0, 1, len(previsoes_por_modelo)))

    for idx_alvo, alvo in enumerate(alvos):
        fig, ax = plt.subplots(figsize=(9, 7))
        y_r = Y_real[:, idx_alvo]

        for cor, (nome_modelo, Y_pred) in zip(cores, previsoes_por_modelo.items()):
            y_p = Y_pred[:, idx_alvo]
            mae = mean_absolute_error(y_r, y_p)
            ax.scatter(y_r, y_p, s=80, color=cor, edgecolor="k",
                       label=f"{nome_modelo} (MAE: {mae:.1f}%)", zorder=3)

        lim_min = min(y_r.min(), min(p[:, idx_alvo].min() for p in previsoes_por_modelo.values()))
        lim_max = max(y_r.max(), max(p[:, idx_alvo].max() for p in previsoes_por_modelo.values()))
        margem = max((lim_max - lim_min) * 0.05, 1)
        ax.plot([lim_min - margem, lim_max + margem],
                [lim_min - margem, lim_max + margem], "r--", label="Ideal (y = x)")

        ax.set_xlabel("Valor Real (%)")
        ax.set_ylabel("Valor Previsto (%)")
        ax.set_title(f"Fase Mineral: {alvo.replace('pct_drx_', '')}", fontweight="bold")
        ax.legend(loc="center left", bbox_to_anchor=(1.02, 0.5), fontsize=9)
        ax.grid(alpha=0.3)
        plt.tight_layout()
        if caminho_saida_prefixo:
            plt.savefig(f"{caminho_saida_prefixo}_{alvo}.png", dpi=150, bbox_inches="tight")
        plt.show()


# ──────────────────────────────────────────────────────────────────
# Visualização: Real vs. Predito -- UM ÚNICO modelo, todas as fases
# agregadas no mesmo painel, coloridas por fase mineral (reproduz o
# formato "Real vs Predito — Árvore de Decisão (Fases Minerais DRX)")
# ──────────────────────────────────────────────────────────────────

def plot_real_vs_predito_modelo_unico_multialvo(Y_real, previsoes_por_modelo,
                                                 alvos, nome_modelo,
                                                 caminho_saida=None):
    """Agrega TODAS as fases minerais num único gráfico de dispersão
    para um modelo específico (ex: 'Árvore de Decisão'), colorindo os
    pontos por fase mineral e anotando R²/MAE/RMSE calculados sobre o
    conjunto agregado (todas as fases empilhadas)."""
    if nome_modelo not in previsoes_por_modelo:
        raise ValueError(
            f"Modelo '{nome_modelo}' não encontrado. "
            f"Disponíveis: {list(previsoes_por_modelo.keys())}"
        )

    Y_pred = previsoes_por_modelo[nome_modelo]
    cores = plt.cm.tab10(np.linspace(0, 1, len(alvos)))

    fig, ax = plt.subplots(figsize=(9, 8))
    for cor, idx_alvo, alvo in zip(cores, range(len(alvos)), alvos):
        y_r = Y_real[:, idx_alvo]
        y_p = Y_pred[:, idx_alvo]
        ax.scatter(y_r, y_p, s=90, color=cor, edgecolor="k",
                   label=alvo.replace("pct_drx_", ""), zorder=3)

    y_r_flat = Y_real.ravel()
    y_p_flat = Y_pred.ravel()
    mae = mean_absolute_error(y_r_flat, y_p_flat)
    rmse = np.sqrt(mean_squared_error(y_r_flat, y_p_flat))
    r2 = r2_score(y_r_flat, y_p_flat)

    lim_min = min(y_r_flat.min(), y_p_flat.min())
    lim_max = max(y_r_flat.max(), y_p_flat.max())
    margem = (lim_max - lim_min) * 0.05
    ax.plot([lim_min - margem, lim_max + margem],
            [lim_min - margem, lim_max + margem],
            "r--", label="Linha Ideal (1:1)")

    ax.text(
        0.03, 0.97,
        f"$R^2$ = {r2:.4f}\nMAE = {mae:.2f}%\nRMSE = {rmse:.2f}%",
        transform=ax.transAxes, va="top", ha="left", fontsize=12,
        bbox=dict(boxstyle="round", facecolor="white", edgecolor="gray", alpha=0.9),
    )

    ax.set_xlabel("Valor Real (%)")
    ax.set_ylabel("Valor Predito (%)")
    ax.set_title(f"Real vs Predito — {nome_modelo} (Fases Minerais DRX)",
                 fontweight="bold", fontsize=14)
    ax.legend(title="Fase Mineral", loc="lower right", fontsize=9)
    ax.grid(alpha=0.3)
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()


# ──────────────────────────────────────────────────────────────────
# Visualização: composição de fases -- real vs. cada modelo, por amostra
# ──────────────────────────────────────────────────────────────────

def plot_composicao_fases_barras(nomes_amostra, Y_real, previsoes_por_modelo,
                                  alvos, caminho_saida=None):
    """Barras horizontais empilhadas: para cada amostra, mostra a
    composição REAL e a composição PREVISTA por cada modelo,
    permitindo comparação visual direta (mesmo formato das figuras
    já usadas no projeto)."""
    amostras_unicas = pd.unique(nomes_amostra)
    nomes_fases = [a.replace("pct_drx_", "") for a in alvos]
    n_amostras = len(amostras_unicas)

    fig, eixos = plt.subplots(n_amostras, 1, figsize=(11, 2.2 * n_amostras))
    if n_amostras == 1:
        eixos = [eixos]

    for ax, amostra in zip(eixos, amostras_unicas):
        idx = np.where(nomes_amostra == amostra)[0]
        linhas_rotulo = ["Real"] + list(previsoes_por_modelo.keys())
        matriz = [Y_real[idx].mean(axis=0)]
        for nome_modelo in previsoes_por_modelo:
            matriz.append(previsoes_por_modelo[nome_modelo][idx].mean(axis=0))
        matriz = np.array(matriz)

        esquerda = np.zeros(len(linhas_rotulo))
        cores = plt.cm.tab10(np.linspace(0, 1, len(nomes_fases)))
        for j, fase in enumerate(nomes_fases):
            ax.barh(linhas_rotulo, matriz[:, j], left=esquerda,
                    color=cores[j], label=fase if ax is eixos[0] else None)
            esquerda += matriz[:, j]

        ax.set_xlim(0, 100)
        ax.set_title(f"Amostra: {amostra}", fontweight="bold")
        ax.invert_yaxis()

    eixos[0].legend(loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=9)
    fig.supxlabel("Porcentagem (%)")
    plt.tight_layout()
    if caminho_saida:
        plt.savefig(caminho_saida, dpi=150, bbox_inches="tight")
    plt.show()


# ──────────────────────────────────────────────────────────────────
# Carregamento a partir do DuckDB
# ──────────────────────────────────────────────────────────────────

def carregar_dados_duckdb(caminho_banco, tabela="atributos_ctc", filtro_sql=None):
    """Lê a tabela de atributos direto do arquivo DuckDB e devolve um
    DataFrame pandas. `filtro_sql`, se informado, é concatenado como
    cláusula WHERE (ex: "amostra IS NOT NULL").

    Usa `duckdb.connect(caminho_banco, read_only=True)` -- read_only
    evita disputa de lock com qualquer outro processo que também
    esteja com o arquivo aberto (ex: seu pipeline de ingestão)."""
    query = f"SELECT * FROM {tabela}"
    if filtro_sql:
        query += f" WHERE {filtro_sql}"

    with duckdb.connect(str(caminho_banco), read_only=True) as con:
        df = con.execute(query).fetchdf()

    print(f"[DUCKDB] {len(df)} linha(s) carregada(s) de '{tabela}' em {caminho_banco}")
    print(f"[DUCKDB] Colunas disponíveis: {list(df.columns)}")
    return df


# ──────────────────────────────────────────────────────────────────
# Execução completa (orquestração de tudo acima)
# ──────────────────────────────────────────────────────────────────

def executar_analise_completa(df, pasta_saida="resultados_ml"):
    """Roda a análise de correlação + LOOCV para granulometria (com
    dispersante) e fases minerais + todas as visualizações, salvando
    tudo em `pasta_saida`. Ajuste as listas de features/alvos abaixo
    conforme as colunas reais do seu DataFrame."""
    pasta = Path(pasta_saida)
    pasta.mkdir(exist_ok=True, parents=True)

    colunas_correlacao = [
        'ctc_consenso_meq_100g', 'ctc_razao_metodos', 'ctc_titulacao_cv',
        'd10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com',
        'razao_floculacao_diametro_medio', 'pct_fase_dominante_drx',
        'pct_drx_Caulinita', 'pct_drx_Montmorilonita', 'pct_drx_Quartzo',
        'pct_drx_Nontronita', 'pct_drx_Cristobalita',
    ]
    colunas_correlacao = [c for c in colunas_correlacao if c in df.columns]

    plot_correlacao(df, colunas_correlacao, metodo='pearson',
                     caminho_saida=pasta / "correlacao_pearson.png")
    plot_correlacao(df, colunas_correlacao, metodo='spearman',
                     caminho_saida=pasta / "correlacao_spearman.png")
    plot_dispersao_pares_top(df, colunas_correlacao, coluna_rotulo='amostra',
                              metodo='pearson', n_pares=9,
                              caminho_saida=pasta / "dispersao_pares_top.png")

    features = ['ctc_consenso_meq_100g']

    # --- Granulometria COM dispersante ---
    modelos = obter_modelos_regressao_simples()
    alvos_granulo_com = [
        'd10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com'
    ]
    alvos_granulo_com = [a for a in alvos_granulo_com if a in df.columns]

    resultados_geral = []
    previsoes_diametro_medio = None
    y_real_diametro_medio = None
    for alvo in alvos_granulo_com:
        df_res, nomes, y_real, previsoes = loocv_regressao_granulometria(
            df, features, alvo, modelos
        )
        resultados_geral.append(df_res)
        if alvo == 'diametro_medio_um_com':
            previsoes_diametro_medio = previsoes
            y_real_diametro_medio = y_real

    df_resultados_granulo_com = pd.concat(resultados_geral, ignore_index=True)
    plot_heatmap_metricas(
        df_resultados_granulo_com, coluna_alvo='alvo',
        titulo_geral="Granulometria (Com Dispersante) — Avaliação de Métricas",
        caminho_saida=pasta / "metricas_heatmap_granulometria_com.png",
    )

    if previsoes_diametro_medio is not None:
        plot_real_vs_predito_grid(
            y_real_diametro_medio, previsoes_diametro_medio,
            "Comparativo Real vs. Previsto: Diâmetro Médio Com Dispersante (µm)",
            unidade="µm",
            caminho_saida=pasta / "real_vs_predito_diametro_medio_com.png",
        )

    # --- Fases minerais (multi-alvo) ---
    modelos_multialvo = obter_modelos_regressao_multialvo()
    alvos_fases = [
        'pct_drx_Montmorilonita', 'pct_drx_Caulinita', 'pct_drx_Quartzo',
        'pct_drx_Cristobalita', 'pct_drx_Nontronita',
    ]
    alvos_fases = [a for a in alvos_fases if a in df.columns]
    df_resultados_fases, nomes_amostra_fases, Y_real, previsoes_fases = (
        loocv_regressao_multialvo_fases(df, features, alvos_fases, modelos_multialvo)
    )
    plot_heatmap_metricas(df_resultados_fases, coluna_alvo='fase_mineral',
                           titulo_geral="Fases Minerais (DRX) — Avaliação de Métricas",
                           caminho_saida=pasta / "metricas_heatmap_fases_minerais.png")

    plot_real_vs_predito_por_fase(Y_real, previsoes_fases, alvos_fases,
                                   caminho_saida_prefixo=pasta / "real_vs_predito_fase")

    # Gráfico único agregado por modelo -- Árvore de Decisão é o
    # destaque padrão (menor MAE/maior R² nas fases minerais segundo
    # a análise anterior), mas qualquer chave de `modelos_multialvo`
    # pode ser passada aqui.
    plot_real_vs_predito_modelo_unico_multialvo(
        Y_real, previsoes_fases, alvos_fases, nome_modelo="Árvore de Decisão",
        caminho_saida=pasta / "real_vs_predito_arvore_decisao.png",
    )

    plot_composicao_fases_barras(nomes_amostra_fases, Y_real, previsoes_fases,
                                  alvos_fases,
                                  caminho_saida=pasta / "composicao_fases_real_vs_pred.png")

    print(f"[ANÁLISE] Concluída. Figuras salvas em: {pasta.resolve()}")
    return {
        'granulometria_com': df_resultados_granulo_com,
        'fases_minerais': df_resultados_fases,
    }


if __name__ == "__main__":
    CAMINHO_DB = (
        Path(__file__).resolve().parent.parent
        / "database"
        / "duckdb"
        / "pibic_dados.duckdb"
    )

    df = carregar_dados_duckdb(CAMINHO_DB, tabela="atributos_ctc")
    executar_analise_completa(df, pasta_saida="resultados_ml")