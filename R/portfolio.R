# =============================================================================
# portfolio.R : ETAPE 1.2, model points, actifs, bilan social, adossement (miroir de portfolio.py)
# Les obligations sont generees par Python (tirages aleatoires) ; les model points sont reconstruits en R.
# =============================================================================
TH <- read.csv(file.path(dataRaw, "tableTH0002.csv")); TF <- read.csv(file.path(dataRaw, "tableTF0002.csv"))
qxM <- function(isH, age) { h <- pmin(approx(TH$age, TH$qx, xout = as.vector(age), rule = 2)$y, 1); f <- pmin(approx(TF$age, TF$qx, xout = as.vector(age), rule = 2)$y, 1)
  q <- ifelse(rep_len(isH, length(age)), h, f); dim(q) <- dim(age); q }
structuralLapse <- function(anc) { r <- ifelse(anc < 8, structuralLapseP["avant8Ans"], ifelse(anc < 9, structuralLapseP["a8Ans"], structuralLapseP["apres8Ans"])); dim(r) <- dim(anc); r }
modelPoints <- function() {
  ages <- c(`35` = 0.10, `45` = 0.17, `55` = 0.22, `65` = 0.24, `75` = 0.17, `85` = 0.10)
  ancs <- list(list(2, 0.22, c(`0` = 1)), list(5, 0.20, c(`0` = 1)), list(8, 0.18, c(`0` = 0.6, `0.005` = 0.4)),
               list(12, 0.20, c(`0.005` = 0.35, `0.01` = 0.40, `0.015` = 0.25)), list(20, 0.20, c(`0.015` = 0.35, `0.025` = 0.35, `0.035` = 0.30)))
  rows <- list()
  for (a in names(ages)) for (an in ancs) { if (as.numeric(a) - an[[1]] < 18) next
    for (tm in names(an[[3]])) for (sx in c("F", "H")) rows[[length(rows) + 1]] <- data.frame(age = as.numeric(a), sexe = sx, anciennete = an[[1]], tmg = as.numeric(tm),
      poids = ages[[a]] * an[[2]] * an[[3]][[tm]] * (if (sx == "F") 0.55 else 0.45)) }
  mp <- do.call(rbind, rows); mp$pm <- mp$poids / sum(mp$poids) * totalReserves; mp$poids <- NULL; mp
}
bondValue <- function(b, r, shift = 0) sapply(seq_len(nrow(b)), function(i) { t <- 1:b$maturiteResiduelle[i]; cf <- rep(b$coupon[i] * b$nominal[i], length(t)); cf[length(t)] <- cf[length(t)] + b$nominal[i]
  sum(cf / (1 + r[t] + b$spread[i] + shift)^t) })
runPortfolio <- function(cv) {
  banner("\u00c9TAPE 1.2 : MODEL POINTS, ACTIFS, ADOSSEMENT (R)")
  mp <- modelPoints(); b <- read.csv(file.path(dataRaw, "actifsObligations.csv")); o <- read.csv(file.path(dataRaw, "actifsAutres.csv"))
  b$valeurMarche <- bondValue(b, cv$tauxSansVa)
  pm <- mp$pm; age <- mp$age; anc <- mp$anciennete; lcf <- numeric(horizon); isH <- mp$sexe == "H"
  for (t in 1:horizon) { q <- as.vector(qxM(isH, age)); lap <- as.vector(structuralLapse(anc)) * (1 - q); lcf[t] <- sum(pm * (q + lap) * (1 + mp$tmg))
    pm <- pm * (1 - q - lap) * (1 + mp$tmg); age <- age + 1; anc <- anc + 1 }
  acf <- numeric(horizon); for (i in seq_len(nrow(b))) { t <- 1:b$maturiteResiduelle[i]; acf[t] <- acf[t] + b$coupon[i] * b$nominal[i]; acf[max(t)] <- acf[max(t)] + b$nominal[i] }
  t <- 1:horizon; st <- function(cf, r) { df <- (1 + r[t])^-t; pv <- sum(cf * df); c(pv, sum(t * cf * df) / pv) }
  sL <- st(lcf, cv$tauxAvecVa); sA <- st(acf, cv$tauxSansVa)
  kpi <- data.frame(indicateur = c("taux garanti moyen", "PVL obligataires", "duration passif garanti", "duration obligations", "ecart de duration"),
                    valeur = c(sum(mp$pm * mp$tmg) / totalReserves, sum(b$valeurMarche - b$valeurComptable), sL[2], sA[2], sA[2] * sA[1] / sL[1] - sL[2]))
  saveTable(kpi, "e1Indicateurs"); print(kpi, row.names = FALSE)
  list(mp = mp, b = b, o = o, kpi = kpi)
}
