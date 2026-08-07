from db import conectar

conn = conectar()
cursor = conn.cursor()


cursor.execute("""
CREATE TABLE IF NOT EXISTS amostras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    codigo TEXT UNIQUE NOT NULL,

    data_coleta TEXT,

    origem TEXT,

    observacoes TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS granulometria (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,


    d10 REAL,
    d50 REAL,
    d90 REAL,

    diametro_medio REAL,


    span REAL,

    -- metadados do ensaio — relevantes para reprodutibilidade
    metodo_optico TEXT,         -- ex: "Fraunhofer", "Mie"
    liquido_dispersante TEXT,   -- ex: "Water"
    agente_dispersante TEXT,    -- ex: "None"
    tempo_ultrasom_s REAL,
    obscuracao_pct REAL,

    -- caminho do PDF original arquivado — rastreabilidade do laudo
    laudo_pdf_path TEXT,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS granulometria_curva (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    diametro_um REAL,      -- x: diâmetro da classe, em µm
    cumulativo_pct REAL,   -- Q3: % cumulativo passante
    densidade REAL,        -- q3: densidade da distribuição

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS plasticidade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    limite_liquidez REAL,

    limite_plasticidade REAL,

    indice_plasticidade REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS reologia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    viscosidade_aparente REAL,

    viscosidade_plastica REAL,

    limite_escoamento REAL,

    tixotropia REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")


cursor.execute("""
CREATE TABLE IF NOT EXISTS drx (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    mineral TEXT, 
            
    percentual REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS curva_condutividade (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    ponto INTEGER,

    volume_adicionado REAL,

    condutividade REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    condutividade_max REAL,

    condutividade_min REAL,

    condutividade_media REAL,

    derivada_max REAL,

    derivada_media REAL,

    area_curva REAL,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS resultados_laboratorio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    ctc REAL,

    classe_argila TEXT,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS predicoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    amostra_id INTEGER NOT NULL,

    modelo TEXT,

    ctc_estimado REAL,

    classe_predita TEXT,

    confianca REAL,

    data_predicao DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY(amostra_id)
    REFERENCES amostras(id)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,

    valor TEXT
)
""")

conn.commit()
conn.close()

cursor.execute("""
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
""")

print("Banco criado com sucesso.")