"""
bot_engine.py
-------------
Orquestrador da conversa — implementa o fluxo do prompt mestre:

  Cliente -> WhatsApp -> [escalonamento? ] -> Identificação (segura) do
  cliente/processo -> Consulta ao ERP -> IA (Claude) interpreta e
  responde, com fallback determinístico se a IA não estiver configurada
  -> Registro do atendimento -> WhatsApp -> Cliente

Princípios (seção 27 do prompt mestre), aplicados aqui:
  1. Consultar antes de responder — toda resposta busca dados atuais
     no ERP (mock ou CONEXOS), nunca "inventa" a partir da conversa.
  2. Não inventar — campos ausentes no ERP nunca são preenchidos por
     suposição, nem pelos templates de fallback nem pela IA (instruída
     em system_prompt.py).
  3. Resolver ou escalar — perguntas rotineiras são respondidas direto;
     situações sensíveis (seção 17) são encaminhadas para humano.
"""

import os
import re
from datetime import datetime

import db
import erp_mock
import conexos_connector
import escalonamento
import ia_followup

ERP_BACKEND = os.environ.get("ERP_BACKEND", "mock").strip().lower()
_erp = conexos_connector if ERP_BACKEND == "conexos" else erp_mock

# -----------------------------------------------------------------------
# Extração de identificadores
# -----------------------------------------------------------------------
_RE_CONTAINER = re.compile(r"\b([A-Za-z]{4}\d{7})\b")
_RE_PROCESSO = re.compile(r"\b([A-Za-z]{2}-[A-Za-z]{2}-\d{3,6}/\d{2})\b")
_RE_BL = re.compile(r"\b([A-Za-z]{4}BS\d{6,8})\b", re.IGNORECASE)

_SAUDACOES = {"oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", "e ai", "eai"}


def extrair_identificador(texto: str):
    texto = texto or ""
    for regex in (_RE_PROCESSO, _RE_CONTAINER, _RE_BL):
        m = regex.search(texto)
        if m:
            return m.group(1)
    return None


def _normaliza_telefone(telefone: str) -> str:
    return "".join(ch for ch in (telefone or "") if ch.isdigit())


def _formata_data_br(data_iso):
    if not data_iso:
        return None
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


# -----------------------------------------------------------------------
# Identificação segura do cliente/processo (determinística — nunca
# delegada à IA, por segurança/LGPD: seção 19 do prompt mestre)
# -----------------------------------------------------------------------

def identificar(telefone: str, texto: str):
    """
    Retorna um dict:
        {"situacao": "ok" | "multiplos" | "nao_encontrado"
                    | "sem_cadastro" | "verificacao_necessaria",
         "processo": dict|None,
         "processos": list}
    """
    identificador = extrair_identificador(texto)
    tel = _normaliza_telefone(telefone)

    if identificador:
        try:
            processo = _erp.buscar_processo_por_identificador(identificador)
        except NotImplementedError:
            return {"situacao": "backend_nao_configurado", "processo": None, "processos": []}

        if not processo:
            return {"situacao": "nao_encontrado", "processo": None, "processos": []}

        telefone_dono = _normaliza_telefone(processo.get("telefone_cliente", ""))
        if telefone_dono and telefone_dono != tel:
            # Identificador existe, mas quem está perguntando não é o
            # telefone cadastrado para esse processo — não entregamos
            # dados sem confirmar identidade (LGPD/segurança).
            return {"situacao": "verificacao_necessaria", "processo": processo, "processos": []}

        return {"situacao": "ok", "processo": processo, "processos": [processo]}

    try:
        processos_cliente = _erp.buscar_processos_por_telefone(telefone)
    except NotImplementedError:
        return {"situacao": "backend_nao_configurado", "processo": None, "processos": []}

    if len(processos_cliente) == 1:
        return {"situacao": "ok", "processo": processos_cliente[0], "processos": processos_cliente}
    if len(processos_cliente) > 1:
        return {"situacao": "multiplos", "processo": None, "processos": processos_cliente}
    return {"situacao": "sem_cadastro", "processo": None, "processos": []}


# -----------------------------------------------------------------------
# Respostas determinísticas (usadas para identificação e como fallback
# quando a IA não está configurada/disponível)
# -----------------------------------------------------------------------

