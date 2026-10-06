# =============================================================================
# config.R : hypotheses du projet ALM (miroir de python/alm/config.py)
# =============================================================================
getRoot <- function() { a <- commandArgs(FALSE); f <- sub("--file=", "", a[grep("--file=", a)]); if (length(f) == 1) normalizePath(file.path(dirname(f), "..")) else normalizePath("..") }
root <- getRoot(); dataRaw <- file.path(root, "data", "raw"); dataProc <- file.path(root, "data", "processed")
outFig <- file.path(root, "outputs", "R", "figures"); outTab <- file.path(root, "outputs", "R", "tables")
for (p in c(outFig, outTab)) dir.create(p, recursive = TRUE, showWarnings = FALSE)
valuationDate <- "2026-06-30"; ufr <- 0.033; convergencePeriod <- 40; convergenceTolerance <- 1e-4; alphaMin <- 0.05; maxMaturity <- 150; upShockMin <- 0.01
totalReserves <- 1e9; loadingOnReserves <- 0.0063; expenseOnReserves <- 0.0035; expenseInflation <- 0.02; marketRate2025 <- 0.0263
ppeInitialPct <- 0.04; capitalisationReservePct <- 0.015; socialEquityPct <- 0.065
structuralLapseP <- c(avant8Ans = 0.03, a8Ans = 0.09, apres8Ans = 0.055)
dynLapse <- list(plafond = c(alpha = -0.06, beta = -0.02, gamma = 0.01, delta = 0.02, rcMin = -0.06, rcMax = 0.40),
                 plancher = c(alpha = -0.04, beta = 0, gamma = 0.01, delta = 0.04, rcMin = -0.04, rcMax = 0.20))
dynamicLapseWeight <- 0.5; competitorSmoothing <- 0.5; competitorMargin <- 0.003; pbFinancial <- 0.85; pbTechnical <- 0.90; ppeMaxYears <- 8; targetSpread <- 0
horizon <- 50; targetAllocation <- c(obligations = 0.76, actions = 0.12, immobilier = 0.07, monetaire = 0.05); newBondMaturity <- 10
equityDividendYield <- 0.03; propertyRentYield <- 0.035
nScenarios <- 1000; hwMeanReversion <- 0.03; hwVolatility <- 0.0085; equityVolatility <- 0.18; propertyVolatility <- 0.10
corrRateEquity <- 0.10; corrRateProperty <- 0.05; corrEquityProperty <- 0.40; equityShock <- 0.39; propertyShock <- 0.25; TAX <- 0.2583; NB <- 30
