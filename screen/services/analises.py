import numpy as np
import json
import joblib
from pathlib import Path


CT_G_L = 3.7       # concentração da solução titulante (g/L)
MM_G_MOL = 319.85  
VA_L = 0.300          # volume da amostra/solução no béquer (L)


def calcular_concentracao_molar(volume_acumulado_mL, ct_g_l=CT_G_L, mm_g_mol=MM_G_MOL, va_l=VA_L):
    """
    Calcula a concentração molar do tensoativo já adicionado à solução.

    Estou seguindo as equações 4, 5 e 6 da dissertação:
    """
    if volume_acumulado_mL <= 0:
        return 0.0
    massa_tensoativo_g = ct_g_l * volume_acumulado_mL / 1000.0
    mols = massa_tensoativo_g / mm_g_mol
    return mols / va_l

def concentracao_para_volume(concentracao_molar, ct_g_l=CT_G_L, mm_g_mol=MM_G_MOL, va_l=VA_L):
    """Função inversa: converte Molaridade (mol/L) de volta para Volume (mL)."""
    if concentracao_molar <= 0:
        return 0.0
    mols = concentracao_molar * va_l
    massa_g = mols * mm_g_mol
    return (massa_g / ct_g_l) * 1000.0

def detectar_cmc_joao_original(pontos_titulacao, limiar_linearidade=10.0, tol_subida=2.0):
    """

    Como funciona:
      Para cada tamanho de janela i (de 2 até o total de pontos),
      pega os ÚLTIMOS i pontos (os de maior concentração), ajusta uma
      reta neles, e verifica se TODOS os resíduos (|medido - previsto|)
      ficam abaixo de `limiar_linearidade`. Se sim, esse é um candidato
      a "trecho linear". Como o loop testa da menor pra maior janela
      SEM parar no primeiro sucesso, o resultado final é o MAIOR
      trecho (a partir do fim da curva) que ainda satisfaz o critério
      -- ou seja, a maior extensão da região "achatada" (pós-CMC) que
      ainda se comporta como uma reta única dentro da tolerância.

    A CMC é o primeiro ponto (menor concentração) desse trecho!!!

    Parâmetros
    ----------
    pontos_titulacao : list[dict]
        cada item com 'volume_acumulado_mL', 'concentracao_molar' (mol/L)
        e 'condutividade'.
    limiar_linearidade : float
        tolerância de resíduo ABSOLUTO (não percentual!) em unidades de
        Ω (condutividade molar, S.cm²/mol). O valor original do João é
        10.0 -- mesma unidade dos dados que ele usava.

    Retorna
    -------
    dict com concentracoes, volumes_mL, omegas (arrays completos),
    indice_cmc, cmc (concentração do ponto de corte), volume_cmc_mL,
    reta (a, b) ajustada no trecho linear, e os pontos do próprio
    trecho (x_trecho, y_trecho) para plotar.

    Lança ValueError se não encontrar nenhum trecho linear com o
    limiar dado (dados insuficientes ou tolerância baixa demais).
    """
    pontos_validos = [p for p in pontos_titulacao if p["concentracao_molar"] > 0]

    if len(pontos_validos) < 2:
        raise ValueError("São necessários ao menos 2 pontos para ajustar uma reta.")

    concentracoes = np.array([p["concentracao_molar"] for p in pontos_validos])
    volumes_mL = np.array([p["volume_acumulado_mL"] for p in pontos_validos])
    condutividades = np.array([p["condutividade"] for p in pontos_validos])
    omegas = (condutividades * 1e-3) / concentracoes

    concentracoes, volumes_mL, omegas = limpar_outliers_titulacao(
        concentracoes, volumes_mL, omegas, tol_subida=tol_subida
    )

    trecho_linear = None
    for i in range(2, len(concentracoes) + 1):
        x_trecho = concentracoes[-i:]
        y_trecho = omegas[-i:]
        coeficientes = np.polyfit(x_trecho, y_trecho, 1)
        polinomio = np.poly1d(coeficientes)
        residuos = y_trecho - polinomio(x_trecho)

        if all(abs(residuos) < limiar_linearidade):
            trecho_linear = (x_trecho, y_trecho, coeficientes)

    if trecho_linear is None:
        raise ValueError(
            "Não foi possível identificar um trecho linear com o limiar de "
            f"{limiar_linearidade}. Verifique se há pontos 'fora de curva' "
            "(Ω subindo em vez de descendo) que precisem ser removidos, ou "
            "aumente o limiar."
        )

    x_trecho, y_trecho, (a, b) = trecho_linear
    indice_cmc = len(concentracoes) - len(x_trecho)

    return {
        "concentracoes": concentracoes,
        "volumes_mL": volumes_mL,
        "omegas": omegas,
        "indice_cmc": int(indice_cmc),
        "cmc": float(x_trecho[0]),
        "volume_cmc_mL": float(volumes_mL[indice_cmc]),
        "reta": (float(a), float(b)),
        "x_trecho": x_trecho,
        "y_trecho": y_trecho,
    }


def cmc_para_ctc(volume_no_corte_mL, massa_amostra_g, normalidade_titulante=0.01):

    if massa_amostra_g <= 0:
        raise ValueError("A massa da amostra deve ser maior que zero.")

    # CTC = (V_titulante * N_titulante * 100) / massa_amostra
    return (volume_no_corte_mL * normalidade_titulante * 100) / massa_amostra_g

