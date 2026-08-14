"""
erp_mock.py
------------
Simula a camada de dados do CONEXOS (sistema de comex da SeletoComex).

Schema alinhado ao "PROMPT MESTRE" fornecido pelo cliente: cada processo
tem informações de processo, carga, aduaneira, financeira e de entrega,
além de histórico de eventos. Campos sem informação disponível ficam
como None — o bot_engine/IA NUNCA deve inventar valor para eles.

Em produção, substituir buscar_processo_por_identificador() e
buscar_processos_por_telefone() por chamadas reais ao CONEXOS
(ver conexos_connector.py).

IMPORTANTE (segurança/LGPD): cada processo tem "telefone_cliente" e
"cliente_cnpj" — usados pelo bot_engine para confirmar que quem está
perguntando tem vínculo com aquele processo antes de entregar qualquer
dado (ver bot_engine.identificar()).

"codigo_empresa": código da filial/empresa dona do processo no CONEXOS
(confirmado pelo Bernardo: "4" = Matriz Jaraguá do Sul — conta e ordem,
encomenda e conta própria/assessoria; "5" = Filial Rondônia — só
encomenda). Usado por followup_diario.py para filtrar o e-mail
operacional do Fernando, que só cobre as filiais 4 e 5. Outros códigos
abaixo (ex: "9") são fictícios, só para testar que o filtro exclui
corretamente processos de fora dessas duas filiais.
"""

