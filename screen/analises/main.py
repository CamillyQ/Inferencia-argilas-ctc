import duckdb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from config import (
    CAMINHO_DB, ALVOS_GRANULOMETRIA, FEATURE_PRINCIPAL, 
    MODELOS_REGRESSAO_SINGLE, MODELOS_REGRESSAO_MULTI, 
    DIR_FIGURAS, ALVOS_FASES_MINERAIS
)
from modelos import loocv_regressao_granulometria, loocv_regressao_multialvo_fases
from geracao_graficos import (
    plot_composicao_fases, plot_heatmap_metricas, 
    plot_matriz_confusao_e_distancias, plot_real_vs_predito_dispersao, 
    plot_real_vs_predito_fases_minerais, gerar_tabela_detalhada_fases, 
    gerar_tabela_detalhada_single_target
)

def configurar_estilo_cientifico():
    """Define padronização estética para publicação científica."""
    plt.style.use('seaborn-v0_8-whitegrid')
    plt.rcParams.update({
        'font.family': 'sans-serif',
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 9,
        'figure.titlesize': 13,
        'figure.dpi': 300,
        'savefig.dpi': 300,
        'axes.spines.top': False,
        'axes.spines.right': False
    })

def carregar_atributos(caminho_db=CAMINHO_DB):
    con = duckdb.connect(caminho_db, read_only=True)
    df = con.sql("SELECT * FROM atributos_ctc").df()
    con.close()
    return df

def main():
    configurar_estilo_cientifico()
    df = carregar_atributos()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 300)

    # 1. REGRESSÃO: GRANULOMETRIA (COM DISPERSANTE)
    print("=" * 70)
    print("TAREFA 1: REGRESSÃO — Prever Granulometria (Com Dispersante)")
    print("=" * 70)
    metricas_granulometria = []
    previsoes_granulo_por_alvo = {}
    y_real_granulo_por_alvo = {}
    nomes_amostra_g = None
    y_real_dmedio = None
    previsoes_dmedio_dict = {}
    
    for alvo in ALVOS_GRANULOMETRIA:
        res, nomes_amostra_g, y_real_g, previsoes = loocv_regressao_granulometria(
            df, FEATURE_PRINCIPAL, alvo, MODELOS_REGRESSAO_SINGLE
        )
        metricas_granulometria.append(res)
        y_real_granulo_por_alvo[alvo] = y_real_g
        previsoes_granulo_por_alvo[alvo] = previsoes
        
        # Isolar diâmetro médio para o gráfico de dispersão
        if alvo == 'diametro_medio_um_com':
            previsoes_dmedio_dict = previsoes
            y_real_dmedio = y_real_g

    df_res_granulo = pd.concat(metricas_granulometria, ignore_index=True)
    print(df_res_granulo.groupby('modelo')['MAE'].mean().reset_index().sort_values('MAE').to_string(index=False))

    plot_heatmap_metricas(
        df_res_granulo, 'alvo', 'MAE', 'RMSE', 'R2',
        'Granulometria (Com Dispersante)', DIR_FIGURAS / 'metricas_heatmap_granulometria_com.png'
    )
    
    plot_real_vs_predito_dispersao(
        y_real_dmedio, previsoes_dmedio_dict,
        'Diâmetro Médio Com Dispersante (µm)', 'µm',
        DIR_FIGURAS / 'real_vs_predito_diametro_medio_com.png'
    )

    # 2. REGRESSÃO MULTI-ALVO: PORCENTAGENS DO DRX
    print("\n" + "=" * 70)
    print("TAREFA 2: REGRESSÃO MULTI-ALVO — Porcentagens das Fases Minerais (% DRX)")
    print("=" * 70)
    
    df_res_fases, nomes_amostra, Y_real_fases, previsoes_fases = loocv_regressao_multialvo_fases(
        df, FEATURE_PRINCIPAL, ALVOS_FASES_MINERAIS, MODELOS_REGRESSAO_MULTI
    )
    print(df_res_fases.groupby('modelo')['MAE (%)'].mean().reset_index().sort_values('MAE (%)').to_string(index=False))

    plot_heatmap_metricas(
        df_res_fases, 'fase_mineral', 'MAE (%)', 'RMSE (%)', 'R2',
        'Fases Minerais (DRX)', DIR_FIGURAS / 'metricas_heatmap_fases_minerais.png'
    )
    plot_composicao_fases(
        nomes_amostra, Y_real_fases, previsoes_fases, ALVOS_FASES_MINERAIS,
        DIR_FIGURAS / 'composicao_fases_real_vs_pred.png'
    )
    plot_real_vs_predito_fases_minerais(
        Y_real_fases, previsoes_fases, ALVOS_FASES_MINERAIS,
        DIR_FIGURAS / 'real_vs_predito_fases_minerais.png'
    )

    # 3. GERAÇÃO DAS TABELAS DETALHADAS
    # 3.1 Granulometria
    df_comparativo_granulo = gerar_tabela_detalhada_single_target(
        nomes_amostra=nomes_amostra_g,
        dict_y_real=y_real_granulo_por_alvo,
        dict_previsoes_por_alvo=previsoes_granulo_por_alvo,
        alvos=ALVOS_GRANULOMETRIA
    )

    print("\n--- TABELA COMPARATIVA DE GRANULOMETRIA ---")
    print(df_comparativo_granulo.to_string(index=False))

    # 3.2 Fases Minerais
    df_comparativo_fases = gerar_tabela_detalhada_fases(
        nomes_amostra=nomes_amostra,
        Y_real=Y_real_fases,
        previsoes_por_modelo=previsoes_fases,
        alvos_fases=ALVOS_FASES_MINERAIS,
    )

    print("\n--- TABELA COMPARATIVA DE FASES MINERAIS ---")
    print(df_comparativo_fases.to_string(index=False))

    # EXPORTAÇÃO EM CSV E EXCEL
    df_comparativo_granulo.to_csv(DIR_FIGURAS / "comparativo_granulometria.csv", index=False)
    df_comparativo_granulo.to_excel(DIR_FIGURAS / "comparativo_granulometria.xlsx", index=False)
    
    df_comparativo_fases.to_csv(DIR_FIGURAS / "comparativo_fases_minerais.csv", index=False)
    df_comparativo_fases.to_excel(DIR_FIGURAS / "comparativo_fases_minerais.xlsx", index=False)
    
    # PERSISTÊNCIA NO DUCKDB
    con = duckdb.connect(CAMINHO_DB)
    con.execute("CREATE OR REPLACE TABLE resultados_granulometria AS SELECT * FROM df_res_granulo")
    con.execute("CREATE OR REPLACE TABLE resultados_fases_minerais AS SELECT * FROM df_res_fases")
    con.execute("CREATE OR REPLACE TABLE comparativo_detalhado_granulometria AS SELECT * FROM df_comparativo_granulo")
    con.execute("CREATE OR REPLACE TABLE comparativo_detalhado_fases AS SELECT * FROM df_comparativo_fases")
    con.close()

    print("\n" + "=" * 70)
    print("PROCESSO CONCLUÍDO COM SUCESSO!")
    print(f"Figuras e tabelas salvas em: {DIR_FIGURAS.resolve()}")
    print("Tabelas atualizadas no DuckDB.")
    print("=" * 70)

if __name__ == "__main__":
    main()