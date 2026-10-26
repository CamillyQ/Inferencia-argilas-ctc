import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from pathlib import Path

CAMINHO_DB = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "duckdb"
    / "pibic_dados.duckdb"
)

con = duckdb.connect(CAMINHO_DB)

# Ajuste 'nome_amostra' para o nome real da coluna identificadora da amostra
query = """
SELECT 
    amostra,
    pct_drx_Montmorilonita,
    pct_drx_Caulinita,
    pct_drx_Quartzo,
    pct_drx_Cristobalita,
    pct_drx_Nontronita,
    d10_um_com,
    d50_um_com,
    d90_um_com,
    ctc_consenso_meq_100g
FROM atributos_ctc
"""
df = con.execute(query).df()
con.close()

df["span_granulometrico"] = df["d90_um_com"] - df["d10_um_com"]

features = [
    "pct_drx_Montmorilonita",
    "pct_drx_Caulinita",
    "pct_drx_Quartzo",
    "pct_drx_Cristobalita",
    "pct_drx_Nontronita",
    "d50_um_com",
    "span_granulometrico",
    "ctc_consenso_meq_100g",  # EDA apenas — NÃO reusar cluster_id como feature preditiva de CTC
]

X = df[features].dropna().copy()
nomes = df.loc[X.index, "amostra"].values
n_amostras = X.shape[0]

print(f"n_amostras = {n_amostras}, n_features = {len(features)}")
if n_amostras < 3 * len(features):
    print("Aviso: n_amostras pequeno relativo ao nº de features — PCA/KMeans exploratórios, não robustos.")

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Teto explícito de componentes: no máx. n_amostras-1, e nunca mais que o necessário para 85%
max_componentes_possiveis = n_amostras - 1
pca_full = PCA(n_components=max_componentes_possiveis, random_state=42)
pca_full.fit(X_scaled)
cum_var_full = np.cumsum(pca_full.explained_variance_ratio_)
n_comp_85 = int(np.argmax(cum_var_full >= 0.85) + 1)

if n_comp_85 >= max_componentes_possiveis:
    print(f"Aviso: precisou de {n_comp_85}/{max_componentes_possiveis} componentes possíveis para 85% — "
          f"redução de dimensionalidade pouco efetiva com n={n_amostras}.")

pca = PCA(n_components=n_comp_85, random_state=42)
X_pca = pca.fit_transform(X_scaled)
print(f"Componentes retidas: {pca.n_components_} | Variância acumulada: {sum(pca.explained_variance_ratio_)*100:.2f}%")

# Escolha de k via silhouette (só k=2 e k=3 fazem sentido com n=6)
print("\nSilhouette score por k:")
melhores_k = {}
for k in range(2, min(4, n_amostras - 1) + 1):
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels_k = km.fit_predict(X_pca)
    score = silhouette_score(X_pca, labels_k)
    melhores_k[k] = score
    print(f"  k={k}: silhouette={score:.3f}")

n_clusters = max(melhores_k, key=melhores_k.get)
print(f"\nk escolhido por silhouette: {n_clusters}")

kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
X["cluster"] = kmeans.fit_predict(X_pca)

tamanhos = X["cluster"].value_counts().sort_index()
print("\nTamanho de cada cluster:")
print(tamanhos)
if (tamanhos == 1).any():
    print("Aviso: há cluster com 1 única amostra — provável outlier isolado, não um agrupamento genuíno.")

# Visualizações
sns.set_theme(style="whitegrid")
fig, axes = plt.subplots(1, 3, figsize=(19, 5))

cum_var = np.cumsum(pca.explained_variance_ratio_) * 100
axes[0].plot(range(1, len(cum_var) + 1), cum_var, marker="o", color="b", linestyle="--")
axes[0].axhline(y=85, color="r", linestyle=":", label="Corte 85%")
axes[0].set_title("Variância Explicada Acumulada (PCA)")
axes[0].set_xlabel("Número de Componentes")
axes[0].set_ylabel("Variância Explicada (%)")
axes[0].set_ylim(0, 105)
axes[0].legend()

sns.scatterplot(
    x=X_pca[:, 0], y=X_pca[:, 1], hue=X["cluster"], palette="Set2",
    style=X["cluster"], s=100, ax=axes[1],
)
for i, nome in enumerate(nomes):
    axes[1].annotate(nome, (X_pca[i, 0], X_pca[i, 1]), fontsize=8, xytext=(5, 5), textcoords="offset points")
axes[1].set_title(f"Clusters no Espaço $PC_1$ vs $PC_2$ (n={n_amostras})")
axes[1].set_xlabel(f"$PC_1$ ({pca.explained_variance_ratio_[0]*100:.1f}% var)")
axes[1].set_ylabel(f"$PC_2$ ({pca.explained_variance_ratio_[1]*100:.1f}% var)")

X_scaled_df = pd.DataFrame(X_scaled, columns=features)
X_scaled_df["cluster"] = X["cluster"].values
cluster_means = X_scaled_df.groupby("cluster").mean()

sns.heatmap(cluster_means, annot=True, cmap="coolwarm", fmt=".2f", ax=axes[2], cbar=True)
axes[2].set_title("Perfil Médio dos Clusters (Escala Z-score)")
axes[2].set_ylabel("Cluster")

plt.tight_layout()
plt.savefig("clusters_argilas.png", dpi=150)
plt.show()

loadings = pd.DataFrame(
    pca.components_.T,
    columns=[f"PC{i+1}" for i in range(pca.n_components_)],
    index=features,
)
print("\nCargas (loadings) por componente:")
print(loadings.sort_values(by="PC1", ascending=False))