_PROCESSOS = [
    # --- Nortesul: processo citado no exemplo do prompt mestre (seção 23) ---
    {
        "processo": "RO-OE-0009/26",
        "cliente": "Distribuidora Nortesul Ltda",
        "cliente_cnpj": "12.345.678/0001-90",
        "telefone_cliente": "5511987654321",
        "responsavel_interno": "BERNARDO",
        "status_processo": "EM DESEMBARAÇO",
        "codigo_empresa": "5",
        "referencia_cliente": "PO-88231",
        "ultima_atualizacao": "2026-08-09",
        "info_processo": {
            "fornecedor": "Guangzhou Auto Parts Co.",
            "origem": "Guangzhou, China",
            "destino": "São Paulo, Brasil",
            "modal": "Marítimo",
            "incoterm": "FOB",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-07-15",
            "etapa_atual": "Aguardando conclusão do desembaraço aduaneiro",
        },
        "info_carga": {
            "container": "MSCU1234567",
            "bl": "MSCUBS0456781",
            "awb": None,
            "booking": "BKG998877",
            "navio": "MSC Anna",
            "voo": None,
            "porto_aeroporto": "Porto de Santos",
            "eta": None,
            "etd": "2026-07-20",
            "prontidao_carga_prevista": "2026-07-15",
            "prontidao_carga_real": "2026-07-18",
            "ata": "2026-08-07",
            "data_embarque": "2026-07-20",
            "data_chegada": "2026-08-07",
            "terminal": "Multilog",
            "transportadora": "TransBrasil Log",
            "agente_cargas": "Global Trade Despachos",
        },
        "info_aduaneira": {
            "registro_di": "26/1234567-8",
            "registro_duimp": None,
            "canal": "Verde",
            "desembaraco": "Em andamento",
            "conferencia": None,
            "exigencia": None,
            "pendencias": [],
            "liberacao": None,
            "situacao_rfb": "Sem pendências identificadas",
            "orgaos_anuentes": [],
            "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia",
            "custos": None,
            "taxas": None,
            "icms": None,
            "afrmm": "Pago",
            "armazenagem": "Em andamento (dentro do prazo)",
            "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": None,
            "nf": "Não emitida",
            "transportadora_entrega": None,
            "agendamento": None,
            "coleta": None,
            "data_prevista_entrega": "2026-08-29",
            "tipo_previsao_entrega": "estimada",
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-07-15", "evento": "Abertura do processo"},
            {"data": "2026-07-20", "evento": "Embarque confirmado no porto de origem"},
            {"data": "2026-08-07", "evento": "Chegada da carga no Porto de Santos"},
            {"data": "2026-08-08", "evento": "Registro da DI — parametrização em Canal Verde"},
            {"data": "2026-08-09", "evento": "Desembaraço em andamento, sem pendências"},
        ],
    },
    # --- Nortesul: segundo processo (para testar "múltiplos processos") ---
    {
        "processo": "RO-OE-0015/26",
        "cliente": "Distribuidora Nortesul Ltda",
        "cliente_cnpj": "12.345.678/0001-90",
        "telefone_cliente": "5511987654321",
        "responsavel_interno": "BERNARDO",
        "status_processo": "EM TRÂNSITO",
        "codigo_empresa": "5",
        "referencia_cliente": "PO-88250",
        "ultima_atualizacao": "2026-08-10",
        "info_processo": {
            "fornecedor": "Ningbo Electronics Ltd.",
            "origem": "Ningbo, China",
            "destino": "São Paulo, Brasil",
            "modal": "Marítimo",
            "incoterm": "CIF",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-07-28",
            "etapa_atual": "Em trânsito internacional",
        },
        "info_carga": {
            "container": "TCLU9988771",
            "bl": "TCLUBS0998812",
            "awb": None,
            "booking": "BKG112233",
            "navio": "COSCO Pacific",
            "voo": None,
            "porto_aeroporto": "Porto de Paranaguá",
            "eta": "2026-08-25",
            "etd": "2026-08-03",
            "prontidao_carga_prevista": "2026-07-30",
            "prontidao_carga_real": "2026-08-02",
            "ata": None,
            "data_embarque": "2026-08-03",
            "data_chegada": None,
            "terminal": None,
            "transportadora": None,
            "agente_cargas": "Global Trade Despachos",
        },
        "info_aduaneira": {
            "registro_di": None, "registro_duimp": None, "canal": None,
            "desembaraco": None, "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": None, "situacao_rfb": None,
            "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia", "custos": None, "taxas": None, "icms": None,
            "afrmm": None, "armazenagem": None, "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": None, "nf": None, "transportadora_entrega": None,
            "agendamento": None, "coleta": None,
            "data_prevista_entrega": "2026-09-05", "tipo_previsao_entrega": "estimada",
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-07-28", "evento": "Abertura do processo"},
            {"data": "2026-08-03", "evento": "Embarque confirmado no porto de origem"},
            {"data": "2026-08-10", "evento": "Em trânsito marítimo — sem intercorrências"},
        ],
    },
    # --- Vale Verde: processo com pendência documental (canal amarelo) ---
    {
        "processo": "RO-IE-0044/26",
        "cliente": "Comercial Vale Verde S.A.",
        "cliente_cnpj": "98.765.432/0001-10",
        "telefone_cliente": "5521998877665",
        "responsavel_interno": "ABNERH",
        "status_processo": "EM DESEMBARAÇO",
        "codigo_empresa": "9",
        "referencia_cliente": "PO-40021",
        "ultima_atualizacao": "2026-08-10",
        "info_processo": {
            "fornecedor": "Hamburg Machinery GmbH",
            "origem": "Hamburgo, Alemanha",
            "destino": "Itajaí, Brasil",
            "modal": "Marítimo",
            "incoterm": "FOB",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-07-10",
            "etapa_atual": "Aguardando documentação complementar (exigência)",
        },
        "info_carga": {
            "container": "HLXU4455667",
            "bl": "HLXUBS0223344",
            "awb": None,
            "booking": "BKG554433",
            "navio": "Hapag Lloyd Bremen",
            "voo": None,
            "porto_aeroporto": "Porto de Itajaí",
            "eta": None,
            "etd": "2026-07-12",
            "prontidao_carga_prevista": "2026-07-08",
            "prontidao_carga_real": "2026-07-10",
            "ata": "2026-07-30",
            "data_embarque": "2026-07-12",
            "data_chegada": "2026-07-30",
            "terminal": "Braskarne",
            "transportadora": None,
            "agente_cargas": "Comex Fácil Assessoria",
        },
        "info_aduaneira": {
            "registro_di": "26/9876543-2",
            "registro_duimp": None,
            "canal": "Amarelo",
            "desembaraco": "Suspenso — aguardando exigência",
            "conferencia": "Documental",
            "exigencia": "Envio da fatura comercial retificada (invoice) e certificado de origem",
            "pendencias": ["Documentação complementar (invoice retificada + certificado de origem)"],
            "liberacao": None,
            "situacao_rfb": "Exigência aberta em 05/08/2026",
            "orgaos_anuentes": [],
            "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia", "custos": None, "taxas": None, "icms": None,
            "afrmm": "Pago", "armazenagem": "Acumulando — acima de 10 dias no terminal",
            "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": None, "nf": None, "transportadora_entrega": None,
            "agendamento": None, "coleta": None,
            "data_prevista_entrega": None, "tipo_previsao_entrega": None,
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-07-10", "evento": "Abertura do processo"},
            {"data": "2026-07-30", "evento": "Chegada no Porto de Itajaí"},
            {"data": "2026-08-01", "evento": "Registro da DI — parametrização em Canal Amarelo"},
            {"data": "2026-08-05", "evento": "Exigência aberta: documentação complementar solicitada"},
        ],
    },
    # --- Vale Verde: processo liberado, aguardando coleta (sem data confirmada) ---
    {
        "processo": "RO-IE-0039/26",
        "cliente": "Comercial Vale Verde S.A.",
        "cliente_cnpj": "98.765.432/0001-10",
        "telefone_cliente": "5521998877665",
        "responsavel_interno": "ABNERH",
        "status_processo": "AGDO CARREGAMENTO",
        "codigo_empresa": "5",
        "referencia_cliente": "PO-40077",
        "ultima_atualizacao": "2026-08-08",
        "info_processo": {
            "fornecedor": "Rotterdam Chemicals BV",
            "origem": "Rotterdam, Holanda",
            "destino": "Santos, Brasil",
            "modal": "Marítimo",
            "incoterm": "CIF",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-06-25",
            "etapa_atual": "Liberado — aguardando agendamento de coleta",
        },
        "info_carga": {
            "container": "OOLU7766554",
            "bl": "OOLUBS0778899",
            "awb": None,
            "booking": "BKG334455",
            "navio": "OOCL Europe",
            "voo": None,
            "porto_aeroporto": "Porto de Santos",
            "eta": None,
            "etd": "2026-07-05",
            "prontidao_carga_prevista": "2026-06-30",
            "prontidao_carga_real": "2026-07-02",
            "ata": "2026-07-30",
            "data_embarque": "2026-07-05",
            "data_chegada": "2026-07-30",
            "terminal": "BTP",
            "transportadora": None,
            "agente_cargas": "Comex Fácil Assessoria",
        },
        "info_aduaneira": {
            "registro_di": "26/5566778-3", "registro_duimp": None, "canal": "Verde",
            "desembaraco": "Concluído", "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": "2026-08-08",
            "situacao_rfb": "Sem pendências", "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia", "custos": None, "taxas": None, "icms": None,
            "afrmm": "Pago", "armazenagem": "Em andamento", "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": "Concluída em 08/08/2026",
            "nf": "Emitida",
            "transportadora_entrega": "A definir",
            "agendamento": None,
            "coleta": None,
            "data_prevista_entrega": None,
            "tipo_previsao_entrega": None,
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-06-25", "evento": "Abertura do processo"},
            {"data": "2026-07-30", "evento": "Chegada no Porto de Santos"},
            {"data": "2026-08-03", "evento": "Canal Verde — sem necessidade de conferência"},
            {"data": "2026-08-08", "evento": "Carga liberada pela Receita Federal — aguardando agendamento de coleta"},
        ],
    },
    # --- Bahia Têxtil: processo com pendência financeira ---
    {
        "processo": "SA-IE-0027/26",
        "cliente": "Indústria Bahia Têxtil",
        "cliente_cnpj": "45.678.912/0001-33",
        "telefone_cliente": "5571991234567",
        "responsavel_interno": "SANTOSTHIAGO",
        "status_processo": "AGDO FECHAMENTO",
        "codigo_empresa": "5",
        "referencia_cliente": "PO-77310",
        "ultima_atualizacao": "2026-08-10",
        "info_processo": {
            "fornecedor": "Vietnam Textile Group",
            "origem": "Ho Chi Minh, Vietnã",
            "destino": "Salvador, Brasil",
            "modal": "Marítimo",
            "incoterm": "FOB",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-06-10",
            "etapa_atual": "Aguardando regularização financeira para liberação",
        },
        "info_carga": {
            "container": "CMAU3322110",
            "bl": "CMAUBS0554433",
            "awb": None,
            "booking": "BKG667788",
            "navio": "CMA CGM Mekong",
            "voo": None,
            "porto_aeroporto": "Porto de Salvador",
            "eta": None,
            "etd": "2026-06-20",
            "prontidao_carga_prevista": "2026-06-15",
            "prontidao_carga_real": "2026-06-17",
            "ata": "2026-07-18",
            "data_embarque": "2026-06-20",
            "data_chegada": "2026-07-18",
            "terminal": "Tecon Salvador",
            "transportadora": None,
            "agente_cargas": "Global Trade Despachos",
        },
        "info_aduaneira": {
            "registro_di": "26/1122334-5", "registro_duimp": None, "canal": "Verde",
            "desembaraco": "Concluído", "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": "2026-07-22",
            "situacao_rfb": "Sem pendências", "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Pendente",
            "custos": "Frete internacional + taxas portuárias",
            "taxas": "THC, capatazia",
            "icms": "Pendente de recolhimento",
            "afrmm": "Pago",
            "armazenagem": "Acumulando — acima do prazo, gerando custo extra",
            "demurrage": "Em contagem desde 30/07/2026",
            "pendencias_financeiras": ["Recolhimento do ICMS de importação pendente por parte do cliente"],
        },
        "info_entrega": {
            "liberacao_carga": "Bloqueada até regularização financeira",
            "nf": "Não emitida",
            "transportadora_entrega": None,
            "agendamento": None,
            "coleta": None,
            "data_prevista_entrega": None,
            "tipo_previsao_entrega": None,
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-06-10", "evento": "Abertura do processo"},
            {"data": "2026-07-18", "evento": "Chegada no Porto de Salvador"},
            {"data": "2026-07-22", "evento": "Desembaraço concluído — Canal Verde"},
            {"data": "2026-07-30", "evento": "Início da contagem de demurrage por atraso na retirada"},
            {"data": "2026-08-10", "evento": "Aguardando recolhimento do ICMS para liberação da carga do terminal"},
        ],
    },
    # --- Bahia Têxtil: processo já entregue (histórico encerrado) ---
    {
        "processo": "SA-IE-0011/26",
        "cliente": "Indústria Bahia Têxtil",
        "cliente_cnpj": "45.678.912/0001-33",
        "telefone_cliente": "5571991234567",
        "responsavel_interno": "SANTOSTHIAGO",
        "status_processo": "ENCERRADO",
        "codigo_empresa": "4",
        "referencia_cliente": "PO-77199",
        "ultima_atualizacao": "2026-07-25",
        "info_processo": {
            "fornecedor": "Shanghai Yarn Co.",
            "origem": "Shanghai, China",
            "destino": "Salvador, Brasil",
            "modal": "Marítimo",
            "incoterm": "FOB",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-05-20",
            "etapa_atual": "Encerrado — entrega concluída",
        },
        "info_carga": {
            "container": "CMAU1100220",
            "bl": "CMAUBS0110022",
            "awb": None,
            "booking": "BKG001122",
            "navio": "CMA CGM Shanghai",
            "voo": None,
            "porto_aeroporto": "Porto de Salvador",
            "eta": None,
            "etd": "2026-06-01",
            "prontidao_carga_prevista": "2026-05-27",
            "prontidao_carga_real": "2026-05-29",
            "ata": "2026-06-28",
            "data_embarque": "2026-06-01",
            "data_chegada": "2026-06-28",
            "terminal": "Tecon Salvador",
            "transportadora": "Rota Log Transportes",
            "agente_cargas": "Global Trade Despachos",
        },
        "info_aduaneira": {
            "registro_di": "26/0011223-4", "registro_duimp": None, "canal": "Verde",
            "desembaraco": "Concluído", "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": "2026-07-02",
            "situacao_rfb": "Sem pendências", "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Concluído", "custos": "Liquidados", "taxas": "Pagas",
            "icms": "Recolhido", "afrmm": "Pago", "armazenagem": "Encerrada",
            "demurrage": None, "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": "Concluída em 02/07/2026",
            "nf": "Emitida",
            "transportadora_entrega": "Rota Log Transportes",
            "agendamento": "Concluído",
            "coleta": "Realizada em 05/07/2026",
            "data_prevista_entrega": "2026-07-10",
            "tipo_previsao_entrega": "confirmada",
            "data_efetiva_entrega": "2026-07-09",
        },
        "historico": [
            {"data": "2026-05-20", "evento": "Abertura do processo"},
            {"data": "2026-06-28", "evento": "Chegada no Porto de Salvador"},
            {"data": "2026-07-02", "evento": "Desembaraço concluído — Canal Verde"},
            {"data": "2026-07-05", "evento": "Coleta realizada no terminal"},
            {"data": "2026-07-09", "evento": "Entrega concluída no destino final"},
        ],
    },
    # --- Metalúrgica Sul Peças: processo ainda não embarcado (AGDO EMBARQUE) ---
    {
        "processo": "SC-OE-0032/26",
        "cliente": "Metalúrgica Sul Peças Ltda",
        "cliente_cnpj": "23.456.789/0001-44",
        "telefone_cliente": "5547988112233",
        "responsavel_interno": "BERNARDO",
        "status_processo": "AGDO EMBARQUE",
        "codigo_empresa": "4",
        "referencia_cliente": "PO-91004",
        "ultima_atualizacao": "2026-08-11",
        "info_processo": {
            "fornecedor": "Shenzhen Metal Components Co.",
            "origem": "Shenzhen, China",
            "destino": "Itajaí, Brasil",
            "modal": "Marítimo",
            "incoterm": "FOB",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-08-01",
            "etapa_atual": "Aguardando embarque — carga em preparação no porto de origem",
        },
        "info_carga": {
            "container": "TEMU2211445",
            "bl": None,
            "awb": None,
            "booking": "BKG778899",
            "navio": "Maersk Shenzhen",
            "voo": None,
            "porto_aeroporto": "Porto de Itajaí",
            "eta": "2026-09-10",
            "etd": "2026-08-20",
            "prontidao_carga_prevista": "2026-08-15",
            "prontidao_carga_real": None,
            "ata": None,
            "data_embarque": None,
            "data_chegada": None,
            "terminal": None,
            "transportadora": None,
            "agente_cargas": "Global Trade Despachos",
        },
        "info_aduaneira": {
            "registro_di": None, "registro_duimp": None, "canal": None,
            "desembaraco": None, "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": None, "situacao_rfb": None,
            "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia", "custos": None, "taxas": None, "icms": None,
            "afrmm": None, "armazenagem": None, "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": None, "nf": None, "transportadora_entrega": None,
            "agendamento": None, "coleta": None,
            "data_prevista_entrega": None, "tipo_previsao_entrega": None,
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-08-01", "evento": "Abertura do processo"},
            {"data": "2026-08-11", "evento": "Booking confirmado — aguardando prontidão da carga para embarque"},
        ],
    },
    # --- Hospitalar MedSul: carga chegou, aguardando presença de carga (pré-DI) ---
    {
        "processo": "SC-IE-0018/26",
        "cliente": "Hospitalar MedSul Equipamentos Ltda",
        "cliente_cnpj": "34.567.890/0001-21",
        "telefone_cliente": "5547999223344",
        "responsavel_interno": "SANTOSTHIAGO",
        "status_processo": "AGDO PRESENÇA DE CARGA",
        "codigo_empresa": "4",
        "referencia_cliente": "PO-65512",
        "ultima_atualizacao": "2026-08-11",
        "info_processo": {
            "fornecedor": "MedTech Equipment GmbH",
            "origem": "Frankfurt, Alemanha",
            "destino": "Navegantes, Brasil",
            "modal": "Aéreo",
            "incoterm": "CIF",
            "tipo_operacao": "Importação direta",
            "data_abertura": "2026-07-25",
            "etapa_atual": "Carga chegada — aguardando registro de presença de carga no Siscomex",
        },
        "info_carga": {
            "container": None,
            "bl": None,
            "awb": "020-88317744",
            "booking": None,
            "navio": None,
            "voo": "LH509",
            "porto_aeroporto": "Aeroporto de Navegantes",
            "eta": None,
            "etd": "2026-08-09",
            "prontidao_carga_prevista": "2026-08-08",
            "prontidao_carga_real": "2026-08-08",
            "ata": "2026-08-10",
            "data_embarque": "2026-08-09",
            "data_chegada": "2026-08-10",
            "terminal": "TECA Navegantes",
            "transportadora": None,
            "agente_cargas": "Comex Fácil Assessoria",
        },
        "info_aduaneira": {
            "registro_di": None, "registro_duimp": None, "canal": None,
            "desembaraco": None, "conferencia": None, "exigencia": None,
            "pendencias": [], "liberacao": None,
            "situacao_rfb": "Aguardando registro de presença de carga",
            "orgaos_anuentes": [], "licenciamento": None,
        },
        "info_financeira": {
            "pagamentos": "Em dia", "custos": None, "taxas": None, "icms": None,
            "afrmm": None, "armazenagem": "Em andamento (dentro do prazo)", "demurrage": None,
            "pendencias_financeiras": [],
        },
        "info_entrega": {
            "liberacao_carga": None, "nf": None, "transportadora_entrega": None,
            "agendamento": None, "coleta": None,
            "data_prevista_entrega": None, "tipo_previsao_entrega": None,
            "data_efetiva_entrega": None,
        },
        "historico": [
            {"data": "2026-07-25", "evento": "Abertura do processo"},
            {"data": "2026-08-10", "evento": "Chegada da carga no Aeroporto de Navegantes"},
            {"data": "2026-08-11", "evento": "Aguardando registro de presença de carga para iniciar o desembaraço"},
        ],
    },
]


def _normaliza(texto: str) -> str:
    return (texto or "").strip().upper().replace(" ", "")


def _normaliza_telefone(telefone: str) -> str:
    return "".join(ch for ch in (telefone or "") if ch.isdigit())


def buscar_processo_por_identificador(identificador: str):
    """Busca por número de processo, container ou BL (case/espaço-insensível)."""
    ident = _normaliza(identificador)
    for p in _PROCESSOS:
        if _normaliza(p["processo"]) == ident:
            return p
        if _normaliza(p["info_carga"]["container"]) == ident:
            return p
        if _normaliza(p["info_carga"]["bl"] or "") == ident:
            return p
    return None


def buscar_processos_por_telefone(telefone: str):
    """Retorna todos os processos vinculados a um telefone de cliente."""
    tel = _normaliza_telefone(telefone)
    return [p for p in _PROCESSOS if p["telefone_cliente"] == tel]


def listar_todos():
    """Utilitário para debug/testes."""
    return _PROCESSOS
