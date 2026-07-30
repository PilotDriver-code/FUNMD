import pandas as pd

def merge_conta_base_CETIP(df_CETIP, df_CLIENTES):

    df_CETIP["Conta"] = df_CETIP["Conta"].astype(str).str.strip()
    df_CLIENTES["Conta"] = df_CLIENTES["Conta"].astype(str).str.strip()

    df = pd.merge(
        df_CETIP,
        df_CLIENTES[["Conta", "Carteira", "Base"]],
        how="left",
        on="Conta",
    )

    df["Carteira"] = df["Carteira"].fillna("contas_sem_depara")

    return df


def tratar_arquivo_CETIP(df_CETIP, tipo_codigo_op_CETIP, tipo_titulo_CETIP):

    df_CETIP["Conta"] = df_CETIP["Conta"].str.replace("-", "")
    df_CETIP = df_CETIP[df_CETIP["Tipo Título"].isin(tipo_titulo_CETIP)]
    df_CETIP["CódOperação"] = df_CETIP["CódOperação"].astype(str).str.strip()

    df_CETIP_FILTRADO = df_CETIP[df_CETIP["CódOperação"].isin(tipo_codigo_op_CETIP)]

    return df_CETIP_FILTRADO


def pre_tratamento_CETIP(
    caminho_CETIP, caminho_CONTA, tipo_codigo_op_CETIP, tipo_titulo_CETIP
):

    df_CETIP = pd.read_csv(caminho_CETIP, sep="\t")
    df_CLIENTES = pd.read_csv(caminho_CONTA, sep=";")

    df_CETIP_tratado = tratar_arquivo_CETIP(df_CETIP, tipo_codigo_op_CETIP, tipo_titulo_CETIP)
    df_CETIP = merge_conta_base_CETIP(df_CETIP_tratado, df_CLIENTES)

    return df_CETIP