"""
followup_semanal.py
--------------------
Geração do resumo semanal de follow-up (toda sexta-feira).

Importante: isso NÃO manda mensagem direto pro cliente. A IA não
participa de grupos do WhatsApp (a API oficial do WhatsApp Business não
permite números conectados via API dentro de grupos) — em vez disso,
esse módulo gera um RASCUNHO pronto por cliente, com o status de todos
os processos em aberto, para a pessoa responsável revisar e colar no
grupo/conversa com o cliente.

Fluxo:
  Disparo semanal (ver app.py: POST /cron/followup-semanal, chamado por
  um agendador externo, ex: GitHub Actions) -> gerar_rascunhos() ->
  grava em db.py -> aparece no /painel para a pessoa responsável copiar.
"""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

import conexos_connector
import conexos_planilha
import erp_mock

ERP_BACKEND = os.environ.get("ERP_BACKEND", "mock").strip().lower()
if ERP_BACKEND == "conexos":
    _erp = conexos_connector
elif ERP_BACKEND == "conexos_planilha":
    _erp = conexos_planilha
else:
    _erp = erp_mock

# -----------------------------------------------------------------------
# Mapeamento responsável interno -> e-mail.
#
# Chaves confirmadas em 14/08/2026 a partir da planilha real exportada do
# CONEXOS (coluna "Responsável"): "BERNARDO", "ABNERH", "SANTOSTHIAGO".
# O erp_mock.py também usa esses mesmos nomes agora, pra testar com o
# mesmo mapeamento que vai valer com dados reais (ver conexos_planilha.py).
# -----------------------------------------------------------------------
EMAIL_RESPONSAVEIS = {
    "BERNARDO": "bernardo.mello@seletocomex.com.br",
    "ABNERH": "abnerh@seletocomex.com.br",
    "SANTOSTHIAGO": "santos.thiago@seletocomex.com.br",
}

EMAIL_SMTP_HOST = os.environ.get("EMAIL_SMTP_HOST", "smtp.office365.com")
EMAIL_SMTP_PORT = int(os.environ.get("EMAIL_SMTP_PORT", "587"))
EMAIL_SMTP_USER = os.environ.get("EMAIL_SMTP_USER")  # ex: followup@seletocomex.com.br
EMAIL_SMTP_PASSWORD = os.environ.get("EMAIL_SMTP_PASSWORD")


def _formata_data_br(data_iso):
    if not data_iso:
        return None
    try:
        return datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def _processo_esta_aberto(processo: dict) -> bool:
    """
    Regra combinada com o Bernardo: o resumo semanal cobre TODOS os
    processos em aberto, sempre (não filtra por "teve mudança na
    semana"). "Aberto" = status do processo diferente de ENCERRADO
    quando esse campo existe (planilha real do CONEXOS); senão, cai no
    critério antigo (ainda não tem entrega efetivada no sistema — usado
    pelo erp_mock.py de teste).
    """
    status = processo.get("status_processo")
    if status:
        return status != "ENCERRADO"
    return not processo["info_entrega"].get("data_efetiva_entrega")


def _resumo_processo_curto(processo: dict) -> str:
    """Uma versão compacta (2-3 linhas) do status de um processo, pensada
    para caber num resumo com vários processos — diferente do
    montar_resposta_fallback (mais detalhado, usado numa pergunta 1:1)."""
    ip = processo["info_processo"]
    ic = processo["info_carga"]
    ia = processo["info_aduaneira"]
    ie = processo["info_entrega"]

    linhas = [f"📦 *{processo['processo']}* — {ip['etapa_atual']}"]

    detalhes = []
    if ic.get("data_chegada"):
        detalhes.append(f"chegou em {_formata_data_br(ic['data_chegada'])}")
    elif ic.get("eta"):
        detalhes.append(f"ETA {_formata_data_br(ic['eta'])}")

    if ia.get("canal"):
        detalhes.append(f"Canal {ia['canal']}")
    if ia.get("exigencia"):
        detalhes.append(f"exigência: {ia['exigencia']}")
    if processo["info_financeira"].get("pendencias_financeiras"):
        detalhes.append(
            "pendência financeira: " + "; ".join(processo["info_financeira"]["pendencias_financeiras"])
        )

    if ie.get("data_prevista_entrega"):
        rotulo = "confirmada" if ie.get("tipo_previsao_entrega") == "confirmada" else "estimada"
        detalhes.append(f"entrega prevista {_formata_data_br(ie['data_prevista_entrega'])} ({rotulo})")

    if detalhes:
        linhas.append("   " + " · ".join(detalhes))

    return "\n".join(linhas)


