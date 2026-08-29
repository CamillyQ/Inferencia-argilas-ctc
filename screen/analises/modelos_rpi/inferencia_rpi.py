import joblib
import pandas as pd
from pathlib import Path

# Definicao dos nomes das variáveis
ALVOS_GRANULOMETRIA = ['d10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com']
ALVOS_FASES_MINERAIS = ['Montmorilonita', 'Caulinita', 'Quartzo', 'Cristobalita', 'Nontronita']

class PredictorRPi5:
    def __init__(self, caminho_pasta_modelos=None):
        pasta_atual = Path(__file__).resolve().parent

        if caminho_pasta_modelos is None:
            pasta = pasta_atual
        else:
            pasta = Path(caminho_pasta_modelos)


        caminho_granulo = pasta / "modelo_granulometria.joblib"
        caminho_fases = pasta / "modelo_fases.joblib"

        if not caminho_granulo.exists():
            raise FileNotFoundError(
                f"Modelo de granulometria não encontrado:\n"
                f"{caminho_granulo}"
            )

        if not caminho_fases.exists():
            raise FileNotFoundError(
                f"Modelo de fases minerais não encontrado:\n"
                f"{caminho_fases}"
            )

        self.modelos_granulo = joblib.load(caminho_granulo)
        self.modelo_fases = joblib.load(caminho_fases)

    def prever(self, X_atributos):
        """
        Recebe um DataFrame com as features de medição da CTC
        e retorna um dicionário com os DataFrames de predição.
        """
        # 1. Predição de Granulometria (µm)
        pred_granulo = {}
        for alvo, modelo in self.modelos_granulo.items():
            pred_granulo[alvo] = modelo.predict(X_atributos)
        df_granulo = pd.DataFrame(pred_granulo)

        # 2. Predição de Fases Minerais (%)
        matriz_fases = self.modelo_fases.predict(X_atributos)
        df_fases = pd.DataFrame(matriz_fases, columns=ALVOS_FASES_MINERAIS)

        return {
            "granulometria": df_granulo,
            "fases_minerais": df_fases
        }

if __name__ == "__main__":
    predictor = PredictorRPi5(caminho_pasta_modelos=None)
    
    # Substitua 'X_novas_medicoes' pelo DataFrame contendo os atributos medidos da amostra
    # Exemplo sintético com 1 amostra:
    # X_novas_medicoes = pd.DataFrame([[...]]) 
    
    # predicoes = predictor.prever(X_novas_medicoes)
    # print("--- Granulometria Prevista (µm) ---")
    # print(predicoes["granulometria"])
    # print("\n--- Fases Minerais Previstas (%) ---")
    # print(predicoes["fases_minerais"])