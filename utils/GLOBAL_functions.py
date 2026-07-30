import json
from pathlib import Path

class ErroDeCarga(Exception):
    """Falha que deve PARAR a execução (arquivos incoerentes), não virar saída."""


def header(titulo):
    largura = 50

    titulo_formatado = f" {titulo} "
    espaco_restante = largura - len(titulo_formatado)

    lado_esquerdo = espaco_restante // 2
    lado_direito = espaco_restante - lado_esquerdo

    print()
    print(("-=" * 30)[:lado_esquerdo] + titulo_formatado + ("-=" * 30)[:lado_direito])


def carregar_mapa_eventos(caminho="mapa_eventos.json"):
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    return (
        dados["tipo_sac_operacao"],
        dados["tipo_codigo_op_CETIP"],
        dados["tipo_titulo_CETIP"],
        dados["tipo_titulo_SAC"],
    )
