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
from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import PlainTextResponse, JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import bot_engine
import conexos_planilha
import db
import followup_diario
import followup_semanal

app = FastAPI(title="SeletoComex - IA de Followup de Importações")

VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "seletocomex-dev-token")
WHATSAPP_API_VERSION = os.environ.get("WHATSAPP_API_VERSION", "v20.0")
CRON_SECRET = os.environ.get("CRON_SECRET")
UPLOAD_SECRET = os.environ.get("UPLOAD_SECRET")


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
    resultado_email = followup_semanal.enviar_emails_responsaveis(rascunhos)
    return {
        "status": "ok",
        "lote": lote,
        "clientes": len(rascunhos),
        "emails": resultado_email,
    }


@app.get("/painel/api/rascunhos-semanais")
def painel_rascunhos_semanais():
    return JSONResponse(db.listar_rascunhos_semanais_recentes())


# -----------------------------------------------------------------------
# Acompanhamento DIÁRIO por status do processo (ver followup_diario.py).
# Roda todo dia útil: manda e-mail interno por responsável (AGDO EMBARQUE /
# EM TRÂNSITO), pra Fernando (AGDO PRESENÇA DE CARGA / AGDO CARREGAMENTO /
# EM DESEMBARAÇO) e pra fiscal/financeiro (AGDO FECHAMENTO). Não manda nada
# pro cliente. Mesmo padrão de proteção do resumo semanal (X-Cron-Secret).
# -----------------------------------------------------------------------

@app.post("/cron/followup-diario")
def cron_followup_diario(x_cron_secret: str | None = Header(default=None)):
    if not CRON_SECRET:
        raise HTTPException(status_code=500, detail="CRON_SECRET não configurado no servidor")
    if x_cron_secret != CRON_SECRET:
        raise HTTPException(status_code=403, detail="Token inválido")

    resultado = followup_diario.executar_followup_diario()
    lote = db.registrar_execucao_diaria(resultado)
    return {"status": "ok", "lote": lote, **resultado}


@app.get("/painel/api/execucoes-diarias")
def painel_execucoes_diarias():
    return JSONResponse(db.listar_execucoes_diarias_recentes())


# -----------------------------------------------------------------------
# Upload manual da planilha do CONEXOS (ponte enquanto não existe API
# oficial — ver conexos_planilha.py). Uma página simples com senha, pra
# o Bernardo (ou quem for exportar) subir o Excel direto do celular ou
# computador, sem precisar mexer em terminal/curl.
# -----------------------------------------------------------------------

_PAGINA_UPLOAD = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Upload planilha CONEXOS — SeletoComex</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #f9f9f7; color: #0b0b0b;
         display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
  .card {{ background: #fff; border: 1px solid rgba(11,11,11,0.1); border-radius: 10px;
           padding: 24px 28px; max-width: 420px; width: 90%; }}
  h1 {{ font-size: 17px; margin: 0 0 6px; }}
  p {{ font-size: 13px; color: #52514e; margin: 0 0 18px; }}
  label {{ display: block; font-size: 13px; margin-bottom: 6px; }}
  input {{ width: 100%; padding: 8px; margin-bottom: 14px; border-radius: 6px;
           border: 1px solid rgba(11,11,11,0.15); box-sizing: border-box; }}
  button {{ width: 100%; padding: 10px; border-radius: 6px; border: none;
            background: #2a78d6; color: #fff; font-size: 14px; cursor: pointer; }}
  .msg {{ margin-top: 14px; font-size: 13px; }}
  .ok {{ color: #0ca30c; }}
  .erro {{ color: #d03b3b; }}
</style>
</head>
<body>
  <div class="card">
    <h1>Upload da planilha do CONEXOS</h1>
    <p>Exporte a "Gerência de Processos" (filiais 4 e 5, todos os status, processos em aberto) em Excel e envie aqui.</p>
    <form action="/admin/upload-conexos" method="post" enctype="multipart/form-data">
      <label for="senha">Senha</label>
      <input type="password" id="senha" name="senha" required>
      <label for="arquivo">Arquivo (.xlsx)</label>
      <input type="file" id="arquivo" name="arquivo" accept=".xlsx" required>
      <button type="submit">Enviar</button>
    </form>
    {mensagem}
  </div>
</body>
</html>
"""


@app.get("/admin/upload")
def pagina_upload():
    return HTMLResponse(_PAGINA_UPLOAD.format(mensagem=""))


@app.post("/admin/upload-conexos")
async def upload_conexos(senha: str = Form(...), arquivo: UploadFile = File(...)):
    if not UPLOAD_SECRET:
        return HTMLResponse(
            _PAGINA_UPLOAD.format(mensagem='<p class="msg erro">UPLOAD_SECRET não configurado no servidor.</p>'),
            status_code=500,
        )
    if senha != UPLOAD_SECRET:
        return HTMLResponse(
            _PAGINA_UPLOAD.format(mensagem='<p class="msg erro">Senha inválida.</p>'),
            status_code=403,
        )

    conteudo = await arquivo.read()
    with open(conexos_planilha.CONEXOS_EXPORT_PATH, "wb") as f:
        f.write(conteudo)

    try:
        total = len(conexos_planilha.listar_todos())
        mensagem = f'<p class="msg ok">✅ Recebido! {total} processo(s) carregado(s).</p>'
    except Exception as exc:
        mensagem = f'<p class="msg erro">Arquivo salvo, mas deu erro ao ler: {exc}</p>'

    return HTMLResponse(_PAGINA_UPLOAD.format(mensagem=mensagem))


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
