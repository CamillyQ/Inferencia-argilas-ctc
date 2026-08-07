import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent

DB_PATH = BASE_DIR / "argilas.db"

def conectar():
    return sqlite3.connect(DB_PATH)


_SQL_CRIAR_TABELA_ENSAIOS_CMC = """
CREATE TABLE IF NOT EXISTS ensaios_cmc (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    data_ensaio TEXT NOT NULL,      -- ISO 8601 (datetime.now().isoformat())

    massa_amostra_g REAL NOT NULL,

    cmc REAL,                       -- mol/L
    omega_cmc REAL,                 -- S.cm2/mol
    ctc REAL,                       -- mEq/100g
    classificacao TEXT,

    indice_joelho INTEGER,
    r2_pre REAL,
    r2_pos REAL,
    reta_pre_a REAL,
    reta_pre_b REAL,
    reta_pos_a REAL,
    reta_pos_b REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
"""

_SQL_CRIAR_INDICES = [
    "CREATE INDEX IF NOT EXISTS idx_ensaios_cmc_amostra ON ensaios_cmc(amostra_id)",
    "CREATE INDEX IF NOT EXISTS idx_ensaios_cmc_data ON ensaios_cmc(data_ensaio)",
    "CREATE INDEX IF NOT EXISTS idx_curva_condutividade_amostra ON curva_condutividade(amostra_id)",
]


def _garantir_tabela_ensaios_cmc(conn: sqlite3.Connection) -> None:
    conn.execute(_SQL_CRIAR_TABELA_ENSAIOS_CMC)
    for sql_indice in _SQL_CRIAR_INDICES:
        conn.execute(sql_indice)


def _obter_ou_criar_amostra_id(conn: sqlite3.Connection, codigo_amostra: str) -> int:
    """
    Busca o id da amostra pelo codigo; se nao existir ainda em `amostras`,
    cria um registro minimo (so com o codigo) para poder pendurar o
    ensaio nela. Se voces ja tiverem uma tela propria de cadastro de
    amostras, da pra trocar esta funcao por uma busca simples (sem INSERT)
    e tratar "amostra nao encontrada" como erro explicito.
    """
    cursor = conn.execute("SELECT id FROM amostras WHERE codigo = ?", (codigo_amostra,))
    linha = cursor.fetchone()
    if linha is not None:
        return linha[0]

    cursor = conn.execute(
        "INSERT INTO amostras (codigo) VALUES (?)", (codigo_amostra,)
    )
    return cursor.lastrowid


