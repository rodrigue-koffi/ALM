# =============================================================================
# steering.R : ETAPES 3 a 5 en R (projection, valorisation, pilotage) (miroir de projection.py, valuation.py, steering.py)
# =============================================================================
runProjection <- function(e, pf, cv) {
  banner("\u00c9TAPE 3 : PROJECTION ALM (R)")
  st <- projectR(e$sc, e$hw, pf$mp, pf$b, pf$o); ce0 <- certaintyEquivalent(cv$tauxAvecVa); ce <- projectR(ce0$sc, ce0$hw, pf$mp, pf$b, pf$o)
  tab <- data.frame(annee = 1:10, tauxServiEquivalentCertain = ce$tauxServi[1, 1:10], ppeEquivalentCertain = ce$ppe[1, 1:10], tauxServiMoyenStochastique = colMeans(st$tauxServi[, 1:10]))
  saveTable(tab, "e3ProjectionEquivalentCertain"); print(tab, row.names = FALSE)
  p <- ggplot(tab, aes(annee)) + geom_line(aes(y = tauxServiEquivalentCertain * 100, colour = "\u00e9quivalent certain")) + geom_line(aes(y = tauxServiMoyenStochastique * 100, colour = "moyenne stochastique")) +
    labs(title = "Taux servi projet\u00e9 (%)", x = "ann\u00e9e", y = "%", colour = NULL); saveFig(p, "e3ProjectionAlm")
  list(st = st, ce = ce, ce0 = ce0)
}
runValuation <- function(e, pr, pf) {
  banner("\u00c9TAPE 4 : VALORISATION (R)")
  vs <- valuationR(pr$st, e$sc); vc <- valuationR(pr$ce, pr$ce0$sc); gu <- projectR(e$sc, e$hw, pf$mp, pf$b, pf$o, guaranteedOnly = TRUE); vg <- valuationR(gu, e$sc)
  tab <- data.frame(poste = c("actifs", "BE stochastique", "BE \u00e9quivalent certain", "TVOG actionnaires", "BE garanti", "FDB", "PVFP stochastique", "imp\u00f4ts", "fuite"),
                    montant = c(pr$st$mv0[1], mean(vs$be), vc$be, vc$pvfp - mean(vs$pvfp), mean(vg$be), mean(vs$be) - mean(vg$be), mean(vs$pvfp), mean(vs$impots), mean(vs$fuite)))
  saveTable(tab, "e4Valorisation"); print(tab, row.names = FALSE)
  p <- ggplot(data.frame(be = vs$be / 1e6), aes(be)) + geom_histogram(bins = 40, fill = palette[1]) + labs(title = "BE par sc\u00e9nario (M\u20ac)", x = "M\u20ac", y = NULL); saveFig(p, "e4Valorisation")
  tab
}
navForR <- function(Z, rates, pf, alloc = targetAllocation, shocks = list()) { hw <- hwMake(rates, hwMeanReversion, hwVolatility); sc <- simulateR(hw, Z)
  out <- projectR(sc, hw, pf$mp, pf$b, pf$o, alloc, shocks); v <- valuationR(out, sc); list(nav = out$mv0[1] - mean(v$be), be = mean(v$be), out = out) }
marketScrR <- function(Z, cv, pf, alloc = targetAllocation) {
  b0 <- navForR(Z, cv$tauxAvecVa, pf, alloc)
  L <- c(tauxHausse = b0$nav - navForR(Z, cv$tauxAvecVaChocHausse, pf, alloc)$nav, tauxBaisse = b0$nav - navForR(Z, cv$tauxAvecVaChocBaisse, pf, alloc)$nav,
         actions = b0$nav - navForR(Z, cv$tauxAvecVa, pf, alloc, list(equity = equityShock))$nav, immobilier = b0$nav - navForR(Z, cv$tauxAvecVa, pf, alloc, list(property = propertyShock))$nav)
  A <- if (L["tauxHausse"] >= L["tauxBaisse"]) 0 else 0.5; M <- matrix(c(1, A, A, A, 1, 0.75, A, 0.75, 1), 3)
  list(nav = b0$nav, L = L, scr = aggregateScr(c(max(L[1:2], 0), max(L["actions"], 0), max(L["immobilier"], 0)), M), out = b0$out) }
runSteering <- function(e, pf, cv) {
  banner("\u00c9TAPE 5 : PILOTAGE ALM (R)")
  m <- marketScrR(e$Z, cv, pf); scrTab <- data.frame(choc = c(names(m$L), "SCR de march\u00e9 agr\u00e9g\u00e9"), perteValeurNette = c(m$L, m$scr))
  grid <- do.call(rbind, lapply(c(0.04, 0.08, 0.12, 0.16, 0.20), function(eq) do.call(rbind, lapply(c(0.04, 0.07, 0.10), function(pr) {
    al <- c(obligations = 1 - 0.05 - eq - pr, actions = eq, immobilier = pr, monetaire = 0.05); g <- marketScrR(e$Z, cv, pf, al)
    data.frame(actions = eq, immobilier = pr, valeurNette = g$nav, scrMarche = g$scr, tauxServiMoyen10Ans = mean(g$out$tauxServi[, 1:10])) }))))
  saveTable(scrTab, "e5ScrMarcheAlm"); saveTable(grid, "e5AllocationStrategique"); print(scrTab, row.names = FALSE)
  p <- ggplot(grid, aes(scrMarche / 1e6, tauxServiMoyen10Ans * 100, colour = actions)) + geom_point(size = 3) + labs(title = "Allocation : SCR de march\u00e9 contre taux servi", x = "SCR (M\u20ac)", y = "%")
  saveFig(p, "e5PilotageAlm")
  list(scrTab = scrTab, grid = grid)
}
