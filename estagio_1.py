# ********* IMPORTS -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import os
import pandas as pd
from pathlib import Path
import json

from utils.CETIP_consolidacao import consolidar_eventos
from utils.GLOBAL_functions import carregar_mapa_eventos, header, limpar_terminal, salvar_arquivo_xlsx

from utils.CETIP_normalizacao import normalizar_CETIP
from utils.CETIP_pre_tratamento import pre_tratamento_CETIP
from utils.SAC_depara_lastros import construir_traducao_lastro
from utils.SAC_normalizacao_VCRAOPRF import normalizar_VCRAOPRF
from utils.SAC_normalizacao_VCRADREC import normalizar_VCRADREC

# ********* CONFIG DE CAMINHOS + VARIAVEL DE AMBIENTE -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

PASTA_ATUAL = Path(__file__).resolve().parent

ARQUIVOS = {
    "CAIXA":    PASTA_ATUAL / "input" / "CAIXA.txt",
    "CONTA":    PASTA_ATUAL / "input" / "CONTA.txt",
    "CETIP":    PASTA_ATUAL / "input" / "CETIP.txt",
    "POSICAO":  PASTA_ATUAL / "input" / "VCRAPRF.txt",
    "OPERACAO": PASTA_ATUAL / "input" / "VCRAOPRF.txt",
    "CONFIG":   PASTA_ATUAL / "config.json"
}

tipo_sac_operacao, tipo_codigo_op_CETIP, tipo_titulo_CETIP, tipo_titulo_SAC = carregar_mapa_eventos(ARQUIVOS["CONFIG"])

limpar_terminal()

# ********* PRE TRATAMENTO CETIP - Inclue conta + base no arq de operacoes_CETIP -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
header("PRE-TRATAMENTO CETIP")

df_CETIP_pre   = pre_tratamento_CETIP(ARQUIVOS["CETIP"], ARQUIVOS["CONTA"], tipo_codigo_op_CETIP, tipo_titulo_CETIP)
salvar_arquivo_xlsx("./trash/PRE-TRATAMENTO", df_CETIP_pre)

print(f"PRE-TRATAMENTO CETIP: {len(df_CETIP_pre)} linhas")

# ********* DE PARA LASTRO - Olha para o arquivo de posição e faz um depara com os lastros -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

header("DE_PARA_LASTROS_SAC")

depara_lastros = construir_traducao_lastro(ARQUIVOS["POSICAO"], tipo_titulo_SAC)
print(depara_lastros)
print(f"DE-PARA LASTROS SAC: {len(depara_lastros)} linhas")

print(type(depara_lastros))
# ********* NORMALIZA CETIP - Olha para o arquivo de CETIP e organiza ele no padrao esperado -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
header("NORMALIZA CETIP")

normalizar_CETIP, diagnostico_CETIP = normalizar_CETIP(df_CETIP_pre, tipo_codigo_op_CETIP)
salvar_arquivo_xlsx("./trash/NORMALIZA_CETIP", normalizar_CETIP)

print(f"NORMALIZA CETIP: {len(normalizar_CETIP)} linhas")

# ********* CONSOLIDA CETIP - Faz agrupamento de eventos iguais + Vencimento de ativos  -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
header("CONSOLIDA CETIP")
consolidado = consolidar_eventos(normalizar_CETIP)
salvar_arquivo_xlsx("./trash/CONSOLIDA_CETIP", consolidado)

# ********* NORMALIZA SAC OPERACAO - Olha para o arquivo de OPERACAO e organiza ele no padrao  -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

header("NORMALIZA SAC OPERACAO")

normalizar_SAC_OPERACAO, diagnostico_SAC_OPERACAO = normalizar_VCRAOPRF(ARQUIVOS["OPERACAO"], depara_lastros, tipo_sac_operacao)
salvar_arquivo_xlsx("./trash/NORMALIZA _SAC_OPERACAO", normalizar_SAC_OPERACAO)


# ********* NORMALIZA SAC OPERACAO - Olha para o arquivo de OPERACAO e organiza ele no padrao  -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
header("NORMALIZA SAC CAIXA")

normalizar_SAC_CAIXA, diagnostico_SAC_CAIXA = normalizar_VCRADREC(ARQUIVOS["CAIXA"], depara_lastros, tipo_sac_operacao)
salvar_arquivo_xlsx("./trash/NORMALIZA _SAC_CAIXA", normalizar_SAC_CAIXA)
print(diagnostico_SAC_CAIXA)
