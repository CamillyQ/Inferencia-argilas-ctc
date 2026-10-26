import duckdb
import joblib
import pandas as pd
from pathlib import Path
from sklearn.svm import SVR
from sklearn.tree import DecisionTreeRegressor
from config import (
    CAMINHO_DB, FEATURE_PRINCIPAL, 
    ALVOS_GRANULOMETRIA, ALVOS_FASES_MINERAIS
)
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier

def exportar_modelos():

    con = duckdb.connect(CAMINHO_DB, read_only=True)
    df = con.sql("SELECT * FROM atributos_ctc").df()
    con.close()

    X = df[FEATURE_PRINCIPAL]
    
    modelos_granulometria = {}
    for alvo in ALVOS_GRANULOMETRIA:
        y = df[alvo]
        random = RandomForestRegressor(n_estimators=100, max_depth=2, random_state=42)
        random.fit(X, y)
        modelos_granulometria[alvo] = random

    # 2. Treinar Árvore de Decisão Multi-Alvo para Fases Minerais
    Y_fases = df[ALVOS_FASES_MINERAIS]
    modelo_fases = DecisionTreeRegressor(random_state=42, max_depth=2)
    modelo_fases.fit(X, Y_fases)

    # 3. Salvar arquivos serializados (.joblib)
    pasta_destino = Path("modelos_rpi")
    pasta_destino.mkdir(exist_ok=True)

    joblib.dump(modelos_granulometria, pasta_destino / "modelo_granulometria.joblib")
    joblib.dump(modelo_fases, pasta_destino / "modelo_fases.joblib")
    
    print(f"Modelos exportados com sucesso para: {pasta_destino.resolve()}")

if __name__ == "__main__":
    exportar_modelos()