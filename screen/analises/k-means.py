
import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score

CAMINHO_DB = 'pibic_dados.duckdb'
DIR_FIGURAS = Path('figuras')
DIR_FIGURAS.mkdir(exist_ok=True)

# Mesmas features de CTC usadas nos modelos supervisionados -- quando você
# adicionar amostras de outros domínios, granulometria e DRX também
# poderão entrar aqui como features de agrupamento (hoje ficam de fora
# porque nos modelos supervisionados são ALVO, não features -- mas nada
# impede usá-las aqui, já que K-means não distingue feature de alvo).
FEATURES_CLUSTERING = ['ctc_consenso_meq_100g', 'ctc_razao_metodos']


def carregar_atributos(caminho_db=CAMINHO_DB):
    con = duckdb.connect(caminho_db, read_only=True)
    df = con.sql("SELECT * FROM atributos_ctc").df()
    con.close()
    return df


def escolher_k_pelo_cotovelo_e_silhueta(X, k_min=2, k_max=None):
    """
    Roda K-means pra vários valores de k e retorna inércia (método do
    cotovelo) e coeficiente de silhueta pra cada um. Com poucas amostras,
    k_max é limitado a n_amostras - 1 (silhueta não é definida pra k=n).
    """
    n = len(X)
    if k_max is None:
        k_max = max(k_min, n - 1)
    k_max = min(k_max, n - 1)

    resultados = []
    for k in range(k_min, k_max + 1):
        km = KMeans(n_clusters=k, n_init=10, random_state=42)
        rotulos = km.fit_predict(X)
        inercia = km.inertia_
        silhueta = silhouette_score(X, rotulos) if k < n else np.nan
        resultados.append({'k': k, 'inercia': inercia, 'silhueta': silhueta})
    return pd.DataFrame(resultados)


def plot_cotovelo_silhueta(df_k, caminho_saida):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.plot(df_k['k'], df_k['inercia'], 'o-')
    ax1.set_xlabel('k (nº de clusters)')
    ax1.set_ylabel('Inércia (soma dos quadrados intra-cluster)')
    ax1.set_title('Método do cotovelo')

    ax2.plot(df_k['k'], df_k['silhueta'], 'o-', color='darkorange')
    ax2.set_xlabel('k (nº de clusters)')
    ax2.set_ylabel('Coeficiente de silhueta')
    ax2.set_title('Silhueta (mais próximo de 1 = clusters mais separados)')

    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=200)
    plt.close(fig)


def plot_clusters(df, rotulos, features, caminho_saida):
    fig, ax = plt.subplots(figsize=(7, 5))
    cores_cluster = plt.cm.tab10(np.linspace(0, 1, len(set(rotulos))))
    for cluster_id in sorted(set(rotulos)):
        mascara = rotulos == cluster_id
        ax.scatter(df.loc[mascara, features[0]], df.loc[mascara, features[1]],
                   color=cores_cluster[cluster_id], label=f'Cluster {cluster_id}', s=100)
    for _, linha in df.iterrows():
        ax.annotate(linha['amostra'], (linha[features[0]], linha[features[1]]),
                    fontsize=8, xytext=(5, 5), textcoords='offset points')
    ax.set_xlabel(features[0])
    ax.set_ylabel(features[1])
    ax.set_title('K-means sobre features de CTC')
    ax.legend()
    fig.tight_layout()
    fig.savefig(caminho_saida, dpi=200)
    plt.close(fig)


def main():
    df = carregar_atributos()
    dados = df.dropna(subset=FEATURES_CLUSTERING).reset_index(drop=True)

    print(f"Amostras disponíveis pra clustering: {len(dados)} ({list(dados['amostra'])})")
    print("\nAVISO: todas as amostras atuais são bentonitas do mesmo estudo.")
    print("Os clusters abaixo são um teste de pipeline, não uma descoberta física.\n")

    X = StandardScaler().fit_transform(dados[FEATURES_CLUSTERING])

    df_k = escolher_k_pelo_cotovelo_e_silhueta(X)
    print(df_k.to_string(index=False))
    plot_cotovelo_silhueta(df_k, DIR_FIGURAS / 'kmeans_cotovelo_silhueta.png')

    # k melhor pela silhueta (ignorando NaN)
    k_escolhido = int(df_k.loc[df_k['silhueta'].idxmax(), 'k']) if df_k['silhueta'].notna().any() else 2
    print(f"\nk escolhido pela silhueta: {k_escolhido}")

    km = KMeans(n_clusters=k_escolhido, n_init=10, random_state=42)
    rotulos = km.fit_predict(X)
    dados['cluster'] = rotulos
    print(dados[['amostra', 'ctc_consenso_meq_100g', 'ctc_razao_metodos', 'fase_dominante_drx', 'cluster']])

    plot_clusters(dados, rotulos, FEATURES_CLUSTERING, DIR_FIGURAS / 'kmeans_clusters.png')

    con = duckdb.connect(CAMINHO_DB)
    con.execute("CREATE OR REPLACE TABLE clusters_kmeans AS SELECT * FROM dados")
    con.close()
    print(f"\ntabela 'clusters_kmeans' salva no banco. Figuras em: {DIR_FIGURAS.resolve()}")


if __name__ == '__main__':
    main()