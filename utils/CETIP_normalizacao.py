from utils.GLOBAL_functions import ErroDeCarga

import pandas as pd

COLUNAS_CETIP = {
    "conta": "Conta",
    "carteira": "Carteira",
    "titulo": "Título",
    "tipo_titulo": "Tipo Título",
    "cod": "CódOperação",
    "tipo_op": "Tipo Operação",
    "qt": "Quantidade",
    "pu": "PU",
    "valor": "Valor",
    "status": "Status",
    "data_liq": "Data Liquidação",
    "data_venc": "Data Vencimento",
    "base": "Base",
}


def validar_colunas_cetip(df):
    """Valida se todas as colunas necessárias existem no arquivo."""

    colunas_faltantes = set(COLUNAS_CETIP.values()) - set(df.columns)

    if colunas_faltantes:
        raise ErroDeCarga(f"CETIP sem colunas: {colunas_faltantes}")


def limpar_colunas_cetip(df):
    """Remove espaços das colunas usadas como identificação."""

    colunas_para_limpar = [
        "carteira",
        "titulo",
        "cod",
    ]

    for chave_coluna in colunas_para_limpar:
        nome_coluna = COLUNAS_CETIP[chave_coluna]

        df[nome_coluna] = df[nome_coluna].astype(str).str.strip()


def carteira_sem_depara(carteira):
    """Verifica se a carteira não possui de-para."""

    return not carteira or carteira.lower() in (
        "nan",
        "----",
        "conta-sem-depara",
    )


def montar_linha_cetip(row, carteira, codigo_operacao, evento):
    """Monta uma linha da CETIP no formato normalizado."""

    C = COLUNAS_CETIP

    return {
        "base": str(row[C["base"]]).strip(),
        "carteira": carteira,
        "ativo": str(row[C["titulo"]]).strip(),
        "evento": evento,
        "data": row[C["data_liq"]],
        "valor": row[C['valor']],
        "origem": {
            "sistema": "cetip",
            "conta": row[C["conta"]],
            "tipo_titulo": row[C["tipo_titulo"]],
            "cod": codigo_operacao,
            "descricao": row[C["tipo_op"]],
            "status": row[C["status"]],
            "qt": row[C['qt']],
            "pu": row[C['pu']],
            "data_venc": row[C["data_venc"]],
        },
    }


def montar_diagnostico_cetip(
    df,
    resultado,
    sem_depara_carteira,
    eventos_nao_mapeados,
):
    """Monta o diagnóstico do processamento."""

    return {
        "linhas_lidas": len(df),
        "linhas_normalizadas": len(resultado),
        "sem_depara_carteira": sorted(set(sem_depara_carteira)),
        "eventos_nao_mapeados": sorted(set(eventos_nao_mapeados)),
    }


def normalizar_CETIP(df, mapa_cetip):
    C = COLUNAS_CETIP

    validar_colunas_cetip(df)
    limpar_colunas_cetip(df)

    linhas_normalizadas = []
    sem_depara_carteira = []
    eventos_nao_mapeados = []

    for _, row in df.iterrows():
        carteira = str(row[C["carteira"]]).strip()

        codigo_operacao = str(row[C["cod"]]).strip()

        # PORTÃO 1 — carteira sem de-para
        if carteira_sem_depara(carteira):
            sem_depara_carteira.append(row[C["conta"]])
            continue

        # PORTÃO 2 — evento não mapeado
        evento = mapa_cetip.get(codigo_operacao)

        if evento is None:
            eventos_nao_mapeados.append(
                (
                    codigo_operacao,
                    row[C["tipo_op"]],
                )
            )
            continue

        linha_normalizada = montar_linha_cetip(
            row=row,
            carteira=carteira,
            codigo_operacao=codigo_operacao,
            evento=evento,
        )

        linhas_normalizadas.append(linha_normalizada)

    resultado = pd.DataFrame(linhas_normalizadas)

    diagnostico = montar_diagnostico_cetip(
        df=df,
        resultado=resultado,
        sem_depara_carteira=sem_depara_carteira,
        eventos_nao_mapeados=eventos_nao_mapeados,
    )

    return resultado, diagnostico
