"""
main.py : orchestrateur du projet ALM (fonds en euros). Usage : cd python && python main.py [--etape N]
  1. Fondations : courbe EIOPA, model points, actifs, bilan social, adossement actif-passif
  2. Générateur de scénarios économiques risque-neutre (Hull-White, actions, immobilier) et tests de martingale
  3. Modèle ALM de projection (comptabilité française, participation aux bénéfices, PPE, réserve de capitalisation, rachats)
  4. Valorisation économique : best estimate stochastique, valeur temps des options et garanties, profits futurs, test de fuite
  5. Pilotage : SCR de marché par le modèle ALM, stress tests, liquidité, allocation stratégique
"""
import argparse
from alm import config as C
from alm.utils import banner, exportExcel
from alm import marketData, portfolio, esg, projection, valuation, steering


def etape1():
    banner("GRANDE ÉTAPE 1 : FONDATIONS")
    curves = marketData.run()
    portfolio.run(curves)


def etape2():
    banner("GRANDE ÉTAPE 2 : GÉNÉRATEUR DE SCÉNARIOS ÉCONOMIQUES")
    esg.run()


def etape3():
    banner("GRANDE ÉTAPE 3 : MODÈLE ALM DE PROJECTION")
    projection.run()


def etape4():
    banner("GRANDE ÉTAPE 4 : VALORISATION ÉCONOMIQUE")
    valuation.run()


def etape5():
    banner("GRANDE ÉTAPE 5 : PILOTAGE ALM")
    steering.run()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--etape", type=int, default=5); a = ap.parse_args()
    etape1()
    for k, f in ((2, etape2), (3, etape3), (4, etape4), (5, etape5)):
        if a.etape >= k:
            f()
    exportExcel(C.root / "outputs" / "python" / f"resultatsEtapes1a{a.etape}.xlsx")
