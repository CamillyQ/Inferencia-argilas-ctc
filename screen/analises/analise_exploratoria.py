"""
Análise estatística descritiva e inferencial das propriedades das argilas:
- Estatística descritiva (média, desvio-padrão, min/max, mediana)
- Matrizes de correlação de Pearson (linear) e Spearman (monotônica, por postos)
- Testes de significância (valor-p) para cada par
- Gráficos de dispersão para os pares mais correlacionados
"""
import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from scipy.stats import pearsonr, spearmanr
from itertools import combinations
from pathlib import Path


CAMINHO_DB = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "duckdb"
    / "pibic_dados.duckdb"
)
DIR_FIGURAS = Path('figuras')
DIR_FIGURAS.mkdir(exist_ok=True)


PROPRIEDADES = [
    'ctc_consenso_meq_100g',
    'ctc_razao_metodos',
    'ctc_titulacao_cv',
    'd10_um_sem', 'd50_um_sem', 'd90_um_sem', 'diametro_medio_um_sem',
    'd10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com',
    'razao_floculacao_diametro_medio',
    'pct_fase_dominante_drx',
    'pct_drx_Caulinita', 'pct_drx_Montmorilonita',
    'pct_drx_Quartzo', 'pct_drx_Nontronita', 'pct_drx_Cristobalita',
]


def carregar_atributos(caminho_db=CAMINHO_DB):
    con = duckdb.connect(caminho_db, read_only=True)
    df = con.sql("SELECT * FROM atributos_ctc").df()
    con.close()
    return df


def estatistica_descritiva(df, colunas):
    desc = df[colunas].describe().T
    desc['n_valido'] = df[colunas].notna().sum()
    desc = desc[['n_valido', 'mean', 'std', 'min', '50%', 'max']]
    desc.columns = ['n', 'media', 'desvio_padrao', 'minimo', 'mediana', 'maximo']
    return desc.round(3)


def matriz_correlacao_com_pvalor(df, colunas, metodo):
    """
    Calcula a matriz de correlação (Pearson ou Spearman) e a matriz de
    valores-p correspondente, usando pares completos.
    """
    func = pearsonr if metodo == 'pearson' else spearmanr
    r_dict = {c: {c2: np.nan for c2 in colunas} for c in colunas}
    p_dict = {c: {c2: np.nan for c2 in colunas} for c in colunas}
    n_dict = {c: {c2: 0 for c2 in colunas} for c in colunas}

    for c in colunas:
        r_dict[c][c] = 1.0
        p_dict[c][c] = 0.0
        n_dict[c][c] = int(df[c].notna().sum())

    for c1, c2 in combinations(colunas, 2):
        pares = df[[c1, c2]].dropna()
        if len(pares) < 3:
            r, p = np.nan, np.nan
        else:
            r, p = func(pares[c1], pares[c2])
        r_dict[c1][c2] = r_dict[c2][c1] = r
        p_dict[c1][c2] = p_dict[c2][c1] = p
        n_dict[c1][c2] = n_dict[c2][c1] = len(pares)

    r_mat = pd.DataFrame(r_dict, index=colunas, columns=colunas)
    p_mat = pd.DataFrame(p_dict, index=colunas, columns=colunas)
    n_mat = pd.DataFrame(n_dict, index=colunas, columns=colunas)
    return r_mat, p_mat, n_mat


def plot_matriz_correlacao(r_mat, p_mat, titulo, caminho_saida, alpha=0.05):
    fig, ax = plt.subplots(figsize=(11, 9))
    mascara_sig = p_mat < alpha
    sns.heatmap(
        r_mat, annot=True, fmt='.2f', cmap='RdBu_r', vmin=-1, vmax=1,
        center=0, square=True, linewidths=0.5, cbar_kws={'label': 'coeficiente de correlação'},
        ax=ax,
    )

    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=200)
    plt.close(fig)


def listar_pares_mais_correlacionados(r_mat, p_mat, n_mat, top=15):
    pares = []
    for c1, c2 in combinations(r_mat.columns, 2):
        r = r_mat.loc[c1, c2]
        if pd.isna(r):
            continue
        pares.append({
            'variavel_1': c1, 'variavel_2': c2,
            'r': r, 'p_valor': p_mat.loc[c1, c2], 'n': n_mat.loc[c1, c2],
        })
    df_pares = pd.DataFrame(pares).sort_values('r', key=lambda s: s.abs(), ascending=False)
    return df_pares.head(top).reset_index(drop=True)


def plot_dispersao_pares(df, pares, caminho_saida, ncols=3):
    n = len(pares)
    nrows = -(-n // ncols)
    fig, eixos = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.8 * nrows), squeeze=False)

    for idx, (_, linha) in enumerate(pares.iterrows()):
        ax = eixos[idx // ncols][idx % ncols]
        c1, c2 = linha['variavel_1'], linha['variavel_2']
        dados = df[[c1, c2, 'amostra']].dropna()
        ax.scatter(dados[c1], dados[c2], color='#2563eb', s=60, zorder=3)
        for _, ponto in dados.iterrows():
            ax.annotate(ponto['amostra'], (ponto[c1], ponto[c2]), fontsize=6.5,
                        xytext=(3, 3), textcoords='offset points')
        ax.set_xlabel(c1, fontsize=8)
        ax.set_ylabel(c2, fontsize=8)
        ax.set_title(f"r={linha['r']:.2f}  p={linha['p_valor']:.3f}  (n={linha['n']})", fontsize=9)

    for idx in range(n, nrows * ncols):
        eixos[idx // ncols][idx % ncols].axis('off')

    fig.suptitle('Pares de propriedades mais correlacionados (Pearson)', fontsize=13)
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=200)
    plt.close(fig)


def main():
    df = carregar_atributos()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 300)

    print("=" * 70)
    print("ESTATÍSTICA DESCRITIVA")
    print("=" * 70)
    desc = estatistica_descritiva(df, PROPRIEDADES)
    print(desc)

    print()
    print("=" * 70)
    print("CORRELAÇÃO DE PEARSON (relação linear)")
    print("=" * 70)
    r_pearson, p_pearson, n_pearson = matriz_correlacao_com_pvalor(df, PROPRIEDADES, 'pearson')
    plot_matriz_correlacao(r_pearson, p_pearson, 'Correlação de Pearson entre propriedades das argilas',
                            DIR_FIGURAS / 'correlacao_pearson.png')

    print()
    print("=" * 70)
    print("CORRELAÇÃO DE SPEARMAN (relação monotônica, por postos)")
    print("=" * 70)
    r_spearman, p_spearman, n_spearman = matriz_correlacao_com_pvalor(df, PROPRIEDADES, 'spearman')
    plot_matriz_correlacao(r_spearman, p_spearman, 'Correlação de Spearman entre propriedades das argilas',
                            DIR_FIGURAS / 'correlacao_spearman.png')

    print()
    print("=" * 70)
    print("PARES MAIS CORRELACIONADOS (Pearson, |r| desc.)")
    print("=" * 70)
    top_pares = listar_pares_mais_correlacionados(r_pearson, p_pearson, n_pearson, top=15)
    print(top_pares.to_string(index=False))
    plot_dispersao_pares(df, top_pares.head(9), DIR_FIGURAS / 'dispersao_pares_top.png')

    con = duckdb.connect(CAMINHO_DB)
    con.execute("CREATE OR REPLACE TABLE correlacoes_pearson AS SELECT * FROM top_pares")
    con.close()

    print(f"\nfiguras salvas em: {DIR_FIGURAS.resolve()}")
    print("tabela 'correlacoes_pearson' salva no banco")


if __name__ == '__main__':
    main()