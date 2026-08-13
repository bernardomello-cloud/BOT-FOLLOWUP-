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
from datetime import datetime

import conexos_connector
import erp_mock

ERP_BACKEND = os.environ.get("ERP_BACKEND", "mock").strip().lower()
_erp = conexos_connector if ERP_BACKEND == "conexos" else erp_mock


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
    semana"). "Aberto" = ainda não tem entrega efetivada no sistema.
    """
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
        rascunhos.append({
            "cliente": cliente,
            "telefone_cliente": telefone,
            "responsavel_interno": processos[0].get("responsavel_interno"),
            "processos": [p["processo"] for p in processos],
            "texto": montar_rascunho_cliente(cliente, processos),
        })
    return rascunhos
