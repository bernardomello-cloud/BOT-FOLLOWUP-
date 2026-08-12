"""
escalonamento.py
-----------------
Rede de segurança DETERMINÍSTICA (não depende de IA) para identificar
situações que devem ir direto para um atendente humano — conforme a
seção 17 do prompt mestre.

Esta checagem roda ANTES de qualquer chamada à IA. Mesmo que a camada
de IA (Claude) também tenha instrução de escalar em casos parecidos,
não queremos depender só do modelo para reconhecer uma reclamação
grave, uma questão jurídica ou um pedido explícito de falar com humano.
"""

import re

# Cada padrão é (motivo_interno, [regex, ...]). Case-insensitive.
_PADROES = [
    ("reclamacao_grave", [
        r"p[eé]ssimo", r"horr[ií]vel", r"absurdo", r"inaceit[aá]vel",
        r"revoltad[oa]", r"muito insatisfeit[oa]", r"v[ao]u? reclamar",
        r"reclama[cç][aã]o formal",
    ]),
    ("juridico", [
        r"jur[ií]dic", r"advogad[oa]", r"a[cç][aã]o judicial",
        r"processo judicial", r"na justi[cç]a", r"procon",
    ]),
    ("financeiro_cobranca", [
        r"cobran[cç]a indevida", r"cobraram errado", r"valor errado",
        r"n[aã]o vou pagar", r"multa indevida", r"fatura errada",
    ]),
    ("solicita_humano", [
        r"falar com (um |uma )?(atendente|humano|responsável|gerente|pessoa)",
        r"quero (um |uma )?(atendente|humano|responsável)",
        r"pode chamar (algu[eé]m|uma pessoa)",
        r"n[aã]o quero falar com (rob[oô]|bot|ia)",
    ]),
    ("alteracao_processo", [
        r"cancelar (o |a )?(processo|importa[cç][aã]o|carga)",
        r"alterar (o )?destino", r"mudar (o )?destino",
        r"trocar (a )?transportadora",
    ]),
    ("situacao_excepcional", [
        r"avaria", r"carga danificada", r"container danificado",
        r"roubo", r"furto", r"extravio", r"sinistro",
    ]),
]

_COMPILADOS = [
    (motivo, [re.compile(p, re.IGNORECASE) for p in padroes])
    for motivo, padroes in _PADROES
]

_DESCRICOES = {
    "reclamacao_grave": "Reclamação grave / cliente insatisfeito",
    "juridico": "Questão jurídica",
    "financeiro_cobranca": "Contestação financeira/cobrança",
    "solicita_humano": "Cliente pediu para falar com atendente humano",
    "alteracao_processo": "Solicitação de alteração operacional do processo",
    "situacao_excepcional": "Situação excepcional (avaria/extravio/sinistro)",
}


def detectar(texto: str):
    """
    Retorna (motivo_interno, descricao) se algum padrão bater, ou
    (None, None) se a mensagem parecer uma consulta rotineira de
    followup.
    """
    texto = texto or ""
    for motivo, regexes in _COMPILADOS:
        for regex in regexes:
            if regex.search(texto):
                return motivo, _DESCRICOES[motivo]
    return None, None


MENSAGEM_ESCALONAMENTO = (
    "Entendi. Para garantir que essa situação seja tratada corretamente, "
    "vou encaminhar sua solicitação para nossa equipe responsável. Em "
    "breve alguém vai continuar seu atendimento por aqui."
)
