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

DIR_FIGURAS = Path("./figuras")
CAMINHO_DB = (
    Path(__file__).resolve().parent.parent
    / "database"
    / "duckdb"
    / "pibic_dados.duckdb"
)
DIR_FIGURAS.mkdir(exist_ok=True)
FEATURE_PRINCIPAL = ['ctc_consenso_meq_100g']

ALVOS_GRANULOMETRIA = [
    'd10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com',
]

ALVOS_FASES_MINERAIS = [
    'pct_drx_Montmorilonita',
    'pct_drx_Caulinita',
    'pct_drx_Quartzo',
    'pct_drx_Cristobalita',
    'pct_drx_Nontronita',
]

_MLP_REG_KWARGS = dict(hidden_layer_sizes=(64, 64), max_iter=5000, random_state=42)
_MLP_CLF_KWARGS = dict(hidden_layer_sizes=(64, 64), max_iter=5000, random_state=42)

MODELOS_REGRESSAO_SINGLE = {
    'Regressão Linear': LinearRegression(),
    'Ridge': Ridge(alpha=1.0),
    'KNN (k=2)': KNeighborsRegressor(n_neighbors=2),
    'Árvore de Decisão': DecisionTreeRegressor(max_depth=2, random_state=42),
    'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=2, random_state=42),
    'SVR (kernel linear)': make_pipeline(StandardScaler(), SVR(kernel='linear')),
    'Rede Neural (MLP)': make_pipeline(StandardScaler(), MLPRegressor(**_MLP_REG_KWARGS)),
}

MODELOS_REGRESSAO_MULTI = {
    'Regressão Linear': LinearRegression(),
    'Ridge': Ridge(alpha=1.0),
    'KNN (k=2)': KNeighborsRegressor(n_neighbors=2),
    'Árvore de Decisão': DecisionTreeRegressor(max_depth=2, random_state=42),
    'Random Forest': RandomForestRegressor(n_estimators=100, max_depth=2, random_state=42),
    'SVR (kernel linear)': MultiOutputRegressor(make_pipeline(StandardScaler(), SVR(kernel='linear'))),
    'Rede Neural (MLP)': make_pipeline(StandardScaler(), MLPRegressor(**_MLP_REG_KWARGS)),
}