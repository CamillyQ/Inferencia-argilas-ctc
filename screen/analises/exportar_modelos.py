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

def exportar_modelos():

    con = duckdb.connect(CAMINHO_DB, read_only=True)
    df = con.sql("SELECT * FROM atributos_ctc").df()
    con.close()

    X = df[FEATURE_PRINCIPAL]

    # 1. Treinar SVR para cada alvo de Granulometria
    modelos_granulometria = {}
    for alvo in ALVOS_GRANULOMETRIA:
        y = df[alvo]
        svr = SVR(kernel='linear')
        svr.fit(X, y)
        modelos_granulometria[alvo] = svr

    # 2. Treinar Árvore de Decisão Multi-Alvo para Fases Minerais
    Y_fases = df[ALVOS_FASES_MINERAIS]
    modelo_fases = DecisionTreeRegressor(random_state=42)
    modelo_fases.fit(X, Y_fases)

    # 3. Salvar arquivos serializados (.joblib)
    pasta_destino = Path("modelos_rpi")
    pasta_destino.mkdir(exist_ok=True)

    joblib.dump(modelos_granulometria, pasta_destino / "modelos_granulometria_svr.joblib")
    joblib.dump(modelo_fases, pasta_destino / "modelo_fases_arvore.joblib")
    
    print(f"Modelos exportados com sucesso para: {pasta_destino.resolve()}")

if __name__ == "__main__":
    exportar_modelos()