def montar_resposta_lista(processos: list) -> str:
    linhas = ["Encontrei mais de um processo em andamento no seu cadastro. Sobre qual deles você quer saber?", ""]
    for p in processos:
        etapa = p["info_processo"].get("etapa_atual", "em andamento")
        linhas.append(f"• *{p['processo']}* — {etapa}")
    linhas.append("")
    linhas.append("Pode responder só com o número do processo (ex: RO-OE-0009/26) ou o número do container.")
    return "\n".join(linhas)


def montar_resposta_fallback(processo: dict) -> str:
    """
    Template determinístico usado quando ANTHROPIC_API_KEY não está
    configurada. É deliberadamente mais simples que a resposta gerada
    pela IA, mas segue a mesma regra de nunca inventar dados ausentes.
    """
    ip = processo["info_processo"]
    ic = processo["info_carga"]
    ia = processo["info_aduaneira"]
    ie = processo["info_entrega"]

    linhas = [f"📦 *Processo {processo['processo']}*", f"Etapa atual: {ip['etapa_atual']}"]

    if ic.get("data_chegada"):
        linhas.append(f"Chegada ao Brasil: {_formata_data_br(ic['data_chegada'])} ({ic.get('terminal') or 'terminal não informado'})")
    elif ic.get("eta"):
        linhas.append(f"Previsão de chegada (ETA): {_formata_data_br(ic['eta'])}")
    else:
        linhas.append("Ainda não há data de chegada confirmada no sistema.")

    if ia.get("canal"):
        linhas.append(f"Canal de parametrização: {ia['canal']}")
    if ia.get("exigencia"):
        linhas.append(f"Pendência aduaneira: {ia['exigencia']}")
    if processo["info_financeira"].get("pendencias_financeiras"):
        linhas.append("Pendência financeira: " + "; ".join(processo["info_financeira"]["pendencias_financeiras"]))

    if ie.get("data_efetiva_entrega"):
        linhas.append(f"Entrega concluída em {_formata_data_br(ie['data_efetiva_entrega'])}.")
    elif ie.get("data_prevista_entrega"):
        rotulo = "confirmada" if ie.get("tipo_previsao_entrega") == "confirmada" else "estimada (pode mudar)"
        linhas.append(f"Previsão de entrega: {_formata_data_br(ie['data_prevista_entrega'])} ({rotulo})")
    else:
        linhas.append("Ainda não há previsão de entrega confirmada no sistema.")

    linhas.append(f"(última atualização no sistema: {_formata_data_br(processo['ultima_atualizacao'])})")
    return "\n".join(linhas)


_MSG_NAO_ENCONTRADO = (
    "Não localizei nenhum processo com esse identificador. 🕵️\n"
    "Pode confirmar o número do processo, container ou BL? "
    "Se preferir, um dos nossos atendentes pode te ajudar."
)

_MSG_SEM_IDENTIFICADOR_SEM_CADASTRO = (
    "Olá! Para eu consultar o status da sua carga, me envie o número do "
    "processo (ex: RO-OE-0009/26), do container (ex: MSCU1234567) ou do BL."
)

_MSG_VERIFICACAO_NECESSARIA = (
    "Para sua segurança, antes de compartilhar informações desse processo "
    "preciso confirmar sua identidade. Pode me informar o nome ou CNPJ da "
    "empresa vinculada a esse processo?"
)

_MSG_BACKEND_NAO_CONFIGURADO = (
    "No momento não consigo consultar o sistema para responder isso — "
    "um atendente vai te ajudar em breve. (motivo interno: integração "
    "com o CONEXOS ainda não configurada)"
)


def _registrar(telefone, texto, resultado):
    db.registrar_mensagem(telefone, "cliente", texto)
    db.registrar_mensagem(telefone, "bot", resultado["resposta"])
    db.registrar_atendimento(
        telefone=telefone,
        cliente=(resultado.get("processo") or {}).get("cliente"),
        processo=(resultado.get("processo") or {}).get("processo"),
        pergunta=texto,
        dados_consultados=resultado.get("processo"),
        resposta=resultado["resposta"],
        acao=resultado["acao"],
        confianca=resultado.get("confianca"),
        encaminhado=resultado.get("escalar", False),
        motivo_encaminhamento=resultado.get("motivo_escalonamento"),
        tempo_resposta_ms=resultado.get("tempo_resposta_ms"),
    )


