import pandas as pd
import numpy as np
import datetime
import duckdb

_CORRECOES = {
    'CLOISISTE': 'CLOSITE',
    'T2 AMARELA': 'T1 AMARELA',
    'CLOSITE NA+': 'CLOSITE', 
}

_NOMES_CANONICOS = {
    'BENTOGEL': 'Bentogel',
    'BRASGEL': 'Brasgel',
    'CHOCOBOFE': 'Chocobofe',
    'CHOCOLATE': 'Chocolate',
    'CLOSITE': 'Closite',
    'VERDE LODO': 'Verde Lodo',
    'T1 CLARA': 'T1 Clara',
    'T1 AMARELA': 'T1 Amarela',
}


def normalizar_amostra(nome):
    """Recebe qualquer grafia da amostra e devolve o nome canônico."""
    if pd.isna(nome):
        return None
    chave = ' '.join(str(nome).strip().upper().split())
    chave = _CORRECOES.get(chave, chave)
    return _NOMES_CANONICOS.get(chave, str(nome).strip())

AMOSTRAS_EXCLUIDAS = {'T1 Clara', 'T1 Amarela'}


def excluir_amostras(df, coluna='amostra'):
    """Remove linhas cuja amostra (já normalizada) está em AMOSTRAS_EXCLUIDAS."""
    return df[~df[coluna].isin(AMOSTRAS_EXCLUIDAS)].reset_index(drop=True)


def parse_ctc(caminho_arquivo):
    """
    Lê a aba CTC. As colunas de cada bloco de amostra são detectadas
    dinamicamente (procurando o texto 'Ensaio' na linha de sub-cabeçalho),
    em vez de assumir posições fixas -- a planilha já teve uma coluna de
    espaçamento removida entre uma versão e outra, o que quebrava silenciosamente
    a leitura do bloco direito.
    """
    raw = pd.read_excel(caminho_arquivo, sheet_name='CTC', header=None)
    registros = []
    for inicio in range(1, raw.shape[0], 6):
        linha_header = inicio + 1
        if linha_header >= raw.shape[0]:
            continue
        colunas_inicio_bloco = [
            c for c in range(raw.shape[1])
            if str(raw.iat[linha_header, c]).strip().upper() == 'ENSAIO'
        ]
        for col_amostra in colunas_inicio_bloco:
            col_volume, col_conc, col_massa, col_ctc = (col_amostra + 1, col_amostra + 2, col_amostra + 3, col_amostra + 4)
            nome_amostra = raw.iat[inicio, col_amostra]
            if pd.isna(nome_amostra):
                continue
            for linha in range(inicio + 2, inicio + 5):
                if linha >= raw.shape[0]:
                    continue
                registros.append({
                    'amostra': normalizar_amostra(nome_amostra),
                    'ensaio': raw.iat[linha, col_amostra],
                    'volume_ml': raw.iat[linha, col_volume],
                    'concentracao_mol_l': raw.iat[linha, col_conc],
                    'massa_amostra_g': raw.iat[linha, col_massa],
                    'ctc_meq_100g': raw.iat[linha, col_ctc],
                })
    df = pd.DataFrame(registros)
    for col in ['volume_ml', 'concentracao_mol_l', 'massa_amostra_g', 'ctc_meq_100g']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna().reset_index(drop=True)
    df['ensaio'] = df['ensaio'].astype(int)
    return df