def montar_rascunho_cliente(cliente: str, processos: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    linhas = [f"📋 *Resumo semanal — {cliente}*", "Segue o status atualizado dos processos em andamento:", ""]
    for p in processos:
        linhas.append(_resumo_processo_curto(p))
        linhas.append("")
    linhas.append(f"_Atualizado em {hoje} — SeletoComex_")
    return "\n".join(linhas).strip()


def gerar_rascunhos() -> list:
    """
    Agrupa todos os processos ABERTOS por cliente e monta um rascunho de
    mensagem por cliente. Retorna uma lista de dicts prontos para
    db.registrar_rascunhos_semanais():

        {"cliente": str, "telefone_cliente": str, "responsavel_interno": str,
         "processos": [numeros], "texto": str}
    """
    try:
        todos = _erp.listar_todos()
    except NotImplementedError:
        return []

    abertos = [p for p in todos if _processo_esta_aberto(p)]

    por_cliente = {}
    for p in abertos:
        chave = (p["cliente"], p["telefone_cliente"])
        por_cliente.setdefault(chave, []).append(p)

    rascunhos = []
    for (cliente, telefone), processos in por_cliente.items():
        responsavel = processos[0].get("responsavel_interno")
        rascunhos.append({
            "cliente": cliente,
            "telefone_cliente": telefone,
            "responsavel_interno": responsavel,
            "email_responsavel": EMAIL_RESPONSAVEIS.get(responsavel),
            "processos": [p["processo"] for p in processos],
            "texto": montar_rascunho_cliente(cliente, processos),
        })
    return rascunhos


# -----------------------------------------------------------------------
# Envio por e-mail (um e-mail por responsável, com os clientes dele).
#
# Não é a IA "mandando pro cliente" — é um aviso interno pra pessoa
# responsável, que revisa e decide o que enviar em cada grupo/conversa.
# Sem EMAIL_SMTP_USER/EMAIL_SMTP_PASSWORD configurados, essa função só
# registra no log e não falha o resto do processo (mesmo padrão do
# envio de WhatsApp: nunca deixa a geração dos rascunhos quebrar por
# causa do envio).
# -----------------------------------------------------------------------

def _agrupar_por_responsavel(rascunhos: list) -> dict:
    """{"email@...": [rascunho, rascunho, ...]}, ignora quem não tem e-mail mapeado."""
    por_email = {}
    for r in rascunhos:
        email = r.get("email_responsavel")
        if not email:
            continue
        por_email.setdefault(email, []).append(r)
    return por_email


def montar_email_responsavel(rascunhos_do_responsavel: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    partes = [
        f"Resumo semanal de follow-up — {hoje}",
        "",
        "Segue o status dos seus clientes com processos em aberto. Revise e "
        "envie a mensagem correspondente no grupo/conversa de cada cliente "
        "(o texto já vem pronto pra copiar também pelo painel).",
        "",
    ]
    for r in rascunhos_do_responsavel:
        partes.append("-" * 40)
        partes.append(r["texto"])
        partes.append("")
    partes.append("-" * 40)
    partes.append("Painel completo: (URL do painel configurada no Render)")
    return "\n".join(partes)


def enviar_emails_responsaveis(rascunhos: list) -> dict:
    """
    Manda um e-mail por responsável, agrupando os clientes dele. Retorna
    um resumo {"enviados": int, "pulados_sem_email": [clientes], "erro": str|None}.
    """
    resultado = {"enviados": 0, "pulados_sem_email": [], "erro": None}

    for r in rascunhos:
        if not r.get("email_responsavel"):
            resultado["pulados_sem_email"].append(r["cliente"])

    if not EMAIL_SMTP_USER or not EMAIL_SMTP_PASSWORD:
        print("[EMAIL] EMAIL_SMTP_USER/EMAIL_SMTP_PASSWORD não configurados — pulando envio (rascunhos só ficam no painel).")
        return resultado

    por_email = _agrupar_por_responsavel(rascunhos)
    if not por_email:
        return resultado

    try:
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)
            for email_destino, rascunhos_pessoa in por_email.items():
                msg = EmailMessage()
                msg["Subject"] = f"Resumo semanal de follow-up — {datetime.now().strftime('%d/%m/%Y')}"
                msg["From"] = EMAIL_SMTP_USER
                msg["To"] = email_destino
                msg.set_content(montar_email_responsavel(rascunhos_pessoa))
                smtp.send_message(msg)
                resultado["enviados"] += 1
                print(f"[EMAIL] Resumo semanal enviado para {email_destino} ({len(rascunhos_pessoa)} cliente(s))")
    except Exception as exc:  # nunca deixa o envio de e-mail quebrar o resto do fluxo
        resultado["erro"] = str(exc)
        print(f"[EMAIL ERRO] falha ao enviar resumo semanal: {exc}")

    return resultado
