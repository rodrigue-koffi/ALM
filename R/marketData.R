# =============================================================================
# marketData.R : ETAPE 1.1, courbe EIOPA par Smith-Wilson (miroir de marketData.py)
# =============================================================================
mats <- 1:maxMaturity
wilsonM <- function(t, u, a, w) outer(t, u, function(x, y) { lo <- pmin(x, y); hi <- pmax(x, y); exp(-w * (x + y)) * (a * lo - 0.5 * exp(-a * hi) * (exp(a * lo) - exp(-a * lo))) })
smithWilson <- function(liqMat, liqRates, u = ufr, out = mats) {
  w <- log(1 + u); p <- (1 + liqRates)^-liqMat
  cf <- function(a, t) { z <- solve(wilsonM(liqMat, liqMat, a, w), p - exp(-w * liqMat)); exp(-w * t) + as.numeric(wilsonM(t, liqMat, a, w) %*% z) }
  gap <- function(a) { T <- max(liqMat) + convergencePeriod; abs(-(log(cf(a, T + 0.001)) - log(cf(a, T - 0.001))) / 0.002 - w) - convergenceTolerance }
  a <- if (gap(alphaMin) <= 0) alphaMin else uniroot(gap, c(alphaMin, 1), tol = 1e-12)$root
  cf(a, out)^(-1 / out) - 1
}
shockCurve <- function(r, sh, dir) { fac <- sapply(seq_along(r), function(m) if (m <= 90) sh[[if (dir == "up") "chocHausse" else "chocBaisse"]][sh$maturite == m] else 0.2)
  if (dir == "up") r + pmax(r * fac, upShockMin) else ifelse(r > 0, r * (1 - fac), r) }
runMarketData <- function() {
  banner("\u00c9TAPE 1.1 : COURBE EIOPA (R)")
  h <- read.csv(file.path(dataRaw, "eiopaRfrFranceHistorique.csv")); row <- h[h$reference_date == valuationDate, ]
  pr <- as.numeric(row[, c("rate_1y", "rate_5y", "rate_10y", "rate_20y")]); sh <- read.csv(file.path(dataRaw, "eiopaChocsTauxFormuleStandard.csv"))
  cv <- data.frame(maturite = mats, tauxSansVa = smithWilson(c(1, 5, 10, 20), pr), tauxAvecVa = smithWilson(c(1, 5, 10, 20), pr + row$va))
  cv$tauxAvecVaChocHausse <- shockCurve(cv$tauxAvecVa, sh, "up"); cv$tauxAvecVaChocBaisse <- shockCurve(cv$tauxAvecVa, sh, "down")
  saveTable(cv, "e1CourbesEiopa"); cv
}
