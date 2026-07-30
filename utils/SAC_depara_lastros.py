import pandas as pd
from utils.GLOBAL_functions import ErroDeCarga

def construir_traducao_lastro(caminho_posicao, tipos_titulo_sac):
    colunas_obrigatorias = {
        "CD_SISTEMA",
        "CD_LASTRO",
        "CD_CETIP_SELIC",
        "RFTP_CD",
    }

    colunas_chave = [
        "CD_SISTEMA",
        "CD_LASTRO",
    ]

    coluna_ativo = "CD_CETIP_SELIC"

    df_posicao = pd.read_csv(
        caminho_posicao,
        sep=";",
    )

    colunas_ausentes = colunas_obrigatorias - set(df_posicao.columns)

    if colunas_ausentes:
        raise ErroDeCarga(
            f"Posição sem as colunas obrigatórias: {sorted(colunas_ausentes)}"
        )

    df_posicao_filtrada = df_posicao[
        df_posicao["RFTP_CD"].isin(tipos_titulo_sac)
    ].copy()

    colunas_para_limpeza = colunas_chave + [coluna_ativo]

    for coluna in colunas_para_limpeza:
        df_posicao_filtrada[coluna] = (
            df_posicao_filtrada[coluna]
            .astype(str)
            .str.strip()
        )

    df_posicao_valida = df_posicao_filtrada[
        df_posicao_filtrada[coluna_ativo].str.lower() != "nan"
    ].copy()

    quantidade_ativos_por_lastro = (
        df_posicao_valida
        .groupby(colunas_chave)[coluna_ativo]
        .nunique()
    )

    lastros_com_conflito = quantidade_ativos_por_lastro[
        quantidade_ativos_por_lastro > 1
    ]

    if not lastros_com_conflito.empty:
        raise ErroDeCarga(
            "Lastro com mais de um CD_CETIP_SELIC na mesma base: "
            f"{list(lastros_com_conflito.index)}"
        )

    # Mantém apenas uma linha por base + lastro
    df_traducao = df_posicao_valida.drop_duplicates(
        subset=colunas_chave
    )

    traducao_lastro = {
        (linha.CD_SISTEMA, linha.CD_LASTRO): linha.CD_CETIP_SELIC
        for linha in df_traducao.itertuples(index=False)
    }

    return traducao_lastro
