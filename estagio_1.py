# ********* IMPORTS -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

import os
import pandas as pd
from pathlib import Path
import json

from utils.CETIP_pre_tratamento import pre_tratamento_CETIP
from utils.SAC_depara_lastros import construir_traducao_lastro
from utils.GLOBAL_functions import carregar_mapa_eventos, header

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

# ********* PRE TRATAMENTO CETIP - Inclue conta + base no arq de operacoes_CETIP -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

df_CETIP_pre   = pre_tratamento_CETIP(ARQUIVOS["CETIP"], ARQUIVOS["CONTA"], tipo_codigo_op_CETIP, tipo_titulo_CETIP)

# ********* DE PARA LASTRO - Olha para o arquivo de posição e faz um depara com os lastros -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

depara_lastros = construir_traducao_lastro(ARQUIVOS["POSICAO"], tipo_titulo_SAC)

header("DE_PARA_LASTROS_SAC")
(depara_lastros)
