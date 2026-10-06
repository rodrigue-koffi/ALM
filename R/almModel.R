# =============================================================================
# almModel.R : ETAPE 3, moteur ALM de projection (miroir exact de almModel.py)
# =============================================================================
dynamicLapse <- function(gap) { out <- 0
  for (k in c("plafond", "plancher")) { p <- dynLapse[[k]]; w <- if (k == "plafond") dynamicLapseWeight else 1 - dynamicLapseWeight
    rc <- ifelse(gap < p["alpha"], p["rcMax"], ifelse(gap < p["beta"], p["rcMax"] * (gap - p["beta"]) / (p["alpha"] - p["beta"]),
          ifelse(gap <= p["gamma"], 0, ifelse(gap <= p["delta"], p["rcMin"] * (gap - p["gamma"]) / (p["delta"] - p["gamma"]), p["rcMin"]))))
    out <- out + w * rc }
  as.numeric(out) }
bondMV <- function(N, Cp, S, P) { mv <- rep(0, nrow(N))
  for (k in 1:NB) { if (!any(N[, k] != 0)) next; j <- 1:k; surv <- outer(1 - S[, k], j, `^`)
    mv <- mv + Cp[, k] * rowSums(P[, 1:k, drop = FALSE] * surv) + N[, k] * P[, k] * surv[, k] }
  mv }
solveServed <- function(pm, tmg, amount, target) {
  lo <- rep(-0.05, nrow(pm)); hi <- pmax(target, 0); need <- function(R) rowSums(pm * pmax(matrix(tmg, nrow(pm), length(tmg), byrow = TRUE), R))
  ok <- need(hi) <= amount + 1e-6
  for (i in 1:40) { mid <- (lo + hi) / 2; big <- need(mid) > amount; hi <- ifelse(big, mid, hi); lo <- ifelse(big, lo, mid) }
  ifelse(ok, pmax(target, 0), lo) }
