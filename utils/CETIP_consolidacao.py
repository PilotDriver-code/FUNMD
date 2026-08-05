import ast
import json
import pandas as pd


def converter_origem_para_dict(valor):
    """
    Converte a origem para dict, caso venha como texto.
    """
    if isinstance(valor, dict):
        return valor

    if pd.isna(valor):
        return {}

    try:
        return ast.literal_eval(str(valor))
    except (ValueError, SyntaxError):
        return {"valor_original": str(valor)}


def normalizar_evento(evento):
    return (
        str(evento)
        .strip()
        .lower()
        .replace("ç", "c")
        .replace("ã", "a")
        .replace("á", "a")
        .replace("â", "a")
        .replace("ê", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ô", "o")
        .replace("ú", "u")
    )


def consolidar_eventos(df):
    df = df.copy()

    # Garante que valor seja numérico
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce").fillna(0)

    # Converte data
    df["data"] = pd.to_datetime(
        df["data"],
        dayfirst=True,
        errors="coerce",
    )

    # Preserva o nome original e cria uma versão normalizada
    df["_evento_original"] = df["evento"].astype(str)
    df["_evento_normalizado"] = df["evento"].apply(normalizar_evento)

    # Converte cada origem em dicionário
    df["_origem_dict"] = df["origem"].apply(converter_origem_para_dict)

    chaves_ativo_data = ["base", "carteira", "ativo", "data"]

    # Identifica quais ativos/data possuem vencimento
    grupos_com_vencimento = (
        df.loc[
            df["_evento_normalizado"].eq("vencimento"),
            chaves_ativo_data,
        ]
        .drop_duplicates()
        .assign(_tem_vencimento=True)
    )

    df = df.merge(
        grupos_com_vencimento,
        on=chaves_ativo_data,
        how="left",
    )

    df["_tem_vencimento"] = df["_tem_vencimento"].fillna(False)

    # Premio nunca entra no agrupamento do vencimento
    eh_premio = df["_evento_normalizado"].isin(["premio", "pagamento de premio"])

    # Tudo que pertence a ativo/data com vencimento,
    # exceto premio, passa a ser consolidado como Vencimento
    deve_agrupar_no_vencimento = df["_tem_vencimento"] & ~eh_premio

    df.loc[deve_agrupar_no_vencimento, "_evento_agrupamento"] = "Vencimento"

    # Os demais permanecem com o evento original
    df["_evento_agrupamento"] = df["_evento_agrupamento"].fillna(df["_evento_original"])

    chaves_agrupamento = [
        "base",
        "carteira",
        "ativo",
        "_evento_agrupamento",
        "data",
    ]

    def consolidar_grupo(grupo):
        origens = grupo["_origem_dict"].tolist()
        eventos = grupo["_evento_original"].tolist()

        # Mantém a ordem, removendo duplicados
        eventos_distintos = list(dict.fromkeys(eventos))

        origem_consolidada = {
            "quantidade_eventos_agrupados": len(grupo),
            "eventos_agrupados": eventos,
            "tipos_eventos_agrupados": eventos_distintos,
            "origens": origens,
        }

        return pd.Series(
            {
                "valor": grupo["valor"].sum(),
                "quantidade_eventos": len(grupo),
                "eventos_agrupados": eventos,
                "origem": origem_consolidada,
            }
        )

    df_final = (
        df.groupby(
            chaves_agrupamento,
            dropna=False,
            sort=False,
        )
        .apply(consolidar_grupo, include_groups=False)
        .reset_index()
        .rename(columns={"_evento_agrupamento": "evento"})
    )

    # Volta a data para o formato brasileiro
    df_final["data"] = df_final["data"].dt.strftime("%d/%m/%Y")

    return df_final