def calcular_ctc_final(resultado_cmc, massa_amostra):
    
    if "volume_cmc_mL" in resultado_cmc:
        volume_exato = resultado_cmc["volume_cmc_mL"]
    else:
        volume_exato = concentracao_para_volume(resultado_cmc["cmc"])
  
    resultado = cmc_para_ctc(
        volume_no_corte_mL=volume_exato, 
        massa_amostra_g=massa_amostra, 
        normalidade_titulante=0.01
    )
    
    return resultado

def classificar_tipo_argila(ctc_meq_100g):
    """
   apenas de exemplo
    """
    if ctc_meq_100g < 15:
        return "Caulinita (estimado)"
    elif ctc_meq_100g < 40:
        return "Ilita (estimado)"
    else:
        return "Esmectita/Bentonita (estimado)"


def limpar_outliers_titulacao(concentracoes, volumes_mL, omegas, tol_subida=2.0):
    
    x_filt, v_filt, y_filt = [concentracoes[0]], [volumes_mL[0]], [omegas[0]]
    
    for i in range(1, len(concentracoes)):
        if omegas[i] <= y_filt[-1] + tol_subida:
            x_filt.append(concentracoes[i])
            v_filt.append(volumes_mL[i])
            y_filt.append(omegas[i])
            
    return np.array(x_filt), np.array(v_filt), np.array(y_filt)


_DIR_MODELOS = Path('modelos_producao')
_CAMINHO_MODELO = _DIR_MODELOS / 'modelo_fase_mineral.joblib'
_CAMINHO_METADADOS = _DIR_MODELOS / 'modelo_fase_mineral_metadados.json'

_modelo_fase_mineral = None  # cache em memória -- carrega do disco só 1x
_faixa_treino_cache = None


def _carregar_modelo_fase_mineral():
    global _modelo_fase_mineral
    if _modelo_fase_mineral is None:
        _modelo_fase_mineral = joblib.load(_CAMINHO_MODELO)
    return _modelo_fase_mineral


def _faixa_ctc_treino():
    """Lê do JSON de metadados a faixa [min, max] de CTC vista no treino."""
    global _faixa_treino_cache
    if _faixa_treino_cache is None:
        with open(_CAMINHO_METADADOS, encoding='utf-8') as f:
            metadados = json.load(f)
        valores = metadados['amostras_treino']
        _faixa_treino_cache = (min(valores), max(valores))
    return _faixa_treino_cache


def classificar_tipo_argila(ctc_meq_100g):
    if ctc_meq_100g < 15:
        return "Caulinita (estimado)"
    elif ctc_meq_100g < 40:
        return "Ilita (estimado)"
    else:
        return "Esmectita/Bentonita (estimado)"


def prever_tipo_argila_ml(ctc_meq_100g):
    """
    Prevê a fase mineral dominante a partir do CTC usando o modelo treinado
    (ver treinar_modelo_producao.py). Sempre devolve um texto pronto pra
    exibir na interface, já com o aviso de confiança.

    Se o modelo não puder ser carregado por qualquer motivo (arquivo
    ausente, versão incompatível de scikit-learn/joblib etc.), cai de
    volta pra regra de literatura -- pra NUNCA travar o app por causa do
    modelo de ML, só perde a previsão mais refinada.

    IMPORTANTE: árvores de decisão dão predict_proba()=100% mesmo fora da
    faixa de CTC vista no treino (o modelo não tem como saber que está
    extrapolando -- ele só sabe em qual folha o valor caiu). Por isso,
    checamos manualmente se o CTC está dentro da faixa treinada antes de
    confiar na previsão.
    """
    try:
        modelo = _carregar_modelo_fase_mineral()
    except Exception as erro:
        tipo_regra = classificar_tipo_argila(ctc_meq_100g)
        return f"{tipo_regra} [regra de literatura -- modelo ML indisponível: {erro}]"

    ctc_min_treino, ctc_max_treino = _faixa_ctc_treino()
    fora_da_faixa = not (ctc_min_treino <= ctc_meq_100g <= ctc_max_treino)

    X = [[ctc_meq_100g]]
    classe_prevista = modelo.predict(X)[0]

    if fora_da_faixa:
        tipo_regra = classificar_tipo_argila(ctc_meq_100g)
        return (
            f"{classe_prevista}? (modelo ML FORA da faixa treinada "
            f"[{ctc_min_treino:.1f}-{ctc_max_treino:.1f}] -- NÃO CONFIÁVEL. "
            f"Regra de literatura sugere: {tipo_regra}. Recomenda-se DRX.)"
        )

    if hasattr(modelo, 'predict_proba'):
        probabilidades = modelo.predict_proba(X)[0]
        confianca = max(probabilidades)
        return f"{classe_prevista} (modelo ML, confiança {confianca:.0%} -- base pequena, verificar por DRX)"

    return f"{classe_prevista} (modelo ML -- base pequena, verificar por DRX)"


# ---- teste ----
for ctc_teste in [40.0, 46.0, 56.0, 85.0, 8.0, 25.0]:
    print(f"CTC={ctc_teste:>5.1f} -> {prever_tipo_argila_ml(ctc_teste)}")

print()
print("=== reteste com checagem de faixa ===")
for ctc in [8.0, 25.0, 40.0, 46.0, 48.0, 56.0, 85.0, 120.0]:
    print(f"CTC={ctc:>6.1f} -> {prever_tipo_argila_ml(ctc)}")