def parse_granulometria_resumo(caminho_arquivo):
    """
    Lê a aba 'resultados granulometria'. Desde a atualização da planilha,
    ela tem DOIS blocos lado a lado: granulometria SEM dispersante
    (hexametafosfato de sódio) e COM dispersante -- os blocos são
    detectados dinamicamente pela coluna com o texto 'Amostras'.
    T1 Clara e T1 Amarela não têm medição com dispersante (vêm como '-'
    na planilha, viram NaN aqui).
    """
    raw = pd.read_excel(caminho_arquivo, sheet_name='resultados granulometria', header=None)
    linha_header = 3
    colunas_bloco = [c for c in range(raw.shape[1]) if str(raw.iat[linha_header, c]).strip() == 'Amostras']
    condicoes = ['sem_dispersante', 'com_dispersante']

    blocos = []
    for col_amostra, condicao in zip(colunas_bloco, condicoes):
        cols = list(range(col_amostra, col_amostra + 5))
        dados = raw.iloc[linha_header + 1:, cols].copy()
        dados.columns = ['amostra', 'd10_um', 'd50_um', 'd90_um', 'diametro_medio_um']
        dados = dados.dropna(subset=['amostra']).reset_index(drop=True)
        dados['amostra'] = dados['amostra'].apply(normalizar_amostra)
        dados['condicao'] = condicao
        blocos.append(dados)

    df = pd.concat(blocos, ignore_index=True)
    for col in ['d10_um', 'd50_um', 'd90_um', 'diametro_medio_um']:
        df[col] = pd.to_numeric(df[col].replace('-', np.nan), errors='coerce')
    return df


def _to_numero_granulometria(valor):
    """Converte célula (str, float, ou datetime corrompido pelo autocorretor do Excel) em float."""
    if pd.isna(valor):
        return np.nan
    if isinstance(valor, (pd.Timestamp, datetime.datetime, datetime.date)):
        # Excel autocorrigiu "dia.mes" pra data -> reconstrói o número original
        dia, mes = valor.day, valor.month
        return float(f"{dia}.{mes:02d}")
    if isinstance(valor, str):
        valor = valor.strip().replace(',', '.')
        if valor in ('-', ''):
            return np.nan
        try:
            return float(valor)
        except ValueError:
            return np.nan
    return float(valor)


def _parse_curva_granulometria(caminho_arquivo, aba, condicao):
    """
    Lê uma aba de distribuição granulométrica (formato: blocos de 4 colunas
    por amostra -- separador, x, Q3 [vol. cumulativo], q3 [vol. incremental]).
    As colunas de cada bloco são detectadas dinamicamente (onde a linha de
    cabeçalho tem o texto 'x'), não por posição fixa.
    """
    raw = pd.read_excel(caminho_arquivo, sheet_name=aba, header=None)
    linha_header = 2
    linha_inicio_dados = 4
    colunas_x = [c for c in range(raw.shape[1]) if str(raw.iat[linha_header, c]).strip() == 'x']

    blocos = []
    for col_x in colunas_x:
        col_q3, col_q3min = col_x + 1, col_x + 2
        nome_amostra = raw.iat[1, col_x]
        if pd.isna(nome_amostra):
            continue
        dados = raw.iloc[linha_inicio_dados:, [col_x, col_q3, col_q3min]].copy()
        dados.columns = ['diametro_um', 'volume_cumulativo_pct', 'volume_incremental_pct']
        dados['amostra'] = normalizar_amostra(nome_amostra)
        blocos.append(dados)

    df = pd.concat(blocos, ignore_index=True)
    for col in ['diametro_um', 'volume_cumulativo_pct', 'volume_incremental_pct']:
        df[col] = df[col].apply(_to_numero_granulometria)
    df = df.dropna(subset=['diametro_um']).reset_index(drop=True)
    df['condicao'] = condicao
    return df


def parse_granulometria_distribuicao(caminho_arquivo):
    """
    Une as curvas de distribuição granulométrica sem e com dispersante
    (hexametafosfato de sódio) numa única tabela longa, diferenciadas
    pela coluna 'condicao'.
    """
    df_sem = _parse_curva_granulometria(caminho_arquivo, 'granulometria sem (NaPO3)6)', 'sem_dispersante')
    df_com = _parse_curva_granulometria(caminho_arquivo, 'granulometria com (NaPO3)6) - 1', 'com_dispersante')
    df = pd.concat([df_sem, df_com], ignore_index=True)
    df = df.sort_values(['amostra', 'condicao', 'diametro_um']).reset_index(drop=True)
    df = df[['amostra', 'condicao'] + [c for c in df.columns if c not in ('amostra', 'condicao')]]
    return df


