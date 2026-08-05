import pandas as pd
import unicodedata
import re

from utils.GLOBAL_functions import ErroDeCarga

COLUNAS_OBRIGATORIAS_SAC_CAIXA = {
   "CD_SISTEMA", 
   "CLCLI_CD", 
   "DT", 
   "VL", 
   "DS", 
   "MTTP_CD", 
   "ORIGEM"
}

COLUNAS_LIMPEZA_SAC_CAIXA = [
    "CD_SISTEMA",
    "CLCLI_CD",
    "MTTP_CD",
    "ORIGEM"
]

CODIGOS_CAIXA_MT_VALIDOS = {"84", "86", "803", "960"}

def ler_sac_caixa(caminho_caixa):

    df = pd.read_csv(
        caminho_caixa,
        sep=";",
        encoding="utf-8-sig"
    )

    return df


def validar_depara_lastros(depara_lastros):

    if not isinstance(depara_lastros, dict):
        raise ErroDeCarga(
            "O de-para de lastros deve ser um dicionário "
            "no formato {(base, codigo_lastro): ativo}."
        )


def validar_colunas_sac_caixa(df):

    colunas_faltantes = COLUNAS_OBRIGATORIAS_SAC_CAIXA - set(df.columns)

    if colunas_faltantes:
        raise ErroDeCarga(f"Arquivo VCRAOPRF sem colunas: {colunas_faltantes}")


def limpar_colunas_sac_caixa(df):

    for coluna in COLUNAS_LIMPEZA_SAC_CAIXA:
        df[coluna] = df[coluna].astype(str).str.strip()

    df["ORIGEM"] = df["ORIGEM"].str.upper()

    df["VL_ORIGINAL"] = df["VL"]

    df["VL"] = pd.to_numeric(
        df["VL"].str.strip(),
        errors="coerce",
    )
    return df


def filtrar_lancamentos_caixa_validos(df):

    mascara_origem_mt = df["ORIGEM"].eq("MT")
    mascara_codigo_valido = df["MTTP_CD"].isin(CODIGOS_CAIXA_MT_VALIDOS)

    df_filtrado = df.loc[
        mascara_origem_mt & mascara_codigo_valido
    ].copy()

    diagnostico = {
        "origem_nao_mt": int((~mascara_origem_mt).sum()),
        "codigo_ignorado": int(
            (mascara_origem_mt & ~mascara_codigo_valido).sum()
        ),
    }

    return df_filtrado, diagnostico


def normalizar_texto(texto):

    if pd.isna(texto):
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto),
    )

    texto = texto.encode("ascii", errors="ignore").decode("ascii").upper().strip()

    texto = re.sub(
        r"\s+",
        " ",
        texto,
    )

    return texto


def identificar_natureza(comentario, mttp_cd):

    texto = normalizar_texto(comentario)

    if "POSTERGACAO" in texto:
        return "Postergacao"

    if "ESTORNO" in texto:
        return "Estorno"

    if "AJUSTE" in texto:
        return "Ajuste"

    if "PREMIO" in texto:
        return "Premio"

    if "PARTICIPACAO" in texto:
        return "Premio"

    # O código 960 representa prêmio.
    if mttp_cd == "960":
        return "Premio"

    return None


def identificar_evento(comentario, natureza):

    texto = normalizar_texto(comentario)

    if "PREMIO" in texto:
        return "Premio"

    if "AMORTIZACAO" in texto:
        return "Amortizacao"

    if "JUROS" in texto or "CORRECAO MONETARIA" in texto or "RENDIMENTO" in texto:
        return "Juros"

    if "VENCIMENTO" in texto or "RESGATE" in texto:
        return "Vencimento"

    # Ajuste de pagamento sem indicar juros ou amortização.
    if natureza == "ajuste":
        return "Ajuste"

    # Prêmio identificado somente pelo código 960.
    if natureza == "premio":
        return "Premio"

    # Exemplo:
    # ESTORNO DO PAGAMENTO NAO LIQUIDADO MOVIA3
    #
    # O comentário informa que é estorno, mas não informa
    # se o evento original era juros ou amortização.
    return None


def preparar_lista_ativos(depara_lastros):
    """
    Extrai os ativos existentes no de-para.

    Exemplo de entrada:

        {
            ("LZ", "4918952"): "MOVIA3",
            ("XZ", "1234567"): "XPTO12",
        }

    Resultado:

        ["XPTO12", "MOVIA3"]
    """
    validar_depara_lastros(depara_lastros)

    ativos = {
        str(ativo).strip().upper()
        for ativo in depara_lastros.values()
        if pd.notna(ativo) and str(ativo).strip()
    }

    # Procura primeiro os códigos maiores.
    return sorted(
        ativos,
        key=len,
        reverse=True,
    )


def identificar_ativo(
    comentario,
    ativos_conhecidos,
):
    """
    Procura no comentário um ativo existente na lista conhecida.

    A função não tenta adivinhar ativos que não estejam
    no DataFrame de lastros.
    """
    texto = normalizar_texto(comentario)

    for ativo in ativos_conhecidos:
        ativo_normalizado = normalizar_texto(ativo)

        padrao = rf"(?<![A-Z0-9])" rf"{re.escape(ativo_normalizado)}" rf"(?![A-Z0-9])"

        if re.search(padrao, texto):
            return ativo

    return None



