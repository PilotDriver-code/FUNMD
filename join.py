import pandas as pd


CHAVE_EVENTO = ["base", "carteira", "ativo", "evento"]  # data NAO entra na chave
CHAVE_ATIVO = ["base", "carteira", "ativo"]


# ---------------------------------------------------------------------------
# 1. Montar o lado SAC dos EVENTOS
#    Operacao (juros, amortizacao, vencimento) + Premio (que so existe no Caixa)
#    O complemento "caixa" NAO entra aqui: ele nao e evento.
# ---------------------------------------------------------------------------
def extrair_premio_como_evento(caixa_consolidado):
    """
    Transforma a coluna 'premio' do Caixa consolidado em linhas de evento,
    para que o premio possa ser comparado com o premio da CETIP (codigo 806).
    """
    if caixa_consolidado is None or caixa_consolidado.empty:
        return pd.DataFrame(columns=CHAVE_EVENTO + ["valor", "quantidade"])

    com_premio = caixa_consolidado[caixa_consolidado["premio"] != 0].copy()
    if com_premio.empty:
        return pd.DataFrame(columns=CHAVE_EVENTO + ["valor", "quantidade"])

    linhas = []
    for registro in com_premio.itertuples():
        linhas.append({
            "base": registro.base,
            "carteira": registro.carteira,
            "ativo": registro.ativo,
            "evento": "Premio",
            "data": getattr(registro, "data", None),
            "valor": registro.premio,
            "quantidade": 0,
        })

    return pd.DataFrame(linhas)


def montar_lado_sac_eventos(operacao_consolidada, caixa_consolidado):
    """
    Junta os eventos da Operacao com o Premio vindo do Caixa.
    Este e o lado SAC que sera comparado evento-a-evento com a CETIP.
    """
    premio = extrair_premio_como_evento(caixa_consolidado)

    partes = [p for p in (operacao_consolidada, premio)
              if p is not None and not p.empty]

    if not partes:
        return pd.DataFrame(columns=CHAVE_EVENTO + ["valor", "quantidade"])

    return pd.concat(partes, ignore_index=True, sort=False)


# ---------------------------------------------------------------------------
# 2. Join evento-a-evento: CETIP  vs  lado SAC
# ---------------------------------------------------------------------------
def juntar_eventos(cetip_consolidada, sac_eventos):
    """
    Outer join por base+carteira+ativo+evento+data.
    Cada linha mostra o valor dos dois lados e a diferenca.
    """
    if cetip_consolidada is None:
        cetip_consolidada = pd.DataFrame(columns=CHAVE_EVENTO + ["valor"])
    if sac_eventos is None:
        sac_eventos = pd.DataFrame(columns=CHAVE_EVENTO + ["valor"])

    # a data nao entra na chave; para nao duplicar coluna, tiro a da CETIP
    if "data" in cetip_consolidada.columns:
        cetip_consolidada = cetip_consolidada.drop(columns=["data"])

    comparado = pd.merge(
        sac_eventos, cetip_consolidada,
        on=CHAVE_EVENTO,
        how="outer",
        suffixes=("_sac", "_cetip"),
        indicator=True,
    )

    comparado["valor_sac"] = pd.to_numeric(
        comparado.get("valor_sac"), errors="coerce").fillna(0)
    comparado["valor_cetip"] = pd.to_numeric(
        comparado.get("valor_cetip"), errors="coerce").fillna(0)
    comparado["diferenca"] = comparado["valor_sac"] - comparado["valor_cetip"]

    comparado["tem_sac"] = comparado["_merge"].isin(["both", "left_only"])
    comparado["tem_cetip"] = comparado["_merge"].isin(["both", "right_only"])
    comparado["evento_orfao"] = comparado["_merge"] != "both"

    return comparado.drop(columns=["_merge"])


# ---------------------------------------------------------------------------
# 3. Aplicar o complemento do Caixa no nivel do ATIVO
#    O caixa (803) nao compara com nada da CETIP: ele fecha o total.
# ---------------------------------------------------------------------------
def montar_mapa_caixa(caixa_consolidado):
    """Indexa o Caixa consolidado por (base, carteira, ativo)."""
    if caixa_consolidado is None or caixa_consolidado.empty:
        return {}

    mapa = {}
    for registro in caixa_consolidado.itertuples():
        mapa[(registro.base, registro.carteira, registro.ativo)] = {
            "caixa": registro.caixa,
            "qtd_linhas_caixa": registro.qtd_linhas_caixa,
            "tem_postergacao": registro.tem_postergacao,
        }
    return mapa


def fechar_total_do_ativo(comparado, mapa_caixa):
    """
    Para cada ATIVO (fundo+ativo), soma os eventos dos dois lados e aplica o
    complemento do Caixa do lado SAC:

        total_sac = eventos_sac + caixa
        fecha quando total_sac == total_cetip

    Devolve um DataFrame com uma linha por ativo.
    """
    if comparado.empty:
        return pd.DataFrame(columns=CHAVE_ATIVO + [
            "total_eventos_sac", "caixa", "total_sac", "total_cetip",
            "diferenca_total", "fecha", "qtd_linhas_caixa", "tem_postergacao"])

    linhas = []
    for chave, grupo in comparado.groupby(CHAVE_ATIVO, dropna=False):
        dados_caixa = mapa_caixa.get(tuple(chave), {})

        total_eventos_sac = grupo["valor_sac"].sum()
        total_cetip = grupo["valor_cetip"].sum()
        caixa = dados_caixa.get("caixa", 0.0)
        total_sac = total_eventos_sac + caixa

        base, carteira, ativo = chave
        linhas.append({
            "base": base,
            "carteira": carteira,
            "ativo": ativo,
            "total_eventos_sac": total_eventos_sac,
            "caixa": caixa,
            "total_sac": total_sac,
            "total_cetip": total_cetip,
            "diferenca_total": total_sac - total_cetip,
            "fecha": abs(total_sac - total_cetip) < 0.01,
            "qtd_linhas_caixa": dados_caixa.get("qtd_linhas_caixa", 0),
            "tem_postergacao": dados_caixa.get("tem_postergacao", False),
        })

    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# 4. Orquestrador
# ---------------------------------------------------------------------------
def montar_diagnostico_join(comparado, fechamento):
    return {
        "eventos_comparados": len(comparado),
        "eventos_orfaos": int(comparado["evento_orfao"].sum()) if len(comparado) else 0,
        "ativos": len(fechamento),
        "ativos_que_fecham": int(fechamento["fecha"].sum()) if len(fechamento) else 0,
        "ativos_com_postergacao": int(fechamento["tem_postergacao"].sum()) if len(fechamento) else 0,
    }


def juntar_CETIP_SAC(cetip_consolidada, operacao_consolidada,
                     caixa_consolidado):
    """
    Junta as tres pontas em dois niveis:

      NIVEL EVENTO: CETIP vs (Operacao + Premio do Caixa)
        -> compara juros, amortizacao, premio evento-a-evento

      NIVEL ATIVO:  total CETIP vs (eventos SAC + caixa)
        -> o complemento do Caixa fecha o montante do ativo

    Devolve (comparado_eventos, fechamento_ativos, diagnostico).
    """
    sac_eventos = montar_lado_sac_eventos(
        operacao_consolidada, caixa_consolidado)

    comparado = juntar_eventos(cetip_consolidada, sac_eventos)

    mapa_caixa = montar_mapa_caixa(caixa_consolidado)
    fechamento = fechar_total_do_ativo(comparado, mapa_caixa)

    diagnostico = montar_diagnostico_join(comparado, fechamento)

    return comparado, fechamento, diagnostico
