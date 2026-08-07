import pandas as pd


CHAVE_ATIVO = ["base", "carteira", "ativo", "data"]

EVENTO_VENCIMENTO = "Vencimento"
EVENTO_PREMIO = "Prêmio"


def somar_eventos_iguais(cetip_normalizada):
    """
    Soma eventos iguais do mesmo fundo+ativo.

    A CETIP pode lancar mais de um codigo para o mesmo evento (ex.: 74 e 874,
    ambos amortizacao). Depois do de-para os dois viram "Amortizacao" e aqui
    viram uma linha so, somada.
    """
    df = cetip_normalizada.copy()
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")

    return (df.groupby(CHAVE_ATIVO + ["evento"], dropna=False)
              .agg(valor=("valor", "sum"),
                   origem=("origem", list))
              .reset_index())


def tem_vencimento(grupo):
    """Indica se o ativo esta vencendo (tem evento de resgate/vencimento)."""
    return (grupo["evento"] == EVENTO_VENCIMENTO).any()


def separar_premio(grupo):
    """
    Separa o premio do resto. O premio NUNCA funde no vencimento: ele e um
    componente proprio, comparado com o premio do SAC (codigo 960 do Caixa).
    """
    premio = grupo[grupo["evento"] == EVENTO_PREMIO]
    demais = grupo[grupo["evento"] != EVENTO_PREMIO]
    return premio, demais


def montar_linha_cetip(registro, evento, valor, origem):
    """Monta uma linha consolidada da CETIP."""
    return {
        "base": registro["base"],
        "carteira": registro["carteira"],
        "ativo": registro["ativo"],
        "evento": evento,
        "data": registro["data"],
        "valor": valor,
        "origem": origem,
    }


def fundir_vencimento(demais):
    """
    Funde vencimento + juros + amortizacao numa unica linha "Vencimento".

    O SAC ja entrega o resgate com o valor total dentro; a CETIP vem partida.
    Fundimos a CETIP para que os dois lados fiquem comparaveis.
    """
    valor_total = demais["valor"].sum()
    eventos_fundidos = list(demais["evento"])
    origens = list(demais["origem"])

    linha = montar_linha_cetip(
        registro=demais.iloc[0],
        evento=EVENTO_VENCIMENTO,
        valor=valor_total,
        origem={"fundidos": eventos_fundidos, "detalhe": origens},
    )
    return linha


def montar_diagnostico_consolidacao(cetip_normalizada, resultado, ativos_fundidos):
    """Diagnostico do processo."""
    return {
        "linhas_cetip_entrada": len(cetip_normalizada),
        "linhas_consolidadas": len(resultado),
        "ativos_com_vencimento_fundido": ativos_fundidos,
    }


def consolidar_CETIP(cetip_normalizada):
    """
    Consolida a CETIP em dois passos:

      1. soma eventos iguais do mesmo fundo+ativo (74 + 874 -> uma Amortizacao)
      2. quando o ativo tem Vencimento, funde vencimento+juros+amortizacao
         numa unica linha "Vencimento". O Premio fica sempre separado.

    A fusao acontece SO na CETIP: o SAC ja entrega o resgate fundido.
    """
    if cetip_normalizada is None or cetip_normalizada.empty:
        vazio = pd.DataFrame(columns=CHAVE_ATIVO + ["evento", "valor", "origem"])
        return vazio, montar_diagnostico_consolidacao(pd.DataFrame(), vazio, 0)

    somada = somar_eventos_iguais(cetip_normalizada)

    linhas = []
    ativos_fundidos = 0

    for _, grupo in somada.groupby(CHAVE_ATIVO, dropna=False):
        if not tem_vencimento(grupo):
            # sem vencimento: cada evento mantem sua propria linha
            for _, registro in grupo.iterrows():
                linhas.append(montar_linha_cetip(
                    registro, registro["evento"], registro["valor"], registro["origem"]))
            continue

        # com vencimento: funde tudo menos o premio
        premio, demais = separar_premio(grupo)

        if not demais.empty:
            linhas.append(fundir_vencimento(demais))
            ativos_fundidos += 1

        for _, registro in premio.iterrows():
            linhas.append(montar_linha_cetip(
                registro, EVENTO_PREMIO, registro["valor"], registro["origem"]))

    resultado = pd.DataFrame(linhas)
    diagnostico = montar_diagnostico_consolidacao(
        cetip_normalizada, resultado, ativos_fundidos)

    return resultado, diagnostico
