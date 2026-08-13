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

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bot_engine
import db
import followup_semanal

app = FastAPI(title="SeletoComex - IA de Followup de Importações")

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "seletocomex-dev-token")
WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0")
CRON_SECRET = os.environ.get("CRON_SECRET")


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
# Resumo semanal de follow-up (toda sexta) — gera RASCUNHOS por cliente
# para a pessoa responsável revisar e enviar no grupo/conversa. A IA não
# entra em grupos (a API do WhatsApp Business não permite isso), então
# esse endpoint não manda nada pro cliente — só prepara os textos, que
# aparecem em /painel para copiar e colar.
#
# Disparado por um agendador EXTERNO (ex: GitHub Actions), porque o
# plano free do Render "dorme" e não confiável para agendar internamente.
# -----------------------------------------------------------------------

@app.post("/cron/followup-semanal")
def cron_followup_semanal(x_cron_secret: str | None = Header(default=None)):
    if not CRON_SECRET:
        raise HTTPException(status_code=500, detail="CRON_SECRET não configurado no servidor")
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    rascunhos = followup_semanal.gerar_rascunhos()
    lote = db.registrar_rascunhos_semanais(rascunhos)
    return {"status": "ok", "lote": lote, "clientes": len(rascunhos)}


@app.get("/painel/api/rascunhos-semanais")
def painel_rascunhos_semanais():
    return JSONResponse(db.listar_rascunhos_semanais_recentes())


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
    Envia a resposta de volta ao cliente via WhatsApp Business Platform
    (Meta Cloud API).

    Requer as variáveis de ambiente WHATSAPP_TOKEN e
    WHATSAPP_PHONE_NUMBER_ID configuradas (ex.: no Render, em
    "Environment"). Sem elas, cai em modo de log (não envia de verdade) —
    útil para testar pela interface de chat (/) sem gastar chamada de API.
    """
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_number_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")

    if not token or not phone_number_id:
        print(f"[WHATSAPP -> {telefone_destino}] (modo log, sem token configurado) {texto}")
        return

    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{phone_number_id}/messages"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": telefone_destino,
        "type": "text",
        "text": {"body": texto},
    }

    try:
        resposta = requests.post(url, headers=headers, json=payload, timeout=10)
        if resposta.status_code >= 400:
            print(f"[WHATSAPP ERRO] status={resposta.status_code} body={resposta.text}")
        else:
            print(f"[WHATSAPP -> {telefone_destino}] enviado (status {resposta.status_code})")
    except requests.RequestException as exc:
        print(f"[WHATSAPP ERRO] falha ao enviar para {telefone_destino}: {exc}")


# Serve a interface de chat e o painel (arquivos estáticos em /static)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