def parse_drx(caminho_arquivo):
    raw = pd.read_excel(caminho_arquivo, sheet_name='DRX ', header=None)
    registros = []
    amostra_atual = None
    ficha_atual= None
    quant_atual = None
    for i in range(raw.shape[0]):
        primeira_col = raw.iat[i, 1]
        two_theta = raw.iat[i, 2]

        if pd.notna(primeira_col) and pd.isna(two_theta) and \
                i + 1 < raw.shape[0] and raw.iat[i + 1, 1] == 'Fase mineral':
            amostra_atual = normalizar_amostra(primeira_col)
            continue
        if primeira_col == 'Fase mineral':
            continue
        
        if pd.isna(two_theta):
            continue

        if pd.notna(raw.iat[i, 5]):
            ficha_atual = raw.iat[i, 5]
        if pd.notna(raw.iat[i, 6]):
            quant_atual = raw.iat[i, 6]
        
        registros.append({
            'amostra': amostra_atual,
            'fase_mineral': primeira_col,
            'two_theta': two_theta,
            'distancia_interplanar_ang': raw.iat[i, 3],
            'plano_cristalografico': raw.iat[i, 4],
            'ficha_identificacao': ficha_atual,
            'quantificacao_pct': quant_atual,
        })
    df = pd.DataFrame(registros)
    df['fase_mineral'] = df['fase_mineral'].ffill()  # picos secundários da mesma fase não repetem o nome
    for col in ['two_theta', 'distancia_interplanar_ang', 'quantificacao_pct']:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['amostra', 'two_theta']).reset_index(drop=True)
    return df


def parse_comparacao_metodos(caminho_arquivo):
    raw = pd.read_excel(caminho_arquivo, sheet_name='comparação entre os métodos', header=None)
    df = raw.iloc[3:9, 1:4].copy()
    df.columns = ['amostra', 'ctc_azul_metileno_meq_100g', 'ctc_cmc_meq_100g']
    df['amostra'] = df['amostra'].apply(normalizar_amostra)
    for col in ['ctc_azul_metileno_meq_100g', 'ctc_cmc_meq_100g']:
       
        df[col] = pd.to_numeric(df[col], errors='coerce')
    df = df.dropna(subset=['amostra']).reset_index(drop=True)
    return df


def montar_amostras(*dataframes):
    """Monta a tabela dimensão: um id substituto (surrogate key) para cada nome de amostra."""
    nomes = sorted(set().union(*[set(df['amostra'].dropna()) for df in dataframes]))
    return pd.DataFrame({
        'amostra_id': range(1, len(nomes) + 1),
        'nome': nomes,
    })


def montar_ensaio_drx_e_picos(df_drx_bruto, df_amostras):
    """
    Separa o resultado bruto de parse_drx (1 linha por pico, ainda com o
    nome da amostra) em duas tabelas:
      - ensaio_drx: 1 linha por amostra que passou por DRX (o ensaio em si)
      - picos_drx: 1 linha por pico, referenciando ensaio_id (não amostra_id
        diretamente) — porque o pico pertence ao ensaio, e é o ensaio que
        pertence à amostra. Isso deixa explícito que há 1 ensaio de DRX por
        amostra hoje, mas permite no futuro ter mais de um ensaio pra mesma
        amostra (reanálise, reescaneamento) sem ambiguidade de a qual
        ensaio cada pico pertence.
    """
    amostras_com_drx = sorted(df_drx_bruto['amostra'].dropna().unique())
    df_ensaio_drx = pd.DataFrame({
        'ensaio_id': range(1, len(amostras_com_drx) + 1),
        'amostra': amostras_com_drx,
    }).merge(df_amostras.rename(columns={'nome': 'amostra'}), on='amostra', how='left')

    df_picos_drx = df_drx_bruto.merge(
        df_ensaio_drx[['ensaio_id', 'amostra']], on='amostra', how='left'
    ).drop(columns=['amostra']).reset_index(drop=True)
    df_picos_drx.insert(0, 'id', range(1, len(df_picos_drx) + 1))
    colunas = ['id', 'ensaio_id'] + [c for c in df_picos_drx.columns if c not in ('id', 'ensaio_id')]
    df_picos_drx = df_picos_drx[colunas]

    df_ensaio_drx = df_ensaio_drx.drop(columns=['amostra'])[['ensaio_id', 'amostra_id']]

    return df_ensaio_drx, df_picos_drx


