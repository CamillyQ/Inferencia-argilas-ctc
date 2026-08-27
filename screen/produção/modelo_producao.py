
import duckdb
import joblib
import json
from datetime import datetime
from pathlib import Path
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

CAMINHO_DB = Path(__file__).resolve().parent.parent.parent / 'screen' / 'database' / 'duckdb' / 'pibic_dados.duckdb'
DIR_MODELOS = Path(__file__).resolve().parent / 'modelos_producao'
DIR_MODELOS.mkdir(exist_ok=True)

FEATURE = 'ctc_consenso_meq_100g'

ALVO_CLASSIFICACAO = 'fase_dominante_drx'
ALVOS_REGRESSAO = [
    'd10_um_sem', 'd50_um_sem', 'd90_um_sem', 'diametro_medio_um_sem',
    'd10_um_com', 'd50_um_com', 'd90_um_com', 'diametro_medio_um_com',
    'razao_floculacao_diametro_medio',
]

USAR_RANDOM_FOREST = False


def _carregar_xy(alvo, caminho_db=CAMINHO_DB):
    con = duckdb.connect(caminho_db, read_only=True)
    df = con.sql(
        f'SELECT amostra, "{FEATURE}", "{alvo}" FROM atributos_ctc '
        f'WHERE "{FEATURE}" IS NOT NULL AND "{alvo}" IS NOT NULL'
    ).df()
    con.close()
    return df


def _nome_arquivo(alvo):
    """fase_dominante_drx -> modelo_fase_dominante_drx.joblib, etc."""
    return f"modelo_{alvo}"


def _treinar_e_exportar_um(alvo, eh_classificacao):
    df = _carregar_xy(alvo)
    X = df[[FEATURE]].values
    y = df[alvo].values

    if eh_classificacao:
        modelo = (RandomForestClassifier(n_estimators=100, max_depth=2, random_state=42)
                  if USAR_RANDOM_FOREST else DecisionTreeClassifier(max_depth=2, random_state=42))
    else:
        modelo = (RandomForestRegressor(n_estimators=100, max_depth=2, random_state=42)
                  if USAR_RANDOM_FOREST else DecisionTreeRegressor(max_depth=2, random_state=42))

    modelo.fit(X, y)
    tipo_modelo = type(modelo).__name__

    base = _nome_arquivo(alvo)
    caminho_modelo = DIR_MODELOS / f'{base}.joblib'
    joblib.dump(modelo, caminho_modelo)

    metadados = {
        'tipo_modelo': tipo_modelo,
        'feature': FEATURE,
        'alvo': alvo,
        'eh_classificacao': eh_classificacao,
        'n_amostras_treino': len(df),
        'amostras_treino': df[FEATURE].round(3).tolist(),
        'data_treino': datetime.now().isoformat(timespec='seconds'),
    }
    if eh_classificacao:
        metadados['classes'] = sorted(modelo.classes_.tolist())

    with open(DIR_MODELOS / f'{base}_metadados.json', 'w', encoding='utf-8') as f:
        json.dump(metadados, f, ensure_ascii=False, indent=2)

    print(f"  {alvo}: {tipo_modelo}, {len(df)} amostras -> {caminho_modelo.name}")
    return metadados


def treinar_e_exportar():
    print("=== classificação ===")
    _treinar_e_exportar_um(ALVO_CLASSIFICACAO, eh_classificacao=True)

    print("\n=== regressão (granulometria) ===")
    for alvo in ALVOS_REGRESSAO:
        _treinar_e_exportar_um(alvo, eh_classificacao=False)

    print(f"\nTodos os modelos salvos em: {DIR_MODELOS.resolve()}")


if __name__ == '__main__':
    treinar_e_exportar()