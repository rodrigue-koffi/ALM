"""
config.py : hypothèses du projet ALM (fonds en euros d'un assureur vie français). Convention camelCase.
Deux familles : paramètres RÉGLEMENTAIRES ou DE PLACE (sourcés dans data/raw/sourcesDonnees.md) et hypothèses de
l'organisme (générées, modifiables ici).
"""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
dataRaw, dataProc = root / "data" / "raw", root / "data" / "processed"
outFig, outTab = root / "outputs" / "python" / "figures", root / "outputs" / "python" / "tables"
for p in (dataProc, outFig, outTab):
    p.mkdir(parents=True, exist_ok=True)
seed = 20260630

# ---------------- marché ----------------
valuationDate = "2026-06-30"
ufr, llp, convergencePeriod, convergenceTolerance, alphaMin, maxMaturity = 0.033, 20, 40, 1e-4, 0.05, 150

# ---------------- passif : fonds en euros ----------------
totalReserves = 1.0e9                 # provisions mathématiques (PM) : 1 milliard d'euros
loadingOnReserves = 0.0063            # chargement sur encours (ACPR 2025 : 0,63 %)
expenseOnReserves = 0.0035            # frais de gestion réels (% des PM)
expenseInflation = 0.02
marketRate2025 = 0.0263               # taux moyen servi 2025 (ACPR)
ppeInitialPct = 0.040                 # PPB / PPE à 4,0 % des PM (ACPR fin 2025)
capitalisationReservePct = 0.015      # réserve de capitalisation
socialEquityPct = 0.065               # fonds propres sociaux (% des PM)
structuralLapse = {"avant8Ans": 0.030, "a8Ans": 0.090, "apres8Ans": 0.055}   # rachats structurels par ancienneté fiscale
dynamicLapse = {"plafond": {"alpha": -0.06, "beta": -0.02, "gamma": 0.01, "delta": 0.02, "rcMin": -0.06, "rcMax": 0.40},
                "plancher": {"alpha": -0.04, "beta": 0.0, "gamma": 0.01, "delta": 0.04, "rcMin": -0.04, "rcMax": 0.20}}   # ONC ACPR 2013
dynamicLapseWeight = 0.5              # moyenne des deux bornes de l'ACPR
competitorSmoothing = 0.5             # taux concurrent = lissage du taux 10 ans + marge
competitorMargin = 0.003
pbFinancial, pbTechnical = 0.85, 0.90 # participation aux bénéfices réglementaire (A132-11)
ppeMaxYears = 8
targetSpread = 0.0                    # taux servi cible = taux concurrent + écart
horizon = 50                          # années de projection

# ---------------- actif ----------------
targetAllocation = {"obligations": 0.76, "actions": 0.12, "immobilier": 0.07, "monetaire": 0.05}
newBondMaturity = 10
creditSpreadCorporate = 0.009
equityDividendYield, propertyRentYield = 0.030, 0.035

# ---------------- générateur de scénarios (étape 2) ----------------
nScenarios = 1000                     # dont moitié antithétiques
hwMeanReversion = 0.03                # hypothèse de place (swaptions euro)
hwVolatility = 0.0085                 # 85 pb de volatilité normale
equityVolatility, propertyVolatility = 0.18, 0.10
corrRateEquity, corrRateProperty, corrEquityProperty = 0.10, 0.05, 0.40

# ---------------- pilotage (étape 5) ----------------
equityShock, propertyShock = 0.39, 0.25
upShockMin = 0.01