def adicionar_amostra_id(df, df_amostras):
    """
    Troca a coluna de texto 'amostra' pelo id substituto correspondente
    (join contra a tabela dimensão df_amostras), remove a coluna de texto,
    e acrescenta um 'id' sequencial próprio da linha (chave primária da
    tabela fato — necessário pra ferramentas como o DBeaver conseguirem
    editar/identificar linhas individualmente, já que amostra_id se repete).
    """
    df = df.merge(
        df_amostras.rename(columns={'nome': 'amostra'}),
        on='amostra',
        how='left',
    )
    df = df.drop(columns=['amostra']).reset_index(drop=True)
    df.insert(0, 'id', range(1, len(df) + 1))
    # reordena: id, amostra_id, ...demais colunas
    colunas = ['id', 'amostra_id'] + [c for c in df.columns if c not in ('id', 'amostra_id')]
    return df[colunas]


def preparar_dataframes(caminho_arquivo):
    df_ctc = excluir_amostras(parse_ctc(caminho_arquivo))
    df_gran_resumo = excluir_amostras(parse_granulometria_resumo(caminho_arquivo))
    df_gran_dist = excluir_amostras(parse_granulometria_distribuicao(caminho_arquivo))
    df_drx_bruto = excluir_amostras(parse_drx(caminho_arquivo))
    df_comparacao = excluir_amostras(parse_comparacao_metodos(caminho_arquivo))
    df_amostras = montar_amostras(df_ctc, df_gran_resumo, df_gran_dist, df_drx_bruto, df_comparacao)

    df_ensaio_drx, df_picos_drx = montar_ensaio_drx_e_picos(df_drx_bruto, df_amostras)

    # substitui o nome da amostra pelo id nas demais tabelas fato
    df_ctc = adicionar_amostra_id(df_ctc, df_amostras)
    df_gran_resumo = adicionar_amostra_id(df_gran_resumo, df_amostras)
    df_gran_dist = adicionar_amostra_id(df_gran_dist, df_amostras)
    df_comparacao = adicionar_amostra_id(df_comparacao, df_amostras)

    return df_amostras, df_gran_resumo, df_gran_dist, df_ensaio_drx, df_picos_drx, df_ctc, df_comparacao


_TIPO_DUCKDB = {
    'int64': 'BIGINT',
    'int32': 'INTEGER',
    'float64': 'DOUBLE',
    'object': 'VARCHAR',
    'bool': 'BOOLEAN',
    'datetime64[ns]': 'TIMESTAMP',
}


def _schema_sql(df, id_coluna='id'):
    """Gera a lista 'coluna TIPO, coluna TIPO, ...' a partir dos dtypes do DataFrame."""
    partes = []
    for col, dtype in df.dtypes.items():
        if col in ('amostra_id', 'ensaio_id'):
            # sempre INTEGER, pra bater com o tipo da coluna referenciada pela FK
            tipo = 'INTEGER'
        else:
            tipo = _TIPO_DUCKDB.get(str(dtype), 'VARCHAR')
        sufixo = ' PRIMARY KEY' if col == id_coluna else ''
        partes.append(f'"{col}" {tipo}{sufixo}')
    return ", ".join(partes)


