"""
app.py
------
Servidor do bot de FOLLOWUP de importações.

Expõe:
  - GET  /                -> interface de chat (para testar sem WhatsApp real)
  - POST /api/chat         -> usado pela interface de chat
  - GET  /webhook          -> verificação do webhook (padrão Meta Cloud API)
  - POST /webhook          -> recebimento de mensagens (padrão Meta Cloud API)
  - GET  /painel           -> painel de controle (métricas de atendimento)
  - GET  /painel/api/stats -> dados (JSON) que alimentam o painel

Como rodar:
    pip install -r requirements.txt
    uvicorn app:app --reload --port 8000
"""

import os

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bot_engine
import db

app = FastAPI(title="SeletoComex - IA de Followup de Importações")

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "seletocomex-dev-token")


class ChatIn(BaseModel):
    telefone: str
    mensagem: str


class ChatOut(BaseModel):
    resposta: str
    resolvido: bool
    acao: str
    confianca: str | None = None
    escalar: bool = False


@app.post("/api/chat", response_model=ChatOut)
def api_chat(payload: ChatIn):
    """Endpoint usado pela UI de demonstração (static/index.html)."""
    resultado = bot_engine.responder(payload.telefone, payload.mensagem)
    return ChatOut(
        resposta=resultado["resposta"],
        resolvido=resultado["resolvido"],
        acao=resultado["acao"],
        confianca=resultado.get("confianca"),
        escalar=resultado.get("escalar", False),
    )


# -----------------------------------------------------------------------
# Painel de controle (seção 22 do prompt mestre)
# -----------------------------------------------------------------------

@app.get("/painel")
def painel_pagina():
    return FileResponse("static/painel.html")


@app.get("/painel/api/stats")
def painel_stats():
    return JSONResponse({
        "resumo": db.stats_resumo(),
        "processos_mais_consultados": db.stats_processos_mais_consultados(),
        "motivos_encaminhamento": db.stats_motivos_encaminhamento(),
        "acoes": db.stats_acoes(),
        "atendimentos_por_dia": db.stats_atendimentos_por_dia(),
        "recentes": db.listar_atendimentos_recentes(limite=20),
    })


# -----------------------------------------------------------------------
# Webhook no formato da Meta Cloud API (WhatsApp Business Platform)
# -----------------------------------------------------------------------

@app.get("/webhook")
def verificar_webhook(request: Request):
    """A Meta chama este endpoint uma vez, na hora de configurar o webhook."""
    params = request.query_params
    modo = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if modo == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(challenge)
    return PlainTextResponse("Token de verificação inválido", status_code=403)


@app.post("/webhook")
async def receber_webhook(request: Request):
    """Recebe mensagens reais do WhatsApp Business (formato Meta Cloud API)."""
    body = await request.json()

    try:
        entry = body["entry"][0]
        change = entry["changes"][0]
        value = change["value"]
        mensagem = value["messages"][0]
        telefone = mensagem["from"]
        texto = mensagem.get("text", {}).get("body", "")
    except (KeyError, IndexError):
        return {"status": "ignorado"}

    resultado = bot_engine.responder(telefone, texto)
    enviar_mensagem_whatsapp(telefone, resultado["resposta"])

    return {"status": "ok", "acao": resultado["acao"], "escalar": resultado.get("escalar", False)}


def enviar_mensagem_whatsapp(telefone_destino: str, texto: str):
    """
    STUB — em produção, aqui vai a chamada real à API do WhatsApp Business
    (Meta Cloud API) para enviar a resposta de volta ao cliente.

        import requests
        WHATSAPP_TOKEN = os.environ["WHATSAPP_TOKEN"]
        PHONE_NUMBER_ID = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
        url = f"https://graph.facebook.com/v20.0/{PHONE_NUMBER_ID}/messages"
        headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
        payload = {
            "messaging_product": "whatsapp", "to": telefone_destino,
            "type": "text", "text": {"body": texto},
        }
        requests.post(url, headers=headers, json=payload, timeout=10)
    """
    print(f"[WHATSAPP -> {telefone_destino}] {texto}")


# Serve a interface de chat e o painel (arquivos estáticos em /static)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