def salvar_ensaio(
    codigo_amostra: str,
    massa_amostra_g: float,
    cmc: Optional[float],
    ctc: Optional[float],
    classificacao: Optional[str] = None,
    omega_cmc: Optional[float] = None,
    indice_joelho: Optional[int] = None,
    r2_pre: Optional[float] = None,
    r2_pos: Optional[float] = None,
    reta_pre: Optional[tuple] = None,
    reta_pos: Optional[tuple] = None,
    pontos_curva: Optional[list] = None,
) -> int:
    """
    Salva o resultado de um ensaio de CTC via CMC. Retorna o id do
    ensaio salvo (linha em ensaios_cmc).

    pontos_curva (opcional): lista de dicts no mesmo formato usado por
    detectar_cmc_joao, ex.: [{"volume_acumulado_mL": v, "condutividade": c}, ...]
    Se fornecido, os pontos brutos sao gravados em curva_condutividade
    (sobrescrevendo quaisquer pontos antigos da mesma amostra).

    Chame esta funcao a partir de ScadaApp.detectar_cmc(), logo depois
    de calcular ctc_final/interseccao/tipo_argila -- hoje esse metodo
    calcula tudo mas nao persiste nada no banco.
    """
    reta_pre = reta_pre or (None, None)
    reta_pos = reta_pos or (None, None)

    conn = conectar()
    try:
        _garantir_tabela_ensaios_cmc(conn)
        amostra_id = _obter_ou_criar_amostra_id(conn, codigo_amostra)

        cursor = conn.execute(
            """
            INSERT INTO ensaios_cmc (
                amostra_id, data_ensaio, massa_amostra_g, cmc, omega_cmc,
                ctc, classificacao, indice_joelho, r2_pre, r2_pos,
                reta_pre_a, reta_pre_b, reta_pos_a, reta_pos_b
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                amostra_id, datetime.now().isoformat(), massa_amostra_g, cmc,
                omega_cmc, ctc, classificacao, indice_joelho, r2_pre, r2_pos,
                reta_pre[0], reta_pre[1], reta_pos[0], reta_pos[1],
            ),
        )
        ensaio_id = cursor.lastrowid

        if pontos_curva:
            conn.execute(
                "DELETE FROM curva_condutividade WHERE amostra_id = ?",
                (amostra_id,),
            )
            conn.executemany(
                """
                INSERT INTO curva_condutividade
                    (amostra_id, ponto, volume_adicionado, condutividade)
                VALUES (?, ?, ?, ?)
                """,
                [
                    (amostra_id, i, p["volume_acumulado_mL"], p["condutividade"])
                    for i, p in enumerate(pontos_curva)
                ],
            )

        conn.commit()
        return ensaio_id
    finally:
        conn.close()


def listar_ensaios(
    filtro_texto: Optional[str] = None,
    data_inicio: Optional[date] = None,
    data_fim: Optional[date] = None,
) -> list:
    """
    Lista os ensaios salvos, do mais recente para o mais antigo.
    Cada item: id, data_hora (datetime), amostra (codigo), ctc, cmc,
    massa_g, classificacao.
    """
    conn = conectar()
    try:
        _garantir_tabela_ensaios_cmc(conn)

        condicoes = []
        parametros = []

        if filtro_texto:
            condicoes.append("amostras.codigo LIKE ?")
            parametros.append(f"%{filtro_texto}%")
        if data_inicio:
            condicoes.append("date(ensaios_cmc.data_ensaio) >= date(?)")
            parametros.append(data_inicio.isoformat())
        if data_fim:
            condicoes.append("date(ensaios_cmc.data_ensaio) <= date(?)")
            parametros.append(data_fim.isoformat())

        where_sql = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

        cursor = conn.execute(
            f"""
            SELECT
                ensaios_cmc.id,
                ensaios_cmc.data_ensaio,
                amostras.codigo,
                ensaios_cmc.ctc,
                ensaios_cmc.cmc,
                ensaios_cmc.massa_amostra_g,
                ensaios_cmc.classificacao
            FROM ensaios_cmc
            JOIN amostras ON amostras.id = ensaios_cmc.amostra_id
            {where_sql}
            ORDER BY ensaios_cmc.data_ensaio DESC
            """,
            parametros,
        )

        resultado = []
        for linha in cursor.fetchall():
            (ensaio_id, data_ensaio_str, codigo, ctc, cmc, massa_g, classificacao) = linha
            resultado.append({
                "id": ensaio_id,
                "data_hora": _parse_data(data_ensaio_str),
                "amostra": codigo,
                "ctc": ctc,
                "cmc": cmc,
                "massa_g": massa_g,
                "classificacao": classificacao,
            })
        return resultado
    finally:
        conn.close()


def obter_ensaio(ensaio_id: int):
    """
    Retorna todos os detalhes de um ensaio, incluindo os pontos brutos
    da curva (concentracoes/omegas), recalculados a partir de
    curva_condutividade -- para o grafico da tela de Historico.
    """
    from services.analises import calcular_concentracao_molar

    conn = conectar()
    try:
        _garantir_tabela_ensaios_cmc(conn)

        cursor = conn.execute(
            """
            SELECT
                ensaios_cmc.id, ensaios_cmc.amostra_id, ensaios_cmc.data_ensaio,
                ensaios_cmc.massa_amostra_g, ensaios_cmc.cmc, ensaios_cmc.omega_cmc,
                ensaios_cmc.ctc, ensaios_cmc.classificacao,
                ensaios_cmc.reta_pre_a, ensaios_cmc.reta_pre_b,
                ensaios_cmc.reta_pos_a, ensaios_cmc.reta_pos_b,
                amostras.codigo
            FROM ensaios_cmc
            JOIN amostras ON amostras.id = ensaios_cmc.amostra_id
            WHERE ensaios_cmc.id = ?
            """,
            (ensaio_id,),
        )
        linha = cursor.fetchone()
        if linha is None:
            return None

        (eid, amostra_id, data_ensaio_str, massa_g, cmc, omega_cmc, ctc,
         classificacao, rpa, rpb, rposa, rposb, codigo) = linha

        pontos = conn.execute(
            """
            SELECT volume_adicionado, condutividade
            FROM curva_condutividade
            WHERE amostra_id = ?
            ORDER BY ponto
            """,
            (amostra_id,),
        ).fetchall()

        concentracoes, omegas = [], []
        for volume, condutividade in pontos:
            concentracao = calcular_concentracao_molar(volume)
            if concentracao > 0:
                concentracoes.append(concentracao)
                omegas.append(condutividade / concentracao)

        return {
            "id": eid,
            "data_hora": _parse_data(data_ensaio_str),
            "amostra": codigo,
            "massa_g": massa_g,
            "cmc": cmc,
            "omega_cmc": omega_cmc,
            "ctc": ctc,
            "classificacao": classificacao,
            "reta_pre": (rpa, rpb) if rpa is not None else None,
            "reta_pos": (rposa, rposb) if rposa is not None else None,
            "concentracoes": concentracoes,
            "omegas": omegas,
        }
    finally:
        conn.close()


def excluir_ensaio(ensaio_id: int) -> None:
    """
    Remove apenas o registro do ensaio (tabela ensaios_cmc). Os dados
    brutos da amostra (curva_condutividade, granulometria etc.) NAO sao
    apagados, ja que pertencem a amostra em si, nao a este ensaio
    especifico -- ajuste aqui se quiser um "excluir tudo" mais agressivo.
    """
    conn = conectar()
    try:
        _garantir_tabela_ensaios_cmc(conn)
        conn.execute("DELETE FROM ensaios_cmc WHERE id = ?", (ensaio_id,))
        conn.commit()
    finally:
        conn.close()


def exportar_ensaio_csv(ensaio_id: int, caminho: str) -> None:
    """Exporta o ensaio (metadados + curva bruta) para um CSV simples."""
    import csv

    ensaio = obter_ensaio(ensaio_id)
    if ensaio is None:
        raise ValueError(f"Ensaio {ensaio_id} nao encontrado.")

    with open(caminho, "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.writer(arquivo)
        escritor.writerow(["amostra", "data_hora", "massa_g", "cmc_mol_L", "ctc_meq_100g", "classificacao"])
        escritor.writerow([
            ensaio["amostra"],
            ensaio["data_hora"],
            ensaio["massa_g"],
            ensaio["cmc"],
            ensaio["ctc"],
            ensaio["classificacao"],
        ])
        escritor.writerow([])
        escritor.writerow(["concentracao_molar", "condutividade_molar"])
        for c, o in zip(ensaio["concentracoes"], ensaio["omegas"]):
            escritor.writerow([c, o])


def _parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor)
    except ValueError:
        return valor