def responder(telefone_remetente: str, texto: str) -> dict:
    """
    Ponto de entrada principal. Retorna:
        {"resposta": str, "resolvido": bool, "processo": dict|None,
         "acao": str, "confianca": str|None, "escalar": bool,
         "motivo_escalonamento": str|None}
    Também registra a interação em db.py (histórico + auditoria).
    """
    texto = (texto or "").strip()

    with db.Cronometro() as cronometro:
        resultado = _responder_interno(telefone_remetente, texto)

    resultado["tempo_resposta_ms"] = cronometro.duracao_ms
    _registrar(telefone_remetente, texto, resultado)
    return resultado


def _responder_interno(telefone_remetente: str, texto: str) -> dict:
    # 1) Rede de segurança determinística — sempre roda primeiro.
    motivo, descricao = escalonamento.detectar(texto)
    if motivo:
        return {
            "resposta": escalonamento.MENSAGEM_ESCALONAMENTO,
            "resolvido": False,
            "processo": None,
            "acao": "escalonamento_palavra_chave",
            "confianca": None,
            "escalar": True,
            "motivo_escalonamento": descricao,
        }

    # 2) Identificação seguindo regras de segurança/propriedade.
    ident = identificar(telefone_remetente, texto)
    situacao = ident["situacao"]

    if situacao == "backend_nao_configurado":
        return {
            "resposta": _MSG_BACKEND_NAO_CONFIGURADO, "resolvido": False, "processo": None,
            "acao": "erro_backend_nao_configurado", "confianca": None,
            "escalar": True, "motivo_escalonamento": "Integração com o CONEXOS não configurada",
        }

    if situacao == "multiplos":
        return {
            "resposta": montar_resposta_lista(ident["processos"]), "resolvido": False, "processo": None,
            "acao": "lista_processos", "confianca": None, "escalar": False, "motivo_escalonamento": None,
        }

    if situacao == "nao_encontrado":
        return {
            "resposta": _MSG_NAO_ENCONTRADO, "resolvido": False, "processo": None,
            "acao": "identificador_nao_encontrado", "confianca": None, "escalar": False,
            "motivo_escalonamento": None,
        }

    if situacao == "verificacao_necessaria":
        return {
            "resposta": _MSG_VERIFICACAO_NECESSARIA, "resolvido": False, "processo": None,
            "acao": "verificacao_necessaria", "confianca": None, "escalar": False,
            "motivo_escalonamento": None,
        }

    if situacao == "sem_cadastro":
        if texto.lower() in _SAUDACOES or len(texto) < 6:
            resposta = (
                "Olá! 👋 Sou a IA de acompanhamento de importações da SeletoComex. "
                "Me envie o número do processo, do container ou do BL que eu já "
                "consulto o status mais recente da sua carga."
            )
        else:
            resposta = _MSG_SEM_IDENTIFICADOR_SEM_CADASTRO
        return {
            "resposta": resposta, "resolvido": False, "processo": None,
            "acao": "pedir_identificador", "confianca": None, "escalar": False,
            "motivo_escalonamento": None,
        }

    # situacao == "ok" -> temos um processo confirmado como do cliente.
    processo = ident["processo"]
    historico = db.obter_historico(telefone_remetente, limite=8)

    resultado_ia = ia_followup.gerar_resposta(processo, historico, texto)

    if resultado_ia:
        return {
            "resposta": resultado_ia["resposta"],
            "resolvido": not resultado_ia["escalar"],
            "processo": processo,
            "acao": "escalonamento_ia" if resultado_ia["escalar"] else "resposta_ia",
            "confianca": resultado_ia["confianca"],
            "escalar": resultado_ia["escalar"],
            "motivo_escalonamento": resultado_ia["motivo_escalonamento"],
        }

    # Fallback determinístico (sem ANTHROPIC_API_KEY configurada, ou
    # falha na chamada à IA) — nunca deixa o cliente sem resposta.
    return {
        "resposta": montar_resposta_fallback(processo),
        "resolvido": True,
        "processo": processo,
        "acao": "resposta_fallback",
        "confianca": None,
        "escalar": False,
        "motivo_escalonamento": None,
    }