def salvar_dataframes_no_duckdb(df_amostras, tabelas, caminho_db='pibic_dados.db'):
    """
    Conecta ao DuckDB e persiste os DataFrames Pandas em tabelas.
    'amostras' é criada primeiro, com PRIMARY KEY em amostra_id.

    'tabelas' é uma lista de tuplas (nome_tabela, df, coluna_fk, tabela_pai, coluna_pai, id_coluna),
    na ORDEM em que devem ser criadas — uma tabela só pode ser criada depois
    da tabela que ela referencia (ex: picos_drx depende de ensaio_drx, que
    depende de amostras). id_coluna é o nome da coluna que é PRIMARY KEY
    dessa tabela (normalmente 'id', mas em ensaio_drx é a própria 'ensaio_id').

    """
    con = duckdb.connect(caminho_db)

    # apaga na ordem inversa (filha antes da mãe), pra não violar FK no DROP
    for nome_tabela, *_ in reversed(tabelas):
        con.execute(f"DROP TABLE IF EXISTS {nome_tabela}")
    con.execute("DROP TABLE IF EXISTS amostras")

    con.execute("""
        CREATE TABLE amostras (
            amostra_id INTEGER PRIMARY KEY,
            nome VARCHAR NOT NULL UNIQUE
        )
    """)
    con.execute("INSERT INTO amostras SELECT * FROM df_amostras")
    print(f"Tabela 'amostras' criada com {len(df_amostras)} linhas.")

    for nome_tabela, df, coluna_fk, tabela_pai, coluna_pai, id_coluna in tabelas:
        # id_coluna é a PK própria da tabela; a coluna de FK é só referência
        # (pode ser a mesma coluna quando a FK já É a PK, como em ensaio_drx)
        schema = _schema_sql(df, id_coluna=id_coluna)
        con.execute(f"""
            CREATE TABLE {nome_tabela} (
                {schema},
                FOREIGN KEY ({coluna_fk}) REFERENCES {tabela_pai}({coluna_pai})
            )
        """)
        con.execute(f"INSERT INTO {nome_tabela} SELECT * FROM df")
        print(f"Tabela '{nome_tabela}' criada com {len(df)} linhas.")

    con.close()
    print(f"\nBanco de dados salvo em: {caminho_db}")

if __name__ == '__main__':
    import sys
    caminho = sys.argv[1] if len(sys.argv) > 1 else 'pibic 2025_2026 OK.xlsx'
    df_amostras, df_gran_resumo, df_gran_dist, df_ensaio_drx, df_picos_drx, df_ctc, df_comparacao = preparar_dataframes(caminho)
    print("\n=== AMOSTRAS ===")
    print(df_amostras)

    print("\n=== GRANULOMETRIA RESUMO ===")
    print(df_gran_resumo)

    print("\n=== GRANULOMETRIA DISTRIBUIÇÃO ===")
    print(df_gran_dist)

    print("\n=== ENSAIO DRX ===")
    print(df_ensaio_drx)

    print("\n=== PICOS DRX ===")
    print(df_picos_drx)

    print("\n=== CTC ===")
    print(df_ctc)

    print("\n=== COMPARAÇÃO DE MÉTODOS CTC ===")
    print(df_comparacao)
    for nome, df in [
        ('amostras', df_amostras), ('granulometria_resumo', df_gran_resumo),
        ('granulometria_distribuicao', df_gran_dist), ('ensaio_drx', df_ensaio_drx),
        ('picos_drx', df_picos_drx), ('ctc', df_ctc), ('comparacao_metodos_ctc', df_comparacao),
    ]:
        print(f'{nome}: {df.shape[0]} linhas, colunas = {list(df.columns)}')

    # ordem importa: uma tabela só pode vir depois da que ela referencia
    # (nome_tabela, df, coluna_fk, tabela_pai, coluna_pai, id_coluna)
    tabelas = [
        ('granulometria_resumo', df_gran_resumo, 'amostra_id', 'amostras', 'amostra_id', 'id'),
        ('granulometria_distribuicao', df_gran_dist, 'amostra_id', 'amostras', 'amostra_id', 'id'),
        ('ctc', df_ctc, 'amostra_id', 'amostras', 'amostra_id', 'id'),
        ('comparacao_metodos_ctc', df_comparacao, 'amostra_id', 'amostras', 'amostra_id', 'id'),
        ('ensaio_drx', df_ensaio_drx, 'amostra_id', 'amostras', 'amostra_id', 'ensaio_id'),
        ('picos_drx', df_picos_drx, 'ensaio_id', 'ensaio_drx', 'ensaio_id', 'id'),
    ]

    # 3. Persiste tudo no DuckDB (amostras vai separado, é a dimensão raiz)
    salvar_dataframes_no_duckdb(df_amostras, tabelas, caminho_db='pibic_dados.duckdb')