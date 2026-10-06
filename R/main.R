# =============================================================================
# main.R : version R du projet ALM (miroir de python/main.py). Usage : Rscript R/main.R [etape]
# R reconstruit la courbe, les model points, les scenarios (memes tirages gaussiens que Python) et tout le modele ALM,
# puis se reconcilie avec les tables Python.
# =============================================================================
invisible(Sys.setlocale("LC_ALL", "C.UTF-8"))
suppressPackageStartupMessages({ library(ggplot2); library(dplyr); library(tidyr) })
args <- commandArgs(trailingOnly = TRUE); etape <- if (length(args)) as.integer(args[1]) else 5
.f <- sub("--file=", "", commandArgs(FALSE)[grep("--file=", commandArgs(FALSE))]); .dir <- if (length(.f)) dirname(normalizePath(.f)) else "R"
for (f in c("config.R", "utils.R", "marketData.R", "portfolio.R", "esg.R", "almModel.R", "steering.R")) source(file.path(.dir, f), encoding = "UTF-8")
py <- function(n) readPyTable(n); hasPy <- file.exists(file.path(root, "outputs", "python", "tables", "e5ScrMarcheAlm.csv"))
cv <- runMarketData(); pf <- runPortfolio(cv)
if (hasPy) { c1 <- py("e1CourbesEiopa"); k <- py("e1Indicateurs"); a <- py("e1Adossement")
  reconcile("e1ReconciliationPythonR", c("taux 10 ans avec VA", "taux 30 ans avec VA", "taux garanti moyen", "PVL obligataires", "duration passif", "duration obligations"),
            c(c1$tauxAvecVa[c(10, 30)], k$valeur[3], k$valeur[6], a$duration[1:2]), c(cv$tauxAvecVa[c(10, 30)], pf$kpi$valeur[1:4])) }
if (etape >= 2) { e <- runEsg(cv); if (hasPy) { m <- py("e2TestsMartingale")
  reconcile("e2ReconciliationPythonR", c(paste("d\u00e9flateur moyen", m$horizon), paste("martingale actions", m$horizon)), c(m$moyenneDeflateur, m$martingaleActions), c(e$mart$moyenneDeflateur, e$mart$martingaleActions)) } }
if (etape >= 3) { pr <- runProjection(e, pf, cv); if (hasPy) { p3 <- py("e3ProjectionEquivalentCertain"); s3 <- py("e3ProjectionStochastique")
  reconcile("e3ReconciliationPythonR", c(paste("taux servi EC ann\u00e9e", 1:10), paste("taux servi moyen stochastique ann\u00e9e", 1:10)),
            c(p3$tauxServi[1:10], s3$tauxServiMoyen[1:10]), c(pr$ce$tauxServi[1, 1:10], colMeans(pr$st$tauxServi[, 1:10]))) } }
if (etape >= 4) { v <- runValuation(e, pr, pf); if (hasPy) { p4 <- py("e4Valorisation"); g <- function(x) p4$montant[p4$poste == x]
  reconcile("e4ReconciliationPythonR", c("actifs", "BE stochastique", "BE \u00e9quivalent certain", "TVOG actionnaires", "BE garanti", "PVFP", "imp\u00f4ts", "fuite"),
            c(g("Valeur de march\u00e9 des actifs"), g("Best estimate stochastique"), g("Best estimate \u00e9quivalent certain"), g("TVOG, vision actionnaires (PVFP \u00e9quivalent certain - PVFP stochastique)"),
              g("BE des prestations garanties"), g("PVFP stochastique"), g("Imp\u00f4ts actualis\u00e9s (stochastique)"), g("\u00c9cart du test de fuite (moyenne)")), v$montant[c(1:5, 7:9)]) } }
if (etape >= 5) { s <- runSteering(e, pf, cv); if (hasPy) { p5 <- py("e5ScrMarcheAlm"); g5 <- py("e5AllocationStrategique")
  reconcile("e5ReconciliationPythonR", c(p5$choc, paste("SCR allocation", g5$actions, g5$immobilier)), c(p5$perteValeurNette, g5$scrMarche), c(s$scrTab$perteValeurNette, s$grid$scrMarche)) } }
