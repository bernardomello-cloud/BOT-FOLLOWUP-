"""
followup_diario.py
--------------------
Acompanhamento DIÁRIO por status do processo (complementar ao resumo
semanal de followup_semanal.py, que roda só na sexta).

Regra combinada com o Bernardo, por status do CONEXOS:

  - AGDO EMBARQUE / EM TRÂNSITO
      -> um e-mail por RESPONSÁVEL DO PROCESSO (mesmo mapeamento de
         followup_semanal.EMAIL_RESPONSAVEIS), listando só os processos
         dele nesses 2 status, com prontidão de carga (prevista/real),
         ETD, ETA, documentação (exigência/pendência aduaneira) e
         referência externa do cliente.

  - AGDO PRESENÇA DE CARGA / AGDO CARREGAMENTO / EM DESEMBARAÇO
      -> UM e-mail só, para Fernando (EMAIL_FERNANDO), com TODOS os
         processos das filiais 4 (Matriz Jaraguá do Sul) e 5 (Filial
         Rondônia) que estiverem nesses 3 status — não filtra por
         responsável, mas filtra por filial (ver EMPRESAS_FERNANDO).

  - AGDO FECHAMENTO
      -> UM e-mail só, para a dupla fiscal/financeiro (shayane e
         Joabe), com TODOS os processos nesse status — eles fecham a
         parte fiscal/financeira (prestação de contas ao cliente,
         valores a devolver ou a receber).

  - ENCERRADO -> não gera nenhum e-mail (processo já finalizado).

Assim como o envio semanal, isso é só aviso INTERNO por e-mail — a IA
não manda nada pro cliente. Reaproveita a mesma configuração SMTP de
followup_semanal.py (EMAIL_SMTP_HOST/PORT/USER/PASSWORD). Sem
EMAIL_SMTP_USER/EMAIL_SMTP_PASSWORD configurados, só loga o que
mandaria e não falha (mesmo padrão do resto do projeto).
"""

import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

import conexos_connector
import conexos_planilha
import erp_mock
from followup_semanal import (
    EMAIL_RESPONSAVEIS,
    EMAIL_SMTP_HOST,
    EMAIL_SMTP_PORT,
    EMAIL_SMTP_USER,
    EMAIL_SMTP_PASSWORD,
    _formata_data_br,
)

ERP_BACKEND = os.environ.get("ERP_BACKEND", "mock").strip().lower()
if ERP_BACKEND == "conexos":
    _erp = conexos_connector
elif ERP_BACKEND == "conexos_planilha":
    _erp = conexos_planilha
else:
    _erp = erp_mock

# E-mails fixos por grupo (não são "responsável do processo" — são papéis
# operacionais/fiscais que acompanham TODOS os processos daquele status).
EMAIL_FERNANDO = "Fernando@seletocomex.com.br"
EMAILS_FISCAL_FINANCEIRO = ["shayane@seletocomex.com.br", "Joabe@seletocomex.com.br"]

# Valores exatamente como aparecem no dropdown "Status do Processo" do CONEXOS.
STATUS_RESPONSAVEL = {"AGDO EMBARQUE", "EM TRÂNSITO"}
STATUS_FERNANDO = {"AGDO PRESENÇA DE CARGA", "AGDO CARREGAMENTO", "EM DESEMBARAÇO"}
STATUS_FISCAL_FINANCEIRO = {"AGDO FECHAMENTO"}

# Filiais que o Fernando acompanha (confirmado pelo Bernardo): "4" = Matriz
# Jaraguá do Sul (conta e ordem, encomenda, conta própria/assessoria);
# "5" = Filial Rondônia (só encomenda). Processos de outras filiais/empresas
# não entram no e-mail dele, mesmo que estejam num dos 3 status acima.
EMPRESAS_FERNANDO = {"4", "5"}
NOMES_EMPRESA = {"4": "Matriz (Jaraguá do Sul)", "5": "Filial Rondônia"}


def _por_status(processos: list, status_set: set) -> list:
    return [p for p in processos if p.get("status_processo") in status_set]


def _processos_fernando(processos: list) -> list:
    """Processos nos 3 status operacionais E nas filiais 4/5 (ver EMPRESAS_FERNANDO)."""
    candidatos = _por_status(processos, STATUS_FERNANDO)
    return [p for p in candidatos if p.get("codigo_empresa") in EMPRESAS_FERNANDO]


