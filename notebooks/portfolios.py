# %% [markdown]
# # Carteira de compra e retenção dos itens CS:GO
#
# A carteira de compra e retenção é a referência de desempenho mais simples. Este caderno mede se
# escolher itens pelo treino gera retorno líquido no teste. O resultado serve de base de comparação
# para o modelo.

# %%
from argparse import ArgumentParser
from pathlib import Path

from great_tables import GT
from helpers.formatting import metric_text_table, write_latex_table
from helpers.params import load_params
from helpers.paths import repo
from helpers.portfolio import eligible_assets, hold_positions, portfolio_returns, portfolio_summary, training_candidates
from helpers.runtime import notebook_arguments
from helpers.schemas import read_table

# %%
PORTFOLIO_LABELS = {
    "assets": "Itens",
    "weeks": "Semanas de teste",
    "sale_fee": "Taxa de venda (%)",
    "roi": "ROI",
    "sharpe": "Sharpe",
    "sortino": "Sortino",
}

PORTFOLIO_FORMATS = {
    "assets": "d",
    "weeks": "d",
    "sale_fee": ".0f",
    "roi": ".2%",
    "sharpe": ".2f",
    "sortino": ".2f",
}

# %% [markdown]
# ## Argumentos da linha de comando

# %%
portfolio_params = load_params()["portfolio"]

parser = ArgumentParser(description="Carteira de compra e retenção com pesos iguais.")
parser.add_argument("--prices", type=Path, default=repo() / "files/prices.parquet", help="Preços semanais limpos.")
parser.add_argument("--k", type=int, default=10, help="Número de itens na carteira.")
parser.add_argument("--rank", choices=["roi", "sharpe", "sortino"], default="roi", help="Razão de treino.")
parser.add_argument("--roi", type=float, default=portfolio_params["min_roi"], help="ROI mínimo no treino.")
parser.add_argument("--sharpe", type=float, default=portfolio_params["min_sharpe"], help="Sharpe mínimo no treino.")
parser.add_argument("--sortino", type=float, default=portfolio_params["min_sortino"], help="Sortino mínimo no treino.")
parser.add_argument(
    "--buy-and-hold",
    type=Path,
    default=repo() / "files/buy_and_hold.parquet",
    help="Linhas semanais da carteira.",
)
parser.add_argument("--output", type=Path, default=repo() / "files/portfolio.parquet", help="Métricas da carteira.")
parser.add_argument("--table", type=Path, default=repo() / "tex/tables/portfolio.tex", help="Tabela LaTeX.")
args = parser.parse_args(notebook_arguments())

if args.k < 1:
    message = "k must be positive"
    raise SystemExit(message)

# %% [markdown]
# ## Selecionar itens elegíveis nas semanas de treino
#
# A seleção usa apenas as semanas de treino. Isso impede que informação do período de teste influencie
# a carteira. Só entram itens com preço na primeira semana de teste, pois só eles podem ser comprados.

# %%
prices = read_table("prices", args.prices).sort("name", "week")
thresholds = {"roi": args.roi, "sharpe": args.sharpe, "sortino": args.sortino}
selected = eligible_assets(training_candidates(prices), args.k, args.rank, thresholds)
selected

# %% [markdown]
# ## Manter a carteira nas semanas de teste e medir o desempenho
#
# A carteira mantém os itens escolhidos sem rebalanceamento. O item que deixa de ter preço mantém o
# último valor. Assim a carteira não inventa retornos nem encerra a posição antes do fim.

# %%
rows = portfolio_returns(hold_positions(prices, selected.select("name"), args.k))
rows

# %% [markdown]
# ROI, Sharpe e Sortino semanais resumem o desempenho. A taxa de venda de 15% entra uma só vez, na
# última semana, porque a estratégia vende apenas no final.

# %%
metrics = portfolio_summary(rows, args.k)
metrics

# %% [markdown]
# ## Construir a tabela da carteira para a tese

# %%
portfolio_text = metric_text_table(metrics, PORTFOLIO_LABELS, PORTFOLIO_FORMATS)

portfolio_gt = (
    GT(portfolio_text)
    .tab_header(title="Carteira de Compra e Retenção — CS:GO")
    .cols_label(metric_name="Métrica", metric_value="Valor")
    .tab_source_note(
        "Carteira igualmente ponderada nas semanas de treino, sem rebalanceamento. "
        "Taxa de venda de 15% na última semana (5% Steam e 10% do jogo). "
        "Razões semanais com taxa livre de risco zero. "
        "Sortino: média sobre o DP das semanas negativas."
    )
)
portfolio_gt

# %% [markdown]
# ## Exportar a carteira em Parquet e a tabela em LaTeX
#
# As linhas semanais e o resumo ficam em Parquet para análises posteriores. A tabela em LaTeX é
# gravada junto, para que a tese use resultados da mesma execução.

# %%
for path in (args.buy_and_hold, args.output, args.table):
    path.parent.mkdir(parents=True, exist_ok=True)

rows.write_parquet(args.buy_and_hold)
metrics.write_parquet(args.output)
write_latex_table(portfolio_gt, args.table)

for path in (args.buy_and_hold, args.output, args.table):
    print(f"Written {path}")