def interpretar_comentario(
    comentario,
    mttp_cd,
    ativos_conhecidos,
):
    """
    Identifica natureza, evento e ativo do comentário.
    """
    natureza = identificar_natureza(
        comentario=comentario,
        mttp_cd=mttp_cd,
    )

    evento = identificar_evento(
        comentario=comentario,
        natureza=natureza,
    )

    ativo = identificar_ativo(
        comentario=comentario,
        ativos_conhecidos=ativos_conhecidos,
    )

    return {
        "natureza": natureza,
        "evento": evento,
        "ativo": ativo,
    }


def interpretar_comentarios_dataframe(df, ativos_conhecidos):
    """
    Interpreta todos os comentários do DataFrame.
    """
    df = df.copy()

    if df.empty:
        df["natureza"] = pd.Series(dtype="object")
        df["evento"] = pd.Series(dtype="object")
        df["ativo"] = pd.Series(dtype="object")

        return df

    interpretacoes = df.apply(
        lambda row: interpretar_comentario(
            comentario=row["DS"],
            mttp_cd=row["MTTP_CD"],
            ativos_conhecidos=ativos_conhecidos,
        ),
        axis=1,
    )

    df_interpretado = pd.DataFrame(
        interpretacoes.tolist(),
        index=df.index,
    )

    df = pd.concat(
        [
            df,
            df_interpretado,
        ],
        axis=1,
    )

    return df



def valor_ou_none(valor):
    """
    Converte valores vazios ou NaN para None.
    """
    if pd.isna(valor):
        return None

    if isinstance(valor, str) and not valor.strip():
        return None

    return valor


def montar_origem_caixa(row):
    """
    Monta o dicionário de rastreabilidade do lançamento.
    """
    return {
        "sistema": "sac_caixa",
        "mttp_cd": row["MTTP_CD"],
        "comentario": row["DS"],
        "natureza": row["natureza"],
        "evento": valor_ou_none(row["evento"]),
        "id": valor_ou_none(row.get("ID")),
        "valor_original": valor_ou_none(row["VL_ORIGINAL"]),
    }



def listar_comentarios_unicos(
    df,
    mascara,
):
    """
    Retorna uma lista de comentários únicos.
    """
    return (
        df.loc[
            mascara,
            "DS",
        ]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda serie: serie.ne("")]
        .drop_duplicates()
        .tolist()
    )


def montar_diagnostico_caixa(
    df_original,
    df_interpretado,
    df_normalizado,
    descartados,
):
    """
    Monta o diagnóstico da normalização.
    """
    return {
        "linhas_lidas": len(df_original),
        "linhas_apos_filtro": len(df_interpretado),
        "linhas_normalizadas": len(df_normalizado),
        "descartados": descartados,
        "ativos_nao_encontrados": (
            listar_comentarios_unicos(
                df=df_interpretado,
                mascara=df_interpretado["ativo"].isna(),
            )
        ),
        "naturezas_nao_identificadas": (
            listar_comentarios_unicos(
                df=df_interpretado,
                mascara=df_interpretado["natureza"].isna(),
            )
        ),
        "eventos_nao_identificados": (
            listar_comentarios_unicos(
                df=df_interpretado,
                mascara=df_interpretado["evento"].isna(),
            )
        ),
        "valores_invalidos": (
            listar_comentarios_unicos(
                df=df_interpretado,
                mascara=df_interpretado["VL"].isna(),
            )
        ),
    }



def normalizar_VCRADREC( caminho_caixa, depara_lastros, tipo_sac_operacao=None,):

    df_original = ler_sac_caixa(caminho_caixa)

    validar_colunas_sac_caixa(df_original)

    df = limpar_colunas_sac_caixa(df_original)

    df, descartados = filtrar_lancamentos_caixa_validos(df)

    ativos_conhecidos = preparar_lista_ativos(
        depara_lastros
    )

    df = interpretar_comentarios_dataframe(
        df=df,
        ativos_conhecidos=ativos_conhecidos,
    )

    # Para entrar no resultado final, é necessário:
    #
    # - identificar a natureza;
    # - identificar o ativo;
    # - possuir um valor numérico válido.
    #
    # O evento pode ficar vazio em casos de estorno genérico.
    mascara_valida = df["natureza"].notna() & df["ativo"].notna() & df["VL"].notna()

    df_normalizado = df.loc[mascara_valida].copy()

    df_normalizado["origem"] = df_normalizado.apply(
        montar_origem_caixa,
        axis=1,
    )

    df_normalizado = df_normalizado.rename(
        columns={
            "CD_SISTEMA": "base",
            "CLCLI_CD": "carteira",
            "DT": "data",
            "VL": "valor",
        }
    )

    colunas_resultado = [
        "base",
        "carteira",
        "ativo",
        "evento",
        "data",
        "valor",
        "natureza",
        "origem",
    ]

    df_normalizado = df_normalizado[colunas_resultado].reset_index(drop=True)

    diagnostico = montar_diagnostico_caixa(
        df_original=df_original,
        df_interpretado=df,
        df_normalizado=df_normalizado,
        descartados=descartados,
    )

    return df_normalizado, diagnostico
