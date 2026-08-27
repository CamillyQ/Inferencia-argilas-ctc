
import duckdb
import pandas as pd
import numpy as np

CAMINHO_DB = 'pibic_dados.duckdb'

CTC_REFERENCIA_MONTMORILONITA_PURA = 100.0


def carregar_dados(caminho_db):
    con = duckdb.connect(caminho_db, read_only=True)

    df_titulacao = con.sql("""
        SELECT a.nome AS amostra,
               AVG(c.ctc_meq_100g)     AS ctc_titulacao_media_meq_100g,
               STDDEV(c.ctc_meq_100g)  AS ctc_titulacao_std_meq_100g,
               COUNT(*)                AS ctc_titulacao_n_ensaios
        FROM ctc c JOIN amostras a ON c.amostra_id = a.amostra_id
        GROUP BY a.nome
    """).df()

    df_comparacao = con.sql("""
        SELECT a.nome AS amostra, cm.ctc_azul_metileno_meq_100g, cm.ctc_cmc_meq_100g
        FROM comparacao_metodos_ctc cm JOIN amostras a ON cm.amostra_id = a.amostra_id
    """).df()

    df_granulometria = con.sql("""
        SELECT a.nome AS amostra, g.condicao, g.d10_um, g.d50_um, g.d90_um, g.diametro_medio_um
        FROM granulometria_resumo g JOIN amostras a ON g.amostra_id = a.amostra_id
    """).df()

    df_picos = con.sql("""
        SELECT a.nome AS amostra, p.fase_mineral, p.quantificacao_pct
        FROM picos_drx p
        JOIN ensaio_drx e ON p.ensaio_id = e.ensaio_id
        JOIN amostras a ON e.amostra_id = a.amostra_id
    """).df().drop_duplicates()

    con.close()
    return df_titulacao, df_comparacao, df_granulometria, df_picos


def engenharia_features_ctc(df_titulacao, df_comparacao):
    """Constroi as features preditoras, todas derivadas de CTC."""
    df = df_titulacao.merge(df_comparacao, on='amostra', how='outer')

    # confiabilidade da medição por titulação (coef. de variação entre réplicas)
    df['ctc_titulacao_cv'] = df['ctc_titulacao_std_meq_100g'] / df['ctc_titulacao_media_meq_100g']

    # divergência entre métodos -- diagnóstico de interferência (matéria
    # orgânica / óxidos de Fe tendem a inflar o azul de metileno)
    df['ctc_diferenca_metodos_meq_100g'] = df['ctc_azul_metileno_meq_100g'] - df['ctc_cmc_meq_100g']
    df['ctc_razao_metodos'] = df['ctc_azul_metileno_meq_100g'] / df['ctc_cmc_meq_100g']

    # CTC de consenso: titulação como referência, azul de metileno como fallback
    df['ctc_consenso_meq_100g'] = df['ctc_titulacao_media_meq_100g'].fillna(df['ctc_azul_metileno_meq_100g'])

    # log: estabiliza variância, apropriado se a relação com propriedades
    # físicas (ex: área superficial específica) for multiplicativa
    df['ctc_log_meq_100g'] = np.log(df['ctc_consenso_meq_100g'])

    # teor de montmorilonita ESTIMADO via CTC (aproximação, não medição direta)
    df['mont_pct_estimado_via_ctc'] = (
        df['ctc_consenso_meq_100g'] / CTC_REFERENCIA_MONTMORILONITA_PURA
    ).clip(upper=1.0)

    # classificação por faixa de CTC (regra de domínio -- serve de baseline
    # físico pra comparar com os modelos de ML depois)
    def classificar(ctc):
        if pd.isna(ctc):
            return None
        if ctc < 40:
            return 'baixa_caulinitica_ilitica'
        if ctc < 60:
            return 'media_mista_interestratificada'
        return 'alta_esmectitica_bentonitica'

    df['classe_ctc_dominio'] = df['ctc_consenso_meq_100g'].apply(classificar)
    return df


def alvos_granulometria(df_granulometria):
    """
    Pivota a granulometria (agora com dimensão sem/com dispersante) em
    colunas largas com sufixo _sem / _com, e deriva a razão de floculação:
    o quanto a amostra "floca"/agrega em água pura, medida pela razão entre
    o diâmetro médio sem e com dispersante. O hexametafosfato de sódio
    desfaz agregados, então essa razão indica o grau de agregação natural
    da amostra -- fisicamente ligado à carga de superfície das lâminas do
    argilomineral, e portanto relacionado ao CTC.
    """
    pivot = df_granulometria.pivot(index='amostra', columns='condicao',
                                    values=['d10_um', 'd50_um', 'd90_um', 'diametro_medio_um'])
    pivot.columns = [f'{col}_{cond.replace("_dispersante", "")}' for col, cond in pivot.columns]
    pivot = pivot.reset_index()

    pivot['razao_floculacao_d50'] = pivot['d50_um_sem'] / pivot['d50_um_com']
    pivot['razao_floculacao_diametro_medio'] = pivot['diametro_medio_um_sem'] / pivot['diametro_medio_um_com']
    return pivot


def alvos_mineralogia(df_picos):
    """Corrige escala e deriva os alvos de composição mineral a partir do DRX."""
    soma = df_picos.groupby('amostra')['quantificacao_pct'].transform('sum')
    df_picos = df_picos.copy()
    df_picos.loc[soma > 5, 'quantificacao_pct'] = df_picos.loc[soma > 5, 'quantificacao_pct'] / 100

    fase_dominante = (
        df_picos.sort_values('quantificacao_pct', ascending=False)
        .groupby('amostra').first().reset_index()
        .rename(columns={'fase_mineral': 'fase_dominante_drx', 'quantificacao_pct': 'pct_fase_dominante_drx'})
    )

    composicao = df_picos.pivot_table(
        index='amostra', columns='fase_mineral', values='quantificacao_pct', fill_value=0
    ).add_prefix('pct_drx_').reset_index()

    return fase_dominante[['amostra', 'fase_dominante_drx', 'pct_fase_dominante_drx']], composicao


def montar_tabela_atributos(caminho_db=CAMINHO_DB):
    df_titulacao, df_comparacao, df_granulometria, df_picos = carregar_dados(caminho_db)

    df_features = engenharia_features_ctc(df_titulacao, df_comparacao)
    df_gran_pivot = alvos_granulometria(df_granulometria)
    df_fase_dominante, df_composicao = alvos_mineralogia(df_picos)

    df_atributos = (
        df_features
        .merge(df_gran_pivot, on='amostra', how='left')
        .merge(df_fase_dominante, on='amostra', how='left')
        .merge(df_composicao, on='amostra', how='left')
        .sort_values('amostra')
        .reset_index(drop=True)
    )
    return df_atributos


if __name__ == '__main__':
    df_atributos = montar_tabela_atributos()
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', 300)
    print(df_atributos)

    # checagem de consistência física: classe_ctc_dominio bate com a fase dominante do DRX?
    print()
    print("=== checagem: classe por CTC x fase dominante real (DRX) ===")
    print(df_atributos[['amostra', 'classe_ctc_dominio', 'fase_dominante_drx', 'pct_fase_dominante_drx']])

    con = duckdb.connect(CAMINHO_DB)
    con.execute("CREATE OR REPLACE TABLE atributos_ctc AS SELECT * FROM df_atributos")
    con.close()
    print("\ntabela 'atributos_ctc' salva no banco")