"""
conexos_connector.py
---------------------
Conector REAL para o sistema CONEXOS — hoje ainda é um "esqueleto"
(stub), porque ainda não temos a documentação/credenciais da API do
CONEXOS. A interface é IDÊNTICA à de erp_mock.py de propósito: o
bot_engine.py não precisa saber qual dos dois está sendo usado (veja
app.py, variável de ambiente ERP_BACKEND).

O QUE FALTA PARA ATIVAR ESTE ARQUIVO:
  1. Confirmar com o suporte/gerente de conta do CONEXOS se existe API
     REST, webhook, ou exportação automatizada para consulta de status
     de processos de importação (veja o rascunho de e-mail em
     "mensagem_para_conexos.md" neste projeto).
  2. Obter: URL base da API, forma de autenticação (API key, OAuth,
     usuário/senha de integração) e os endpoints de consulta.
  3. Preencher as variáveis de ambiente abaixo (.env):
        CONEXOS_API_BASE_URL
        CONEXOS_API_KEY   (ou o esquema de auth que o CONEXOS usar)
  4. Implementar as duas funções abaixo trocando o TODO pela chamada
     real (normalmente com a biblioteca "requests").
  5. Mudar no .env: ERP_BACKEND=conexos

Enquanto isso não estiver pronto, o bot continua funcionando com
erp_mock.py (ERP_BACKEND=mock), sem nenhum risco de quebrar o teste
atual.
"""

import os

CONEXOS_API_BASE_URL = os.environ.get("CONEXOS_API_BASE_URL", "")
CONEXOS_API_KEY = os.environ.get("CONEXOS_API_KEY", "")


def _cliente_http():
    """
    Monta um client HTTP autenticado para o CONEXOS.
    Ajustar o esquema de autenticação conforme a documentação real
    (Bearer token, Basic Auth, chave em header customizado, etc.)
    """
    import requests

    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {CONEXOS_API_KEY}",
        "Accept": "application/json",
    })
    return session


def buscar_processo_por_identificador(identificador: str):
    """
    Deve retornar um dict no MESMO formato usado em erp_mock.py (veja
    aquele arquivo para o schema completo e exemplos reais):
        {
            "processo": ..., "cliente": ..., "cliente_cnpj": ...,
            "telefone_cliente": ..., "responsavel_interno": ...,
            "ultima_atualizacao": ...,
            "info_processo": {fornecedor, origem, destino, modal,
                incoterm, tipo_operacao, data_abertura, etapa_atual},
            "info_carga": {container, bl, awb, booking, navio, voo,
                porto_aeroporto, eta, etd, ata, data_embarque,
                data_chegada, terminal, transportadora, agente_cargas},
            "info_aduaneira": {registro_di, registro_duimp, canal,
                desembaraco, conferencia, exigencia, pendencias[],
                liberacao, situacao_rfb, orgaos_anuentes[], licenciamento},
            "info_financeira": {pagamentos, custos, taxas, icms, afrmm,
                armazenagem, demurrage, pendencias_financeiras[]},
            "info_entrega": {liberacao_carga, nf, transportadora_entrega,
                agendamento, coleta, data_prevista_entrega,
                tipo_previsao_entrega ("confirmada"|"estimada"|None),
                data_efetiva_entrega},
            "historico": [{"data":..., "evento":...}, ...]
        }
    Campos sem informação disponível devem ser None (nunca inventados).
    ou None se não encontrar.

    Exemplo de implementação real (ajustar endpoint/campos ao que o
    CONEXOS realmente expuser):

        session = _cliente_http()
        resp = session.get(
            f"{CONEXOS_API_BASE_URL}/processos/{identificador}", timeout=10
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        dados = resp.json()
        return _mapear_processo_conexos(dados)
    """
    raise NotImplementedError(
        "conexos_connector ainda não está configurado. "
        "Peça a documentação/API ao CONEXOS e implemente esta função, "
        "ou use ERP_BACKEND=mock enquanto isso."
    )


def buscar_processos_por_telefone(telefone: str):
    """
    Mesma ideia da função acima, mas retornando uma LISTA de processos
    vinculados a um telefone/cliente. Se o CONEXOS não tiver telefone
    cadastrado por processo, uma alternativa é mapear telefone -> CNPJ
    do cliente (ex: numa tabela própria) e filtrar por CNPJ na consulta.
    """
    raise NotImplementedError(
        "conexos_connector ainda não está configurado. "
        "Peça a documentação/API ao CONEXOS e implemente esta função, "
        "ou use ERP_BACKEND=mock enquanto isso."
    )


def _mapear_processo_conexos(dados_brutos: dict) -> dict:
    """
    Função auxiliar (a preencher): traduz o formato de resposta do
    CONEXOS para o formato padrão usado pelo bot_engine.py.
    """
    raise NotImplementedError
