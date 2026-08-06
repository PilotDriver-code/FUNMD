import re
import unicodedata

import pandas as pd

from utils.GLOBAL_functions import ErroDeCarga

COLUNAS_OBRIGATORIAS_CAIXA = {
    "CD_SISTEMA",
    "CLCLI_CD",
    "DT",
    "VL",
    "DS",
    "MTTP_CD",
    "ORIGEM",
}

COLUNAS_LIMPEZA_CAIXA = [
    "CD_SISTEMA",
    "CLCLI_CD",
    "MTTP_CD",
    "ORIGEM",
]

# Apenas estes codigos entram. 960 = premio (vira evento comparavel com a CETIP);
# 803 = complemento "caixa". Todo o resto (RF, CL, 965, 262, 81, 100...) e descartado.
CODIGO_PREMIO = "960"
CODIGO_CAIXA = "803"
CODIGOS_MT_ACEITOS = {CODIGO_PREMIO, CODIGO_CAIXA}


def ler_caixa(caminho_caixa):
    """Le o arquivo SAC Caixa."""
    return pd.read_csv(caminho_caixa, sep=";", encoding="utf-8-sig")


def validar_colunas_caixa(df):
    """Valida se todas as colunas obrigatorias existem."""
    colunas_faltantes = COLUNAS_OBRIGATORIAS_CAIXA - set(df.columns)
    if colunas_faltantes:
        raise ErroDeCarga(f"Arquivo CAIXA sem colunas: {colunas_faltantes}")


def limpar_colunas_caixa(df):
    """Remove espacos das colunas de identificacao."""
    for coluna in COLUNAS_LIMPEZA_CAIXA:
        df[coluna] = df[coluna].astype(str).str.strip()


def sem_acento(texto):
    """Remove acentos para comparar texto sem depender de encoding."""
    if not isinstance(texto, str):
        return ""
    forma = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in forma if not unicodedata.combining(c))


def tokenizar_comentario(comentario):
    """Quebra o comentario em tokens por espaco, hifen, colchete e barra."""
    if not isinstance(comentario, str):
        return []
    return [t for t in re.split(r"[\s\-\[\]/]+", comentario) if t]


def buscar_ativo_no_comentario(comentario, ativos_conhecidos):
    """
    Busca por TOKEN INTEIRO: quebra o comentario em palavras e verifica se
    alguma delas E exatamente um ativo conhecido (valores do de-para).
    Devolve o ativo encontrado ou None.
    """
    tokens = tokenizar_comentario(comentario)
    for token in tokens:
        if token in ativos_conhecidos:
            return token
    return None


def classificar_lancamento_caixa(codigo, comentario):
    """
    Decide evento, tipo de complemento e flag de postergacao.

    Retorna dict:
      evento     -> "Premio" (960) ou None (803, que e complemento sem evento)
      complemento-> True quando entra na coluna "caixa" (803)
      postergacao-> True quando o comentario indica POSTERGACAO ou ESTORNO
    """
    texto = sem_acento(comentario).upper()

    if codigo == CODIGO_PREMIO:
        return {"evento": "Prêmio", "complemento": False, "postergacao": False}

    # codigo == 803 -> complemento "caixa"
    eh_postergacao = ("POSTERGACAO" in texto) or ("ESTORNO" in texto)
    return {"evento": None, "complemento": True, "postergacao": eh_postergacao}


def montar_origem_caixa(registro, classificacao):
    """Preserva os dados originais para auditoria."""
    return {
        "sistema": "sac_caixa",
        "mttp_cd": registro.MTTP_CD,
        "comentario": registro.DS,
        "complemento": classificacao["complemento"],
        "postergacao": classificacao["postergacao"],
        "id": getattr(registro, "ID", None),
        "valor_original": registro.VL,
    }


def montar_linha_caixa(registro, ativo, classificacao):
    """Monta uma linha do Caixa no formato comum da conciliacao."""
    return {
        "base": registro.CD_SISTEMA,
        "carteira": registro.CLCLI_CD,
        "ativo": ativo,
        "evento": classificacao["evento"],  # "Prêmio" ou None (complemento)
        "data": registro.DT,
        "valor": registro.VL,
        "complemento": classificacao["complemento"],
        "postergacao": classificacao["postergacao"],
        "origem": montar_origem_caixa(registro, classificacao),
    }


def montar_diagnostico_caixa(df, resultado, descartados, ativos_nao_encontrados):
    """Monta o diagnostico do processamento."""
    return {
        "linhas_lidas": len(df),
        "linhas_normalizadas": len(resultado),
        "descartados": descartados,
        "ativos_nao_encontrados": ativos_nao_encontrados,
    }


def normalizar_CAIXA(caminho_caixa, de_para_lastro):
    """
    Normaliza o SAC Caixa.

    de_para_lastro: dict {(base, lastro): ativo} vindo de construir_traducao_lastro.
                    Usamos os VALORES (ativos conhecidos) para achar o ativo
                    dentro do comentario, por token inteiro.

    Regras:
      - so ORIGEM == "MT"
      - so MTTP_CD 960 (premio) e 803 (complemento "caixa")
      - ativo vem da busca por token no comentario (nao da posicao no texto)
      - 960 -> evento "Prêmio" ; 803 -> complemento, com flag de postergacao
      - ativo nao encontrado -> avisos (nunca chuta)
    """
    df = ler_caixa(caminho_caixa)
    validar_colunas_caixa(df)
    limpar_colunas_caixa(df)

    ativos_conhecidos = set(de_para_lastro.values())

    linhas_normalizadas = []
    ativos_nao_encontrados = []
    descartados = {"origem_nao_mt": 0, "codigo_ignorado": 0}

    for registro in df.itertuples():
        # PORTAO 1 — so ORIGEM MT
        if registro.ORIGEM != "MT":
            descartados["origem_nao_mt"] += 1
            continue

        # PORTAO 2 — so 960 e 803
        if registro.MTTP_CD not in CODIGOS_MT_ACEITOS:
            descartados["codigo_ignorado"] += 1
            continue

        # PORTAO 3 — achar o ativo por token no comentario
        ativo = buscar_ativo_no_comentario(registro.DS, ativos_conhecidos)
        if ativo is None:
            ativos_nao_encontrados.append(registro.DS)
            continue

        classificacao = classificar_lancamento_caixa(registro.MTTP_CD, registro.DS)

        linha = montar_linha_caixa(registro, ativo, classificacao)
        linhas_normalizadas.append(linha)

    resultado = pd.DataFrame(linhas_normalizadas)

    diagnostico = montar_diagnostico_caixa(
        df=df,
        resultado=resultado,
        descartados=descartados,
        ativos_nao_encontrados=ativos_nao_encontrados,
    )

    return resultado, diagnostico
