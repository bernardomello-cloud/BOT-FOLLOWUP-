# IA de Followup de Importações — SeletoComex (Protótipo v2)

Protótipo funcional de uma IA que responde clientes no WhatsApp sobre o
status/andamento de processos de importação, implementando o fluxo e as
regras do **prompt mestre** definido para o projeto: identificação
segura do cliente, consulta ao sistema (CONEXOS/mock), interpretação
humanizada dos dados por IA (Claude), regras de "nunca inventar",
escalonamento para humano em situações sensíveis, registro de auditoria
e um painel de controle.

Este pacote roda localmente com **dados fictícios** (simulando o
CONEXOS), no mesmo formato que os dados reais terão. Não é necessário
nenhuma credencial de WhatsApp para testar — há uma tela de chat de
demonstração incluída.

## O que já está pronto

- **Identificação segura do cliente/processo** (`bot_engine.identificar`)
  — determinística, nunca delegada à IA: confirma que o telefone de
  quem está perguntando é o mesmo cadastrado no processo antes de
  entregar qualquer dado (ver seção "Segurança e LGPD").
- **Escalonamento por palavra-chave** (`escalonamento.py`) — detecta
  reclamação grave, questão jurídica, cobrança contestada, pedido
  explícito de humano, entre outros, e desvia para atendimento humano
  antes mesmo de chamar a IA.
- **IA generativa (Claude) com regras do prompt mestre**
  (`system_prompt.py` + `ia_followup.py`) — interpreta os dados do
  processo e do histórico da conversa e gera uma resposta humanizada,
  seguindo as regras de nunca inventar, diferenciar data
  confirmada/estimada/indisponível, e se autoavaliar com um nível de
  confiança (alta/média/baixa), escalando para humano quando a
  confiança é baixa ou a situação exige decisão humana.
- **Modo fallback sem IA** — se `ANTHROPIC_API_KEY` não estiver
  configurada (ou a chamada falhar), o bot responde com um template
  determinístico mais simples, mas nunca deixa o cliente sem resposta.
- **Base de dados simulada** (`erp_mock.py`) com o schema completo
  pedido (informações de processo, carga, aduaneiras, financeiras e de
  entrega), cobrindo cenários variados: em trânsito, canal verde sem
  pendência, canal amarelo com exigência documental, liberado aguardando
  coleta, pendência financeira, e processo já entregue.
- **Esqueleto do conector real com o CONEXOS** (`conexos_connector.py`)
  — mesma interface do mock, pronto para receber a implementação real
  quando a documentação/API chegar.
- **Persistência e auditoria** (`db.py`, SQLite) — histórico de
  conversa por telefone (dá contexto à IA) + log completo de todos os
  atendimentos (pergunta, dados consultados, resposta, confiança,
  encaminhamento, tempo de resposta).
- **Painel de controle** em `/painel` — atendimentos totais, taxa de
  resolução automática, processos mais consultados, motivos de
  encaminhamento, atendimentos por dia e lista de atendimentos recentes.
- **Servidor web** (`app.py`) com `/webhook` no formato da Meta Cloud
  API, `/api/chat` para testes, e a tela de chat de demonstração em `/`.

## Como testar agora (sem WhatsApp real)

```bash
pip install -r requirements.txt
uvicorn app:app --reload --port 8000
```

Abra `http://localhost:8000` para a tela de chat, e
`http://localhost:8000/painel` para o painel de controle.

Sugestões de mensagens para testar (troque o "cliente simulado" no
seletor do topo da tela de chat):

- `Boa tarde, como está minha carga RO-OE-0009/26?` — exemplo do prompt
  mestre: carga chegada, Canal Verde, aguardando desembaraço.
- `tem novidade da minha importação?` (cliente Nortesul) — tem 2
  processos cadastrados, o bot pergunta qual.
- `por que minha carga RO-IE-0044/26 não foi liberada?` (cliente Vale
  Verde) — processo com exigência documental (Canal Amarelo).
- `quando vou conseguir retirar a carga RO-IE-0039/26?` — liberado, mas
  sem data de entrega confirmada ainda.
- `quero falar com um advogado, isso é um absurdo` — dispara
  escalonamento imediato para humano.
- Trocar para o telefone "número desconhecido" e perguntar por
  `RO-OE-0009/26` — mostra a verificação de identidade (o processo
  existe, mas não pertence a esse telefone).

**Nota sobre a IA:** sem uma `ANTHROPIC_API_KEY` configurada no `.env`,
o bot funciona no modo fallback (respostas determinísticas, testadas e
funcionando). Com a chave configurada, as respostas passam a ser
geradas pelo Claude seguindo o prompt mestre (interpretação humanizada,
contexto de conversa, autoavaliação de confiança). Testei a integração
com a API simulada (mock) para garantir que a chamada, o formato dos
dados enviados e o parsing da resposta estão corretos — o teste com a
API real do Claude ainda precisa ser feito por você (ou por mim, se me
der acesso a uma chave) antes de ir para produção.

