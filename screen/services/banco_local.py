import sqlite3
import csv
from pathlib import Path
from datetime import datetime, date
import uuid

CAMINHO_BANCO_LOCAL = Path(__file__).resolve().parent.parent / "dados_ensaios.db"


def obter_conexao():
    conn = sqlite3.connect(CAMINHO_BANCO_LOCAL)
    conn.row_factory = sqlite3.Row  # permite acessar colunas por nome
    return conn


def _coluna_existe(cursor, tabela, nome_coluna):
    cursor.execute(f"PRAGMA table_info({tabela})")
    return nome_coluna in [linha[1] for linha in cursor.fetchall()]



def inicializar_banco():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ensaios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_hora TEXT NOT NULL,
            massa_amostra_g REAL,
            cmc_mol_l REAL,
            volume_cmc_mL REAL,
            ctc_meq_100g REAL,
            d10_um REAL,
            d50_um REAL,
            d90_um REAL,
            diametro_medio_um REAL,
            montmorilonita_pct REAL,
            caulinita_pct REAL,
            quartzo_pct REAL,
            cristobalita_pct REAL,
            nontronita_pct REAL
        )
    """)

    for coluna, definicao in [
        ("amostra_nome", "TEXT"),
        ("tipo_argila", "TEXT"),
        ("uuid_sync", "TEXT"),
        ("sincronizado", "INTEGER DEFAULT 0"),
    ]:
        if not _coluna_existe(cursor, "ensaios", coluna):
            cursor.execute(f"ALTER TABLE ensaios ADD COLUMN {coluna} {definicao}")

    # índice único -- garante que o mesmo ensaio nunca seja inserido 2x
    # no D1 mesmo que o sync_client rode a mesma linha por engano
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_ensaios_uuid_sync
        ON ensaios(uuid_sync)
    """)

    conn.commit()
    conn.close()


def salvar_ensaio(resultado, ctc_final, df_granulo, df_fases, amostra_nome=None, tipo_argila=None):
    g = df_granulo.iloc[0]
    f = df_fases.iloc[0]
    identificador = str(uuid.uuid4())

    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ensaios (
            data_hora, amostra_nome, massa_amostra_g, cmc_mol_l, volume_cmc_mL,
            ctc_meq_100g, tipo_argila, uuid_sync, sincronizado,
            d10_um, d50_um, d90_um, diametro_medio_um,
            montmorilonita_pct, caulinita_pct, quartzo_pct, cristobalita_pct, nontronita_pct
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        amostra_nome,
        resultado.get("massa_amostra_g"),
        resultado.get("cmc"),
        resultado.get("volume_cmc_mL"),
        ctc_final,
        tipo_argila,
        identificador,
        float(g["d10_um_com"]), float(g["d50_um_com"]),
        float(g["d90_um_com"]), float(g["diametro_medio_um_com"]),
        float(f["Montmorilonita"]), float(f["Caulinita"]),
        float(f["Quartzo"]), float(f["Cristobalita"]), float(f["Nontronita"]),
    ))
    conn.commit()
    conn.close()


def listar_ensaios_pendentes_sync():
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ensaios WHERE sincronizado = 0")
    linhas = cursor.fetchall()
    conn.close()
    return [dict(linha) for linha in linhas]


def marcar_como_sincronizado(uuid_sync):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("UPDATE ensaios SET sincronizado = 1 WHERE uuid_sync = ?", (uuid_sync,))
    conn.commit()
    conn.close()

def _linha_para_dict(linha):
    """Traduz os nomes de coluna do banco pras chaves que a tela de
    Histórico espera (ex: 'ctc_meq_100g' -> 'ctc'), e converte
    data_hora de string pra datetime de verdade."""
    d = dict(linha)
    try:
        data_hora = datetime.strptime(d.get("data_hora"), "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        data_hora = d.get("data_hora")

    return {
        "id": d.get("id"),
        "data_hora": data_hora,
        "amostra": d.get("amostra_nome") or "—",
        "massa_g": d.get("massa_amostra_g"),
        "cmc": d.get("cmc_mol_l"),
        "ctc": d.get("ctc_meq_100g"),
        "classificacao": d.get("tipo_argila") or "—",
        "d10_um": d.get("d10_um"),
        "d50_um": d.get("d50_um"),
        "d90_um": d.get("d90_um"),
        "diametro_medio_um": d.get("diametro_medio_um"),
        "montmorilonita_pct": d.get("montmorilonita_pct"),
        "caulinita_pct": d.get("caulinita_pct"),
        "quartzo_pct": d.get("quartzo_pct"),
        "cristobalita_pct": d.get("cristobalita_pct"),
        "nontronita_pct": d.get("nontronita_pct"),
    }


def listar_ensaios(filtro_texto=None, data_inicio=None, data_fim=None):
    """Ensaios mais recentes primeiro, filtrando por nome de amostra
    (busca parcial) e por intervalo de data quando informados."""
    conn = obter_conexao()
    cursor = conn.cursor()

    condicoes, parametros = [], []

    if filtro_texto:
        condicoes.append("amostra_nome LIKE ? COLLATE NOCASE")
        parametros.append(f"%{filtro_texto}%")
    if data_inicio:
        condicoes.append("date(data_hora) >= date(?)")
        parametros.append(str(data_inicio))
    if data_fim:
        condicoes.append("date(data_hora) <= date(?)")
        parametros.append(str(data_fim))

    query = "SELECT * FROM ensaios"
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data_hora DESC"

    cursor.execute(query, parametros)
    linhas = cursor.fetchall()
    conn.close()
    return [_linha_para_dict(linha) for linha in linhas]


def obter_ensaio(ensaio_id):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ensaios WHERE id = ?", (ensaio_id,))
    linha = cursor.fetchone()
    conn.close()
    return _linha_para_dict(linha) if linha else None


def excluir_ensaio(ensaio_id):
    conn = obter_conexao()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM ensaios WHERE id = ?", (ensaio_id,))
    conn.commit()
    conn.close()


def exportar_ensaio_csv(ensaio_id, caminho):
    """Exporta o snapshot salvo do ensaio. Não inclui os pontos brutos
    de titulação -- eles não são persistidos no banco (só o resultado
    final), então não têm como ser recuperados aqui depois do fato."""
    ensaio = obter_ensaio(ensaio_id)
    if ensaio is None:
        raise ValueError(f"Ensaio com id={ensaio_id} não encontrado.")

    with open(caminho, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(["Campo", "Valor"])
        for chave, valor in ensaio.items():
            writer.writerow([chave, valor])