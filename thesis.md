---
title: "Análise do mercado de skins de CS:GO: preços, retornos, carteiras e métodos de aprendizado de máquina (2020–2023)"
author: Pedro Mendes
bibliography: references.bib
lang: pt-BR
nocite: "@*"
link-citations: true
---

# Introdução

```{=latex}
\lipsum[2]
```

```{=latex}
\newpage
```

# Revisão Bibliográfica

```{=latex}
\lipsum[4]
```

```{=latex}
\newpage
```

# Dados

```{=latex}
\lipsum[4]
```

```{=latex}
\insertGreatTable{Cobertura temporal — CS:GO}{coverage_daily}{output/tables/coverage_daily.tex}
\insertFigure{Ativos com preço em cada dia}{0.9}{output/images/coverage.png}{coverage}{Elaboração própria.}
\insertGreatTable{Auditoria da limpeza dos dados — CS:GO}{audit}{output/tables/audit.tex}
\insertGreatTable{Histórico de preços dos itens — CS:GO}{coverage_items}{output/tables/coverage_items.tex}
\insertGreatTable{Itens selecionados e excluídos por semestre do primeiro registro — CS:GO}{selection}{output/tables/selection.tex}
\insertGreatTable{Qualidade do conjunto de dados limpo — CS:GO}{quality}{output/tables/quality.tex}
\insertGreatTable{Saltos de preço — CS:GO}{jumps}{output/tables/jumps.tex}
\insertGreatTable{Dias com mais saltos de preço — CS:GO}{jump_days}{output/tables/jump_days.tex}
\insertGreatTable{Parcela de dias com preço por item — CS:GO}{activity}{output/tables/activity.tex}
\insertGreatTable{Preço Steam de 24 horas e referências alternativas — CS:GO}{sources}{output/tables/sources.tex}
```

```{=latex}
\newpage
```

# Metodologia

## Escopo teórico da avaliação das carteiras

O estudo compara estratégias de investimento em carteiras teóricas, sem simular a execução de ordens na Steam. A avaliação admite posições fracionárias como recurso de cálculo, embora a plataforma permita apenas a negociação de itens inteiros.

O capital inicial corresponde a uma unidade normalizada. Para uma carteira com $k$ ativos, o peso inicial $w_{i,0}$ do ativo $i$ segue:

$$
w_{i,0} = \frac{1}{k}, \qquad i = 1, \ldots, k.
$$

Dentro dessas hipóteses, o valor monetário do capital inicial não altera os retornos percentuais. O número de ativos continua relevante, pois altera a composição e a concentração da carteira.

A estratégia buy-and-hold mantém as posições sem rebalanceamento, de modo que os pesos variam com os preços. O cálculo aplica a taxa de venda dos parâmetros uma única vez, na liquidação final. O estudo não impõe um orçamento monetário fixo nem quantidades inteiras de cada item.

Uma aplicação real exige considerar a indivisibilidade dos itens, o saldo não investido e os preços efetivos de execução. Também exige considerar a diferença entre ofertas de compra e venda, a profundidade do mercado e o volume disponível. A execução real ainda depende dos prazos de negociação, dos arredondamentos e de outros custos.

Os resultados representam o desempenho das regras sob essas hipóteses, não a rentabilidade executável de uma conta real.

```{=latex}
\newpage
```

# Resultados

```{=latex}
\lipsum[4]
```

## Retornos

```{=latex}
\insertGreatTable{Retornos diários por item — CS:GO}{returns}{output/tables/returns.tex}
\insertGreatTable{Risco dos retornos diários por item — CS:GO}{returns_risk}{output/tables/returns_risk.tex}
\insertGreatTable{Momentos dos retornos diários — CS:GO}{distribution}{output/tables/distribution.tex}
\insertGreatTable{Percentis dos retornos diários — CS:GO}{distribution_quantiles}{output/tables/distribution_quantiles.tex}
\insertFigure{Distribuição dos retornos diários}{0.9}{output/images/returns_histogram.png}{returns}{Elaboração própria.}
\insertFigure{Distribuição das medidas de retorno entre os itens}{0.9}{output/images/item_distributions.png}{item_distributions}{Elaboração própria.}
\insertGreatTable{Retornos diários por raridade — CS:GO}{rarity}{output/tables/rarity.tex}
\insertGreatTable{Retornos diários por faixa de preço — CS:GO}{price_buckets}{output/tables/price_buckets.tex}
```

