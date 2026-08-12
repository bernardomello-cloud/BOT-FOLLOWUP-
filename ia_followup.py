"""
ia_followup.py
----------------
Camada que chama o Claude (Anthropic) para gerar a resposta rica e
humanizada, seguindo o system_prompt.py. Usa "tool use" para forçar uma
saída estruturada (resposta + confiança + escalonamento), em vez de
tentar interpretar texto livre.

Se ANTHROPIC_API_KEY não estiver configurada (ou a chamada falhar por
qualquer motivo), retorna None — bot_engine.py cai no modo fallback
(templates determinísticos), garantindo que o bot nunca trave por causa
desta camada.
"""

import json
import os

from system_prompt import SYSTEM_PROMPT, RESPONDER_CLIENTE_TOOL

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-opus-4-5-20251101")


def _montar_mensagens(contexto_processo, historico, mensagem_atual):
    """
    Monta a lista de mensagens no formato da API de Mensagens da
    Anthropic: histórico da conversa + a mensagem atual, com os dados
    do processo anexados como contexto na última mensagem do usuário.
    """
    mensagens = []
    for item in historico:
        papel = "assistant" if item["papel"] == "bot" else "user"
        mensagens.append({"role": papel, "content": item["texto"]})

    bloco_dados = (
        "DADOS DO PROCESSO (JSON, extraído do sistema — use somente isto, "
        "campos null significam informação não disponível):\n"
        f"{json.dumps(contexto_processo, ensure_ascii=False, indent=2)}\n\n"
        f"MENSAGEM DO CLIENTE:\n{mensagem_atual}"
    )
    mensagens.append({"role": "user", "content": bloco_dados})
    return mensagens


def gerar_resposta(contexto_processo: dict, historico: list, mensagem_atual: str):
    """
    Retorna um dict {"resposta": str, "confianca": str, "escalar": bool,
    "motivo_escalonamento": str|None} ou None se a IA não puder ser
    usada agora (sem chave configurada ou erro de chamada).
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        mensagens = _montar_mensagens(contexto_processo, historico, mensagem_atual)

        resp = client.messages.create(
            model=MODEL,
            max_tokens=800,
            system=SYSTEM_PROMPT,
            tools=[RESPONDER_CLIENTE_TOOL],
            tool_choice={"type": "tool", "name": "responder_cliente"},
            messages=mensagens,
        )

        for bloco in resp.content:
            if bloco.type == "tool_use" and bloco.name == "responder_cliente":
                dados = bloco.input
                return {
                    "resposta": dados.get("resposta", "").strip(),
                    "confianca": dados.get("confianca", "media"),
                    "escalar": bool(dados.get("escalar", False)),
                    "motivo_escalonamento": dados.get("motivo_escalonamento"),
                }
        return None
    except Exception:
        # Qualquer erro (rede, chave inválida, etc.) -> cai no fallback.
        # Em produção, vale registrar esse erro em log/monitoramento.
        return None