def _linha_embarque_transito(p: dict) -> str:
    ic = p["info_carga"]
    ia = p["info_aduaneira"]
    linhas = [f"📦 *{p['processo']}* — {p['cliente']} ({p.get('status_processo')})"]

    detalhes = []
    if ic.get("prontidao_carga_prevista"):
        detalhes.append(f"prontidão prevista {_formata_data_br(ic['prontidao_carga_prevista'])}")
    if ic.get("prontidao_carga_real"):
        detalhes.append(f"prontidão real {_formata_data_br(ic['prontidao_carga_real'])}")
    if ic.get("etd"):
        detalhes.append(f"ETD {_formata_data_br(ic['etd'])}")
    if ic.get("eta"):
        detalhes.append(f"ETA {_formata_data_br(ic['eta'])}")
    if detalhes:
        linhas.append("   " + " · ".join(detalhes))

    doc = []
    if ia.get("exigencia"):
        doc.append(f"exigência: {ia['exigencia']}")
    elif ia.get("pendencias"):
        doc.append("pendência: " + "; ".join(ia["pendencias"]))
    elif ia.get("situacao_rfb"):
        doc.append(f"situação: {ia['situacao_rfb']}")
    if p.get("referencia_cliente"):
        doc.append(f"ref. cliente {p['referencia_cliente']}")
    if doc:
        linhas.append("   " + " · ".join(doc))

    return "\n".join(linhas)


def _linha_operacional(p: dict) -> str:
    ic = p["info_carga"]
    linhas = [f"📦 *{p['processo']}* — {p['cliente']}"]
    detalhes = []
    filial = NOMES_EMPRESA.get(p.get("codigo_empresa"))
    if filial:
        detalhes.append(filial)
    if ic.get("data_chegada"):
        detalhes.append(f"chegou em {_formata_data_br(ic['data_chegada'])}")
    if ic.get("terminal"):
        detalhes.append(f"terminal {ic['terminal']}")
    if p["info_aduaneira"].get("situacao_rfb"):
        detalhes.append(p["info_aduaneira"]["situacao_rfb"])
    if p.get("referencia_cliente"):
        detalhes.append(f"ref. cliente {p['referencia_cliente']}")
    if detalhes:
        linhas.append("   " + " · ".join(detalhes))
    return "\n".join(linhas)


def _linha_fechamento(p: dict) -> str:
    ifin = p["info_financeira"]
    ie = p["info_entrega"]
    linhas = [f"📦 *{p['processo']}* — {p['cliente']}"]
    detalhes = []
    if ifin.get("pendencias_financeiras"):
        detalhes.append("pendência: " + "; ".join(ifin["pendencias_financeiras"]))
    if ifin.get("icms"):
        detalhes.append(f"ICMS: {ifin['icms']}")
    if ifin.get("demurrage"):
        detalhes.append(f"demurrage: {ifin['demurrage']}")
    if ie.get("data_prevista_entrega"):
        detalhes.append(f"entrega prevista {_formata_data_br(ie['data_prevista_entrega'])}")
    if p.get("referencia_cliente"):
        detalhes.append(f"ref. cliente {p['referencia_cliente']}")
    if detalhes:
        linhas.append("   " + " · ".join(detalhes))
    return "\n".join(linhas)


def _agrupar_por_responsavel(processos: list) -> dict:
    """{"email@...": [processo, ...]} só de quem tem e-mail mapeado."""
    por_email = {}
    for p in processos:
        email = EMAIL_RESPONSAVEIS.get(p.get("responsavel_interno"))
        if not email:
            continue
        por_email.setdefault(email, []).append(p)
    return por_email


