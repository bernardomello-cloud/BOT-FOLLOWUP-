name: Followup semanal

# Dispara o resumo semanal de follow-up toda sexta-feira, chamando o
# endpoint protegido do bot (POST /cron/followup-semanal). O bot só
# gera os RASCUNHOS e grava no banco — não manda nada pro cliente.
# Veja followup_semanal.py e app.py para o que esse endpoint faz.

on:
  schedule:
    # 11:00 UTC = 08:00 no horário de Brasília (UTC-3, sem horário de
    # verão hoje em dia). Ajuste se precisar de outro horário/dia.
    - cron: "0 11 * * 5"
  workflow_dispatch: {}   # permite disparar manualmente pelo botão "Run workflow" no GitHub

jobs:
  disparar-followup-semanal:
    runs-on: ubuntu-latest
    steps:
      - name: Chamar endpoint de geração dos rascunhos
        run: |
          resposta=$(curl -s -w "\n%{http_code}" -X POST \
            "https://bot-follow-up.onrender.com/cron/followup-semanal" \
            -H "X-Cron-Secret: ${{ secrets.CRON_SECRET }}")
          codigo=$(echo "$resposta" | tail -n1)
          corpo=$(echo "$resposta" | sed '$d')
          echo "HTTP $codigo"
          echo "$corpo"
          if [ "$codigo" != "200" ]; then
            echo "Falha ao gerar o resumo semanal (HTTP $codigo)"
            exit 1
          fi