## Estrutura do projeto

```
followup-bot/
├── app.py                      servidor FastAPI (webhook, chat, painel)
├── bot_engine.py                 orquestração: identificação → escalonamento → IA/fallback → registro
├── escalonamento.py               regras determinísticas de encaminhamento para humano
├── system_prompt.py                system prompt da IA (adaptado do prompt mestre) + schema da resposta
├── ia_followup.py                  chamada ao Claude (tool use) para gerar a resposta rica
├── db.py                           persistência SQLite (histórico de conversa + auditoria + painel)
├── erp_mock.py                     dados fictícios, usados quando ERP_BACKEND=mock
├── conexos_connector.py            esqueleto do conector real com o CONEXOS (ERP_BACKEND=conexos)
├── mensagem_para_conexos.md        texto pronto para pedir acesso/API ao suporte do CONEXOS
├── static/index.html               tela de chat para testes
├── static/painel.html              painel de controle (métricas de atendimento)
├── requirements.txt
├── Procfile                        usado pelo Railway/Render para iniciar o servidor
└── .env.example                    variáveis de ambiente necessárias
```

## Como o fluxo funciona (mapeado ao prompt mestre)

```
Cliente → WhatsApp → escalonamento.detectar() [palavra-chave grave?]
                              │ não
                              ▼
                    bot_engine.identificar() [telefone/identificador → processo, com checagem de propriedade]
                              │
                              ▼
                 ia_followup.gerar_resposta() [Claude: interpreta dados + histórico, nunca inventa]
                              │  (sem API key / erro → fallback determinístico)
                              ▼
                    db.registrar_atendimento() [auditoria + alimenta o painel]
                              │
                              ▼
                         WhatsApp → Cliente
```

## Segurança e LGPD

- **Verificação de propriedade:** se alguém informar um número de
  processo/container/BL que pertence a OUTRO cliente (telefone
  diferente do cadastrado), o bot não entrega nenhum dado — pede
  confirmação de identidade (nome/CNPJ) antes. Isso evita que uma
  pessoa descubra dados de outro cliente só adivinhando ou testando
  números de processo.
- **A IA nunca decide "de quem" é um processo** — essa parte é sempre
  determinística (`bot_engine.identificar`), e a IA só recebe os dados
  do processo já confirmado como do cliente que está conversando.
- **Registro de auditoria:** toda pergunta, dado consultado, resposta e
  eventual encaminhamento fica salvo em `atendimentos.db` (ver `db.py`),
  para rastreabilidade e conformidade com LGPD.
- **Pendente antes de produção:** confirmar com o jurídico/compliance da
  SeletoComex a base legal de tratamento desses dados, se é necessário
  aviso de privacidade na primeira interação, e definir uma política de
  retenção (por quanto tempo manter `atendimentos.db`).
- **Segurança do webhook:** ao publicar de verdade, validar a assinatura
  das requisições da Meta (`X-Hub-Signature-256`) para garantir que as
  mensagens realmente vêm do WhatsApp.

## Escalonamento para humano

Duas camadas, por segurança:

1. **Determinística** (`escalonamento.py`) — palavras-chave de
   reclamação grave, jurídico, cobrança contestada, pedido explícito de
   humano, alteração operacional do processo, ou situação excepcional
   (avaria/extravio). Roda antes de qualquer coisa, então funciona
   mesmo se a IA estiver fora do ar.
2. **Pela própria IA** (quando configurada) — o Claude também pode
   marcar `escalar=true` com um `motivo_escalonamento`, por exemplo
   quando os dados do processo são contraditórios ou a pergunta exige
   decisão humana que não estava prevista nas palavras-chave.

Em ambos os casos, o motivo é registrado no banco para você acompanhar
no painel quais tipos de situação mais geram encaminhamento.

## Painel de controle

Acesse `http://localhost:8000/painel`. Mostra: total de atendimentos,
clientes atendidos, taxa de resolução automática, processos mais
consultados, motivos de encaminhamento, atendimentos por dia, e uma
tabela com os atendimentos mais recentes (pergunta, ação tomada,
confiança, se foi encaminhado). Os dados vêm de `atendimentos.db` —
apague esse arquivo para zerar o histórico local.

---

## Como conectar ao WhatsApp real (caminho oficial — Business API)

> ⚠️ Nota de transparência: ao preparar esta seção, minha ferramenta de
> busca na web estava indisponível, então não consegui confirmar preços
> e regras mais recentes de cada provedor. Confirme valores e detalhes
> atualizados diretamente com a Meta/provedor escolhido antes de decidir.