def montar_email_responsavel_diario(processos: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    partes = [
        f"Acompanhamento diário — embarque e trânsito — {hoje}",
        "",
        "Seus processos em AGDO EMBARQUE ou EM TRÂNSITO hoje:",
        "",
    ]
    for p in processos:
        partes.append(_linha_embarque_transito(p))
        partes.append("")
    return "\n".join(partes).strip()


def montar_email_fernando(processos: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    partes = [
        f"Acompanhamento diário — operacional — {hoje}",
        "",
        f"{len(processos)} processo(s) das filiais Matriz e Rondônia nestes status hoje "
        "(AGDO PRESENÇA DE CARGA / AGDO CARREGAMENTO / EM DESEMBARAÇO):",
        "",
    ]
    por_status = {}
    for p in processos:
        por_status.setdefault(p.get("status_processo"), []).append(p)
    for status in ("AGDO PRESENÇA DE CARGA", "AGDO CARREGAMENTO", "EM DESEMBARAÇO"):
        lista = por_status.get(status)
        if not lista:
            continue
        partes.append(f"--- {status} ({len(lista)}) ---")
        for p in lista:
            partes.append(_linha_operacional(p))
            partes.append("")
    return "\n".join(partes).strip()


def montar_email_fiscal_financeiro(processos: list) -> str:
    hoje = datetime.now().strftime("%d/%m/%Y")
    partes = [
        f"Acompanhamento diário — fechamento fiscal/financeiro — {hoje}",
        "",
        f"{len(processos)} processo(s) em AGDO FECHAMENTO hoje — favor avaliar "
        "prestação de contas e valores a devolver/receber para cada cliente:",
        "",
    ]
    for p in processos:
        partes.append(_linha_fechamento(p))
        partes.append("")
    return "\n".join(partes).strip()


def _enviar(smtp: smtplib.SMTP, destino: str, assunto_base: str, corpo: str):
    hoje = datetime.now().strftime("%d/%m/%Y")
    msg = EmailMessage()
    msg["Subject"] = f"{assunto_base} — {hoje}"
    msg["From"] = EMAIL_SMTP_USER
    msg["To"] = destino
    msg.set_content(corpo)
    smtp.send_message(msg)
    print(f"[EMAIL DIÁRIO] enviado para {destino}")


def executar_followup_diario() -> dict:
    """
    Roda a rotina diária inteira (lê o ERP, agrupa por status, manda os
    e-mails). Retorna um resumo pronto pra logar/gravar no painel:

        {"enviados": int, "erro": str|None,
         "detalhe": {"responsaveis": {"email": qtd_processos, ...},
                      "fernando": qtd_processos,
                      "fiscal_financeiro": qtd_processos}}
    """
    resultado = {
        "enviados": 0,
        "erro": None,
        "detalhe": {"responsaveis": {}, "fernando": 0, "fiscal_financeiro": 0},
    }

    try:
        todos = _erp.listar_todos()
    except NotImplementedError:
        resultado["erro"] = "ERP backend não implementado (ver ERP_BACKEND no .env)"
        return resultado

    por_responsavel = _agrupar_por_responsavel(_por_status(todos, STATUS_RESPONSAVEL))
    processos_fernando = _processos_fernando(todos)
    processos_fiscal = _por_status(todos, STATUS_FISCAL_FINANCEIRO)

    resultado["detalhe"]["responsaveis"] = {e: len(p) for e, p in por_responsavel.items()}
    resultado["detalhe"]["fernando"] = len(processos_fernando)
    resultado["detalhe"]["fiscal_financeiro"] = len(processos_fiscal)

    if not EMAIL_SMTP_USER or not EMAIL_SMTP_PASSWORD:
        print("[EMAIL DIÁRIO] EMAIL_SMTP_USER/EMAIL_SMTP_PASSWORD não configurados — pulando envio.")
        return resultado

    try:
        with smtplib.SMTP(EMAIL_SMTP_HOST, EMAIL_SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(EMAIL_SMTP_USER, EMAIL_SMTP_PASSWORD)

            for email_destino, processos in por_responsavel.items():
                _enviar(
                    smtp, email_destino,
                    "Acompanhamento diário — embarque/trânsito",
                    montar_email_responsavel_diario(processos),
                )
                resultado["enviados"] += 1

            if processos_fernando:
                _enviar(
                    smtp, EMAIL_FERNANDO,
                    "Acompanhamento diário — operacional",
                    montar_email_fernando(processos_fernando),
                )
                resultado["enviados"] += 1

            if processos_fiscal:
                _enviar(
                    smtp, ", ".join(EMAILS_FISCAL_FINANCEIRO),
                    "Acompanhamento diário — fechamento fiscal/financeiro",
                    montar_email_fiscal_financeiro(processos_fiscal),
                )
                resultado["enviados"] += 1
    except Exception as exc:  # nunca deixa o envio diário derrubar o endpoint
        resultado["erro"] = str(exc)
        print(f"[EMAIL DIÁRIO ERRO] falha ao enviar acompanhamento diário: {exc}")

    return resultado