## Mercado

```{=latex}
\insertFigure{Índice do mercado e volatilidade móvel}{0.9}{output/images/market.png}{market}{Elaboração própria.}
\insertGreatTable{Retornos e dependência no mercado — CS:GO}{dynamics}{output/tables/dynamics.tex}
```

## Efeitos de calendário

```{=latex}
\insertGreatTable{Retornos diários dos itens por fase da promoção — CS:GO}{item_phases}{output/tables/item_phases.tex}
\insertGreatTable{Retorno diário do mercado por fase da promoção — CS:GO}{sale_phases}{output/tables/sale_phases.tex}
\insertGreatTable{Efeito da promoção por raridade — CS:GO}{sale_rarity}{output/tables/sale_rarity.tex}
\insertGreatTable{Retorno diário do mercado por dia da semana — CS:GO}{weekday}{output/tables/weekday.tex}
```

## Plano de avaliação

```{=latex}
\insertGreatTable{Comparação entre períodos — CS:GO}{regimes}{output/tables/regimes.tex}
\insertGreatTable{Divisão cronológica entre treinamento, validação e teste — CS:GO}{evaluation_split}{output/tables/evaluation_split.tex}
```

## Carteira buy-and-hold

```{=latex}
\insertGreatTable{Candidatos que passam pelos limites de treinamento — CS:GO}{portfolio_thresholds}{output/tables/portfolio_thresholds.tex}
\insertGreatTable{Comparação de tamanhos de carteira na validação — CS:GO}{portfolio_sweep}{output/tables/portfolio_sweep.tex}
\insertGreatTable{Raridade dos itens da carteira — CS:GO}{portfolio_rarity}{output/tables/portfolio_rarity.tex}
\insertGreatTable{Carteira buy-and-hold — CS:GO}{portfolio}{output/tables/portfolio.tex}
\insertGreatTable{ROI líquido da carteira buy-and-hold e das referências — CS:GO}{portfolio_benchmarks}{output/tables/portfolio_benchmarks.tex}
\insertGreatTable{Comparação direta entre carteiras buy-and-hold — CS:GO}{portfolio_random}{output/tables/portfolio_random.tex}
\insertGreatTable{Distribuição dos resultados das carteiras aleatórias — CS:GO}{portfolio_random_distribution}{output/tables/portfolio_random_distribution.tex}
\insertFigure{Valor das carteiras nos dias de teste}{0.9}{output/images/portfolio_value.png}{portfolio_value}{Elaboração própria.}
\insertGreatTable{Contribuição de cada item da carteira — CS:GO}{portfolio_items}{output/tables/portfolio_items.tex}
\insertGreatTable{Sensibilidade dos resultados — CS:GO}{sensitivity}{output/tables/sensitivity.tex}
```

```{=latex}
\newpage
```

# Limitações

- A fonte é secundária: a csgotrader.app lê médias agregadas da steamapis. Não há volume, número de negócios nem diferença entre oferta e demanda. Por isso o trabalho não repete os testes de volume e de spread de Glaus (2022) e não separa ruído de valor.
- A janela tem dez promoções da Steam. O poder para testar o efeito de promoção é limitado, e os resultados descrevem uma associação, não uma causa. Não há controle para outros eventos do calendário, como torneios.
- O preço de 24 horas é uma média de vendas, não um preço executável. Não há livro de ofertas, então deslizamento e profundidade de mercado ficam fora do modelo.
- Os fundos da carteira Steam não podem ser sacados. O preço da Steam é cerca de 1,28 vez o da BUFF, então o valor em dinheiro é menor que o ROI líquido calculado.
- Dias com captura incompleta foram descartados (56 dias), e 16 dias não têm instantâneo. A fonte não publica dias depois de 30/10/2023, então só 28 dias seguem o lançamento do CS2.
- Itens sem ordens ativas não têm histórico na Steam. Isso gera viés de sobrevivência na fonte, como Glaus (2022) aponta.
- A amostra cobre 2020 a 2023 e uma só quebra de regime. Os limites de limpeza, o teto do retorno e a janela de preços são escolhas do autor. A tabela de sensibilidade mostra o efeito delas.

```{=latex}
\newpage
```

# Conclusão

```{=latex}
\lipsum[4]
```

```{=latex}
\newpage
```

# Referências {-}

::: {#refs}
:::
