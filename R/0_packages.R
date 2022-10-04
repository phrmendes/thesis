# -------------------- #
# ----- PACKAGES ----- #
# -------------------- #

if (!require("pacman")) {
  install.packages("pacman")
  library(pacman)
}

pacman::p_install(
  tidyverse,
  tidymodels,
  arrow,
  xts,
  data.table,
  collapse,
  forecast,
  smooth
)