Existem dois caminhos, ambos usando a **WhatsApp Business Platform**
(a API oficial — não é o WhatsApp comum do celular/computador):

### Opção A — Meta Cloud API direta (gratuita até certo volume)

1. Criar uma conta no [Meta Business Manager](https://business.facebook.com/)
   e um app no [Meta for Developers](https://developers.facebook.com/),
   ativando o produto **WhatsApp**.
2. Cadastrar um **número de telefone comercial** na plataforma.
3. Configurar o **Webhook** apontando para a URL pública do seu deploy
   (`https://SEU-APP.up.railway.app/webhook`), usando o mesmo valor de
   `WHATSAPP_VERIFY_TOKEN` do `.env`.
4. Preencher no `.env`: `WHATSAPP_TOKEN` e `WHATSAPP_PHONE_NUMBER_ID`.
5. Implementar o envio real dentro de `enviar_mensagem_whatsapp()` em
   `app.py` (exemplo já comentado lá).

### Opção B — Provedor/BSP (Business Solution Provider)

Empresas como **Z-API**, **Take Blip** ou **Twilio** intermediam o
cadastro na Meta e oferecem um painel/API mais simples de integrar,
geralmente por uma mensalidade — pode ser mais rápido para começar.

**Sobre usar o mesmo número que você já tem no computador:** confirme
diretamente com a Meta ou o provedor escolhido se é possível manter o
app comum funcionando no mesmo número ("coexistência") sem perder
histórico/acesso. Na dúvida, o caminho mais seguro é registrar um
número comercial novo só para o bot.

**Recomendação:** comece pela Opção B para validar com clientes reais
rapidamente, e migre para a Opção A se o volume crescer.

---

## Como conectar ao CONEXOS (seu sistema real)

1. **Verificar no próprio CONEXOS**: procure no painel por "Integrações",
   "API", "Webhooks" ou "Configurações avançadas".
2. **Falar com o suporte/gerente de conta do CONEXOS**: use o texto
   pronto em [`mensagem_para_conexos.md`](./mensagem_para_conexos.md).
3. **Quando a resposta chegar**, me envie a documentação e eu implemento
   `conexos_connector.py` de verdade — o resto do bot não precisa mudar.

Alterne entre mock e CONEXOS pela variável `ERP_BACKEND` no `.env`
(`mock` ou `conexos`).

---

## Camada de IA (Claude) — como ativar

Preencha `ANTHROPIC_API_KEY` no `.env`. Opcionalmente, `ANTHROPIC_MODEL`
para trocar o modelo (padrão: um modelo Claude atual de alta
capacidade, adequado para seguir instruções longas e complexas como o
prompt mestre). O prompt do sistema está em `system_prompt.py` — se as
regras de negócio mudarem (novos tipos de escalonamento, novo tom de
voz, etc.), é ali que se ajusta, sem tocar no resto do código.

---

## Como publicar o bot (deploy) — Railway ou Render

1. Crie uma conta em [railway.app](https://railway.app) ou
   [render.com](https://render.com).
2. Suba este projeto para um repositório no GitHub.
3. Crie um novo serviço a partir do repositório — o `Procfile` já diz
   como iniciar o servidor.
4. Configure as variáveis de ambiente do `.env.example` no painel do
   serviço (nunca suba o `.env` para o GitHub).
5. Use a URL pública gerada (+ `/webhook`) no cadastro do WhatsApp
   Business API.

**Nota:** o SQLite (`atendimentos.db`) grava em disco local — em
serviços com disco efêmero, os dados de auditoria/painel podem se
perder a cada novo deploy. Para produção, considere um banco gerenciado
(Postgres) — a interface de `db.py` foi pensada para facilitar essa troca.

## Próximos passos (estado atual: 11/08/2026)

1. ~~Protótipo v1 validado~~ ✅
2. ~~Implementar as regras do prompt mestre (IA, escalonamento,
   segurança, auditoria, painel)~~ ✅ — modo fallback testado
   ponta a ponta; modo IA testado com chamada simulada (sem chave real).
3. **Você:** configurar `ANTHROPIC_API_KEY` e testar o modo IA de
   verdade — posso ajudar a revisar as primeiras respostas reais e
   ajustar o `system_prompt.py` se necessário.
4. **Você:** enviar `mensagem_para_conexos.md` ao suporte do CONEXOS.
5. **Você:** decidir e criar conta no caminho de WhatsApp (Opção A/B).
6. **Eu, quando você tiver a doc do CONEXOS:** implementar
   `conexos_connector.py` de verdade.
7. **Você:** criar conta no Railway/Render para publicarmos com URL
   pública.
8. Rodar um piloto com um grupo pequeno de clientes, acompanhando pelo
   painel, antes de liberar para todos.
