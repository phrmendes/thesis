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
\input{output/tables/coverage_daily.tex}
\insertFigure{Ativos com preço em cada dia}{0.9}{output/images/coverage.png}{coverage}{Elaboração própria.}
\input{output/tables/audit.tex}
\input{output/tables/coverage_items.tex}
\input{output/tables/selection.tex}
\input{output/tables/quality.tex}
\input{output/tables/jumps.tex}
\input{output/tables/jump_days.tex}
\input{output/tables/activity.tex}
\input{output/tables/sources.tex}
```

```{=latex}
\newpage
```

# Metodologia

```{=latex}
\lipsum[4]
```

```{=latex}
\newpage
```

# Resultados

```{=latex}
\lipsum[4]
```

## Retornos

```{=latex}
\input{output/tables/returns.tex}
\input{output/tables/distribution.tex}
\insertFigure{Distribuição dos retornos diários}{0.9}{output/images/returns_histogram.png}{returns}{Elaboração própria.}
\input{output/tables/rarity.tex}
\input{output/tables/price_buckets.tex}
```

## Mercado

```{=latex}
\insertFigure{Índice do mercado e volatilidade móvel}{0.9}{output/images/market.png}{market}{Elaboração própria.}
\input{output/tables/dynamics.tex}
\input{output/tables/price_noise.tex}
\input{output/tables/stationarity.tex}
```

## Efeitos de calendário

```{=latex}
\input{output/tables/sale_seasons.tex}
\input{output/tables/sale_phases.tex}
\input{output/tables/sale_events.tex}
\input{output/tables/sale_activity.tex}
\input{output/tables/sale_rarity.tex}
\input{output/tables/weekday.tex}
```

## Desenho da avaliação

```{=latex}
\input{output/tables/regimes.tex}
\input{output/tables/walk_forward.tex}
```

## Carteira de compra e retenção

```{=latex}
\input{output/tables/portfolio_thresholds.tex}
\input{output/tables/portfolio_rarity.tex}
\input{output/tables/portfolio.tex}
\input{output/tables/portfolio_benchmarks.tex}
\input{output/tables/portfolio_sweep.tex}
\insertFigure{Valor das carteiras nos dias de teste}{0.9}{output/images/portfolio_value.png}{portfolio_value}{Elaboração própria.}
\input{output/tables/portfolio_items.tex}
\input{output/tables/sensitivity.tex}
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