projectR <- function(sc, hw, mp, b, o, alloc = targetAllocation, shocks = list(), H = horizon, guaranteedOnly = FALSE) {
  n <- nrow(sc$D); M <- nrow(mp); tmg <- mp$tmg; tmgM <- matrix(tmg, n, M, byrow = TRUE)
  pm <- matrix(mp$pm, n, M, byrow = TRUE); age <- matrix(mp$age, n, M, byrow = TRUE); anc <- matrix(mp$anciennete, n, M, byrow = TRUE); isH <- mp$sexe == "H"
  N0 <- Cp0 <- S0 <- numeric(NB); for (i in seq_len(nrow(b))) { k <- b$maturiteResiduelle[i]; N0[k] <- N0[k] + b$nominal[i]; Cp0[k] <- Cp0[k] + b$coupon[i] * b$nominal[i]; S0[k] <- S0[k] + b$spread[i] * b$nominal[i] }
  S0 <- ifelse(N0 > 0, S0 / N0, 0); N <- matrix(N0, n, NB, byrow = TRUE); Cp <- matrix(Cp0, n, NB, byrow = TRUE); S <- matrix(S0, n, NB, byrow = TRUE)
  P0 <- matrix(hw$P(1:NB), n, NB, byrow = TRUE); bondBook <- rowSums(N)
  gv <- function(cl, f) rep(o[[f]][o$classe == cl], n)
  eqMv <- gv("actions", "valeurMarche") * (1 - if (is.null(shocks$equity)) 0 else shocks$equity); eqBook <- gv("actions", "valeurComptable")
  prMv <- gv("immobilier", "valeurMarche") * (1 - if (is.null(shocks$property)) 0 else shocks$property); prBook <- gv("immobilier", "valeurComptable"); cash <- gv("monetaire", "valeurMarche")
  rcRes <- rep(totalReserves * capitalisationReservePct, n); ppe <- matrix(0, n, ppeMaxYears); ppe[, ppeMaxYears] <- totalReserves * ppeInitialPct
  comp <- rep(marketRate2025, n); served <- rep(marketRate2025, n); mv0 <- bondMV(N, Cp, S, P0) + eqMv + prMv + cash
  keys <- c("prestations", "frais", "impots", "dividendes", "tauxServi", "tauxConcurrent", "pm", "ppe", "resultat", "rachatsTotaux", "tauxRachatConjoncturel", "coutGarantie")
  out <- setNames(lapply(keys, function(k) matrix(0, n, H)), keys); infl <- 1
  Pmat <- function(t) if (t == 0) P0 else sapply(1:NB, function(j) hw$Ptr(t, t + j, sc$r[, t + 1]))
  for (t in 0:(H - 1)) {
    Pt <- Pmat(t); if (is.null(dim(Pt))) Pt <- matrix(Pt, nrow = n)
    bondMv <- bondMV(N, Cp, S, Pt); total <- bondMv + eqMv + prMv + cash; realized <- rep(0, n)
    for (cl in c("eq", "pr")) { mvv <- if (cl == "eq") eqMv else prMv; bk <- if (cl == "eq") eqBook else prBook; w <- alloc[[if (cl == "eq") "actions" else "immobilier"]]
      tgt <- w * total; sell <- pmax(mvv - tgt, 0); buy <- pmax(tgt - mvv, 0); fr <- ifelse(mvv > 0, sell / mvv, 0)
      realized <- realized + fr * (mvv - bk); bk <- bk * (1 - fr) + buy; mvv <- mvv - sell + buy; cash <- cash + sell - buy
      if (cl == "eq") { eqMv <- mvv; eqBook <- bk } else { prMv <- mvv; prBook <- bk } }
    tgB <- alloc[["obligations"]] * total; buyB <- pmax(tgB - bondMv, 0); sellB <- pmax(bondMv - tgB, 0); frB <- ifelse(bondMv > 0, sellB / bondMv, 0)
    gainB <- frB * (bondMv - bondBook); N <- N * (1 - frB); Cp <- Cp * (1 - frB); bondBook <- bondBook * (1 - frB)
    rcRes <- rcRes + pmax(gainB, 0); lossB <- pmax(-gainB, 0); takeRc <- pmin(lossB, rcRes); rcRes <- rcRes - takeRc; realized <- realized - (lossB - takeRc)
    cash <- cash + sellB - buyB; par <- (1 - Pt[, newBondMaturity]) / rowSums(Pt[, 1:newBondMaturity, drop = FALSE]); k <- newBondMaturity
    S[, k] <- ifelse(N[, k] + buyB > 0, S[, k] * N[, k] / (N[, k] + buyB), 0); N[, k] <- N[, k] + buyB; Cp[, k] <- Cp[, k] + par * buyB; bondBook <- bondBook + buyB
    loss <- rowSums(S * N); N <- N * (1 - S); Cp <- Cp * (1 - S); bondBook <- bondBook - loss
    coupons <- rowSums(Cp); red <- N[, 1]; bondBook <- bondBook - red
    N <- cbind(N[, -1, drop = FALSE], 0); Cp <- cbind(Cp[, -1, drop = FALSE], 0); S <- cbind(S[, -1, drop = FALSE], 0)
    gE <- sc$equity[, t + 2] / sc$equity[, t + 1]; gP <- sc$property[, t + 2] / sc$property[, t + 1]
    eqMv <- eqMv * gE; dv <- eqMv * equityDividendYield / (1 + equityDividendYield); eqMv <- eqMv - dv
    prMv <- prMv * gP; rent <- prMv * propertyRentYield / (1 + propertyRentYield); prMv <- prMv - rent
    cashInt <- cash * (sc$D[, t + 1] / sc$D[, t + 2] - 1); cash <- cash + cashInt + coupons + red + dv + rent
    finRes <- coupons + dv + rent + cashInt + realized - loss
    q <- qxM(isH[col(age)], age)
    dyn <- if (guaranteedOnly) rep(0, n) else dynamicLapse(served - comp)
    lap <- pmin(pmax(structuralLapse(anc) + (if (guaranteedOnly) 0 else dyn), 0), 1) * (1 - q)
    leavers <- pm * (q + lap); benefits <- rowSums(leavers * (1 + tmgM)); pm <- pm - leavers
    loadings <- rowSums(pm * loadingOnReserves); expenses <- rowSums(pm) * expenseOnReserves * infl * (if (is.null(shocks$expenseMult)) 1 else shocks$expenseMult)
    tech <- loadings - expenses; intLeav <- rowSums(leavers * tmgM); pmTot <- rowSums(pm)
    share <- ifelse(pmTot > 0, pmTot / (pmTot + rcRes + totalReserves * socialEquityPct), 0)
    minPb <- pmax(pbFinancial * finRes * share + pbTechnical * pmax(tech, 0) - intLeav, 0)
    forced <- ppe[, 1]; ppe[, 1] <- 0
    comp <- competitorSmoothing * comp + (1 - competitorSmoothing) * (zeroRate(hw, t, 10, sc$r[, t + 1]) + competitorMargin)
    target <- pmax(comp + targetSpread, 0); pmNet <- pm * (1 - loadingOnReserves)
    needT <- rowSums(pmNet * pmax(tmgM, target)); gCost <- rowSums(pmNet * tmgM); avail <- minPb + forced
    if (guaranteedOnly) { credited <- gCost; dotPpe <- repPpe <- realizeX <- sacrifice <- rep(0, n); ppe[, ] <- 0 } else {
      short <- pmax(needT - avail, 0); repPpe <- pmin(short, rowSums(ppe)); rem <- repPpe
      for (kk in 1:ppeMaxYears) { take <- pmin(rem, ppe[, kk]); ppe[, kk] <- ppe[, kk] - take; rem <- rem - take }
      short2 <- short - repPpe; realizeX <- pmin(pmax(eqMv - eqBook, 0), short2 / pbFinancial); eqBook <- eqBook + realizeX; finRes <- finRes + realizeX
      short3 <- pmax(short2 - pbFinancial * realizeX, 0); sacrifice <- pmin(short3, pmax((1 - pbFinancial) * finRes * share, 0))
      credPb <- avail + repPpe + pbFinancial * realizeX + sacrifice; dotPpe <- pmax(credPb - pmax(needT, forced), 0)
      credited <- pmax(pmax(credPb - dotPpe, 0), gCost); ppe <- cbind(ppe[, -1, drop = FALSE], dotPpe) }
    sN <- solveServed(pmNet, tmg, credited, pmax(credited / pmax(rowSums(pmNet), 1e-9) + 0.05, 0))
    rateMp <- pmax(tmgM, sN); pm <- pmNet * (1 + rateMp); credTot <- rowSums(pmNet * rateMp)
    funded <- avail + repPpe + pbFinancial * realizeX + sacrifice; cost <- if (guaranteedOnly) rep(0, n) else pmax(credTot - funded, 0)
    served <- ifelse(rowSums(pmNet) > 0, credTot / rowSums(pmNet), 0)
    result <- finRes + loadings - expenses - intLeav - credTot - (dotPpe - repPpe - forced); tax <- TAX * pmax(result, 0); dvd <- result - tax
    cash <- cash - benefits - expenses - tax - dvd; infl <- infl * (1 + expenseInflation); age <- age + 1; anc <- anc + 1
    vals <- list(prestations = benefits, frais = expenses, impots = tax, dividendes = dvd, tauxServi = served, tauxConcurrent = comp, pm = rowSums(pm),
                 ppe = rowSums(ppe), resultat = result, rachatsTotaux = rowSums(leavers), tauxRachatConjoncturel = dyn, coutGarantie = cost)
    for (kk in names(vals)) out[[kk]][, t + 1] <- vals[[kk]]
  }
  PH <- Pmat(H); if (is.null(dim(PH))) PH <- matrix(PH, nrow = n)
  mvH <- bondMV(N, Cp, S, PH) + eqMv + prMv + cash
  out$terminalAssures <- rowSums(pm) + rowSums(ppe); out$terminalActionnaires <- mvH - out$terminalAssures; out$mv0 <- mv0
  out
}
valuationR <- function(out, sc, H = horizon) { D <- sc$D[, 2:(H + 1), drop = FALSE]
  be <- rowSums(D * (out$prestations + out$frais)) + sc$D[, H + 1] * out$terminalAssures
  pvfp <- rowSums(D * out$dividendes) + sc$D[, H + 1] * out$terminalActionnaires; tax <- rowSums(D * out$impots)
  list(be = be, pvfp = pvfp, impots = tax, fuite = out$mv0 - be - pvfp - tax) }
