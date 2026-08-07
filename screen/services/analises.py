import numpy as np


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


def detectar_cmc_joao_original(pontos_titulacao, limiar_linearidade=10.0):
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
    omegas = condutividades / concentracoes

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

def calcular_ctc_final(interseccao_cmc, massa_amostra):
    volume_exato = concentracao_para_volume(interseccao_cmc['x_cmc'])
  
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


def limpar_outliers_titulacao(concentracoes, omegas, tol_subida=2.0):
    """
    Filtra pontos anormais onde omega aumenta significativamente 
    em vez de cair/estabilizar.
    """
    x_filt, y_filt = [concentracoes[0]], [omegas[0]]
    
    for i in range(1, len(concentracoes)):
        if omegas[i] <= y_filt[-1] + tol_subida:
            x_filt.append(concentracoes[i])
            y_filt.append(omegas[i])
            
    return np.array(x_filt), np.array(y_filt)
