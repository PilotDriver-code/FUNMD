import pandas as pd
from utils.GLOBAL_functions import ErroDeCarga

import pandas as pd

COLUNAS_LIMPEZA_SAC_OPERACAO = [
    "CD_SISTEMA",
    "CLCLI_CD",
    "CD_LASTRO",
    "SG_OPERACAO",
]


COLUNAS_OBRIGATORIAS_SAC_OPERACAO = {
    "CD_SISTEMA",
    "CLCLI_CD",
    "DT",
    "CD",
    "CD_LASTRO",
    "SG_OPERACAO",
    "DS_TP_TRANSACAO",
    "QT",
    "VL_PU_OPERACAO",
    "VL_BRUTO",
}


def ler_sac_operacao(caminho_operacao):
    """
    Lê o arquivo SAC Operação e mantém apenas operações privadas.
    """

    df = pd.read_csv(
        caminho_operacao,
        sep=";",
        encoding="utf-8-sig"
    )

    df = df[df["IC_PUB_PRIV"] == "I"]

    return df


def validar_colunas_sac_operacao(df):
    """
    Valida se todas as colunas obrigatórias existem no arquivo.
    """

    colunas_faltantes = COLUNAS_OBRIGATORIAS_SAC_OPERACAO - set(df.columns)

    if colunas_faltantes:
        raise ErroDeCarga(f"Arquivo VCRAOPRF sem colunas: {colunas_faltantes}")


def limpar_colunas_sac_operacao(df):

    for coluna in COLUNAS_LIMPEZA_SAC_OPERACAO:
        df[coluna] = df[coluna].astype(str).str.strip()



def traduzir_evento_sac_operacao(codigo_evento, tipo_sac_operacao):
    """
    Traduz o código original do SAC para o evento padronizado.
    """

    return tipo_sac_operacao.get(codigo_evento)


def localizar_ativo_sac_operacao(
    traducao,
    sistema,
    lastro,
):
    """
    Localiza o ativo utilizando a combinação sistema + lastro.
    """

    return traducao.get((sistema, lastro))


def montar_origem_sac_operacao(registro):
    """
    Monta os dados originais preservados para auditoria.
    """
    return {
        "sistema": "sac_operacao",
        "lastro": registro.CD_LASTRO,
        "trade": registro.CD,
        "id": registro.ID,
        "evento_cru": registro.SG_OPERACAO,
        "descricao": registro.DS_TP_TRANSACAO,
        "pub_priv": registro.IC_PUB_PRIV,
        "qt": registro.QT,
        "pu": registro.VL_PU_OPERACAO,
        "valor_original": registro.VL_BRUTO,
    }


def montar_linha_sac_operacao(
    registro,
    evento,
    ativo,
):
    """
    Monta uma linha no formato comum da conciliação.
    """

    return {
        "base": registro.CD_SISTEMA,
        "carteira": registro.CLCLI_CD,
        "ativo": ativo,
        "evento": evento,
        "data": registro.DT,
        "valor": registro.VL_BRUTO,
        "qntd": registro.QT,
        "trade": registro.CD,
        "origem": montar_origem_sac_operacao(registro),
    }


def montar_diagnostico_sac_operacao(
    df,
    resultado,
    eventos_nao_mapeados,
    lastros_ausentes,
):
    """
    Monta o diagnóstico final do processamento.
    """

    return {
        "linhas_lidas": len(df),
        "linhas_normalizadas": len(resultado),
        "eventos_nao_mapeados": sorted(set(eventos_nao_mapeados)),
        "lastros_ausentes": sorted(set(lastros_ausentes)),
    }


def normalizar_VCRAOPRF(caminho_operacao, traducao, tipo_sac_operacao):

    df = ler_sac_operacao(caminho_operacao)

    validar_colunas_sac_operacao(df)
    limpar_colunas_sac_operacao(df)

    linhas_normalizadas = []
    eventos_nao_mapeados = []
    lastros_ausentes = []

    for registro in df.itertuples():
        # PORTÃO 1 — evento fora do de-para
        evento = traduzir_evento_sac_operacao(registro.SG_OPERACAO, tipo_sac_operacao)

        if evento is None:
            eventos_nao_mapeados.append(registro.SG_OPERACAO)
            continue

        # PORTÃO 2 — localizar ativo pelo lastro
        ativo = localizar_ativo_sac_operacao(
            traducao=traducao,
            sistema=registro.CD_SISTEMA,
            lastro=registro.CD_LASTRO,
        )

        if ativo is None:
            lastros_ausentes.append(
                (
                    registro.CD_SISTEMA,
                    registro.CD_LASTRO,
                )
            )

            ativo = None

        linha_normalizada = montar_linha_sac_operacao(
            registro=registro,
            evento=evento,
            ativo=ativo,
        )

        linhas_normalizadas.append(linha_normalizada)

    resultado = pd.DataFrame(linhas_normalizadas)

    diagnostico = montar_diagnostico_sac_operacao(
        df=df,
        resultado=resultado,
        eventos_nao_mapeados=eventos_nao_mapeados,
        lastros_ausentes=lastros_ausentes,
    )

    return resultado, diagnostico
