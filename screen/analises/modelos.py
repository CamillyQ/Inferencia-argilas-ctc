
import numpy as np
import pandas as pd
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
        resultados.append({'modelo': nome_modelo, 'alvo': alvo, 'MAE': mae, 'RMSE': rmse, 'R2': r2})
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