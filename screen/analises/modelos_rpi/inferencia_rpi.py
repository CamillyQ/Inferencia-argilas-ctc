import joblib
import pandas as pd
from pathlib import Path

# Definir nomes das variáveis
ALVOS_GRANULOMETRIA = ['d10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com']
ALVOS_FASES_MINERAIS = ['Montmorilonita', 'Caulinita', 'Quartzo', 'Cristobalita', 'Nontronita']

class PredictorRPi5:
    def __init__(self, caminho_pasta_modelos="modelos_rpi"):
        pasta = Path(caminho_pasta_modelos)
        
        # Carregar modelos pre-treinados
        self.modelos_granulo = joblib.load(pasta / "modelos_granulometria_svr.joblib")
        self.modelo_fases = joblib.load(pasta / "modelo_fases_arvore.joblib")

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

# Exemplo prático de execução no Raspberry Pi 5
if __name__ == "__main__":
    predictor = PredictorRPi5(caminho_pasta_modelos="modelos_rpi")
    
    # Substitua 'X_novas_medicoes' pelo DataFrame contendo os atributos medidos da amostra
    # Exemplo sintético com 1 amostra:
    # X_novas_medicoes = pd.DataFrame([[...]]) 
    
    # predicoes = predictor.prever(X_novas_medicoes)
    # print("--- Granulometria Prevista (µm) ---")
    # print(predicoes["granulometria"])
    # print("\n--- Fases Minerais Previstas (%) ---")
    # print(predicoes["fases_minerais"])