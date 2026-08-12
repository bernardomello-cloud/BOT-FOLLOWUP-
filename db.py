"""
db.py
------
Persistência local (SQLite) para:
  1. Histórico de conversa por telefone — dá contexto à IA (seção 12 do
     prompt mestre: "e depois disso?" precisa saber a que "isso" se refere).
  2. Log de atendimentos — auditoria/LGPD (seção 21) e dados para o
     painel de controle (seção 22).

Em produção, para múltiplas instâncias do servidor rodando em paralelo,
troque SQLite por um banco compartilhado (Postgres, por exemplo) — a
interface das funções abaixo pode ficar igual.
"""

import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "atendimentos.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefone TEXT NOT NULL,
    papel TEXT NOT NULL,           -- 'cliente' ou 'bot'
    texto TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS atendimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telefone TEXT NOT NULL,
    cliente TEXT,
    processo TEXT,
    pergunta TEXT NOT NULL,
    dados_consultados TEXT,        -- JSON (snapshot do que foi consultado)
    resposta TEXT NOT NULL,
    acao TEXT NOT NULL,            -- rótulo interno (ex: status_por_identificador)
    confianca TEXT,                -- alta | media | baixa | null (modo fallback)
    encaminhado INTEGER NOT NULL DEFAULT 0,
    motivo_encaminhamento TEXT,
    tempo_resposta_ms INTEGER,
    criado_em TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_mensagens_telefone ON mensagens(telefone);
CREATE INDEX IF NOT EXISTS idx_atendimentos_telefone ON atendimentos(telefone);
CREATE INDEX IF NOT EXISTS idx_atendimentos_processo ON atendimentos(processo);
"""


@contextmanager
def _conexao():
    con = sqlite3.connect(DB_PATH)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def inicializar():
    with _conexao() as con:
        con.executescript(_SCHEMA)


def registrar_mensagem(telefone: str, papel: str, texto: str):
    with _conexao() as con:
        con.execute(
            "INSERT INTO mensagens (telefone, papel, texto, criado_em) VALUES (?, ?, ?, ?)",
            (telefone, papel, texto, datetime.now().isoformat(timespec="seconds")),
        )


def obter_historico(telefone: str, limite: int = 10):
    """Retorna as últimas `limite` mensagens (cliente + bot) em ordem cronológica."""
    with _conexao() as con:
        cur = con.execute(
            "SELECT papel, texto FROM mensagens WHERE telefone = ? ORDER BY id DESC LIMIT ?",
            (telefone, limite),
        )
        linhas = cur.fetchall()
    return [{"papel": papel, "texto": texto} for papel, texto in reversed(linhas)]


def registrar_atendimento(
    telefone, cliente, processo, pergunta, dados_consultados,
    resposta, acao, confianca=None, encaminhado=False,
    motivo_encaminhamento=None, tempo_resposta_ms=None,
):
    with _conexao() as con:
        con.execute(
            """INSERT INTO atendimentos
               (telefone, cliente, processo, pergunta, dados_consultados,
                resposta, acao, confianca, encaminhado, motivo_encaminhamento,
                tempo_resposta_ms, criado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                telefone, cliente, processo, pergunta,
                json.dumps(dados_consultados, ensure_ascii=False) if dados_consultados else None,
                resposta, acao, confianca, int(bool(encaminhado)),
                motivo_encaminhamento, tempo_resposta_ms,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )


# -----------------------------------------------------------------------
# Consultas para o painel de controle (seção 22 do prompt mestre)
# -----------------------------------------------------------------------

def stats_resumo():
    with _conexao() as con:
        total = con.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
        clientes = con.execute("SELECT COUNT(DISTINCT telefone) FROM atendimentos").fetchone()[0]
        processos = con.execute(
            "SELECT COUNT(DISTINCT processo) FROM atendimentos WHERE processo IS NOT NULL"
        ).fetchone()[0]
        encaminhados = con.execute(
            "SELECT COUNT(*) FROM atendimentos WHERE encaminhado = 1"
        ).fetchone()[0]
        tempo_medio = con.execute(
            "SELECT AVG(tempo_resposta_ms) FROM atendimentos WHERE tempo_resposta_ms IS NOT NULL"
        ).fetchone()[0]

    taxa_resolucao = 0.0
    if total > 0:
        taxa_resolucao = round(100.0 * (total - encaminhados) / total, 1)

    return {
        "total_atendimentos": total,
        "clientes_atendidos": clientes,
        "processos_consultados": processos,
        "encaminhados_para_humano": encaminhados,
        "taxa_resolucao_automatica": taxa_resolucao,
        "tempo_medio_resposta_ms": round(tempo_medio) if tempo_medio else None,
    }


def stats_processos_mais_consultados(limite=5):
    with _conexao() as con:
        cur = con.execute(
            """SELECT processo, COUNT(*) as qtd FROM atendimentos
               WHERE processo IS NOT NULL
               GROUP BY processo ORDER BY qtd DESC LIMIT ?""",
            (limite,),
        )
        return [{"processo": p, "quantidade": q} for p, q in cur.fetchall()]


def stats_motivos_encaminhamento():
    with _conexao() as con:
        cur = con.execute(
            """SELECT COALESCE(motivo_encaminhamento, 'outro'), COUNT(*) FROM atendimentos
               WHERE encaminhado = 1 GROUP BY 1 ORDER BY 2 DESC"""
        )
        return [{"motivo": m, "quantidade": q} for m, q in cur.fetchall()]


def stats_acoes():
    """Distribuição por tipo de ação (proxy para 'perguntas mais frequentes')."""
    with _conexao() as con:
        cur = con.execute(
            "SELECT acao, COUNT(*) FROM atendimentos GROUP BY acao ORDER BY 2 DESC"
        )
        return [{"acao": a, "quantidade": q} for a, q in cur.fetchall()]


def stats_atendimentos_por_dia(dias=14):
    with _conexao() as con:
        cur = con.execute(
            """SELECT substr(criado_em, 1, 10) as dia, COUNT(*) FROM atendimentos
               GROUP BY dia ORDER BY dia DESC LIMIT ?""",
            (dias,),
        )
        linhas = cur.fetchall()
    return [{"dia": d, "quantidade": q} for d, q in reversed(linhas)]


def listar_atendimentos_recentes(limite=50):
    with _conexao() as con:
        cur = con.execute(
            """SELECT telefone, cliente, processo, pergunta, resposta, acao,
                      confianca, encaminhado, motivo_encaminhamento, criado_em
               FROM atendimentos ORDER BY id DESC LIMIT ?""",
            (limite,),
        )
        colunas = [d[0] for d in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]


class Cronometro:
    """Utilitário simples para medir tempo de resposta em milissegundos."""

    def __enter__(self):
        self._inicio = time.time()
        return self

    def __exit__(self, *exc):
        self.duracao_ms = int((time.time() - self._inicio) * 1000)


inicializar()
