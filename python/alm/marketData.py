"""
marketData.py : ÉTAPE 1.1, courbe des taux sans risque EIOPA au 30/06/2026 (Smith-Wilson, UFR 3,30 %, VA),
reprise du projet Solvabilité II (méthode validée à 0,34 pb sur le fichier officiel EIOPA 2021), et chocs de taux de
la formule standard. C'est la courbe d'actualisation du best estimate et la courbe initiale du générateur de scénarios.
"""
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from . import config as C
from .utils import log, banner, saveTable

mats = np.arange(1, C.maxMaturity + 1)


def wilson(t, u, alpha, omega):
    t, u = np.asarray(t, float)[:, None], np.asarray(u, float)[None, :]
    lo, hi = np.minimum(t, u), np.maximum(t, u)
    return np.exp(-omega * (t + u)) * (alpha * lo - 0.5 * np.exp(-alpha * hi) * (np.exp(alpha * lo) - np.exp(-alpha * lo)))


def smithWilson(liquidMat, liquidRates, ufr=C.ufr, alpha=None, out=mats):
    """Taux sans risque (composition annuelle) de 1 à 150 ans à partir de taux zéro-coupon liquides."""
    omega = np.log(1 + ufr)
    u = np.asarray(liquidMat, float)
    p = (1 + np.asarray(liquidRates, float)) ** -u

    def curve(a, t):
        zeta = np.linalg.solve(wilson(u, u, a, omega), p - np.exp(-omega * u))
        return np.exp(-omega * np.asarray(t, float)) + wilson(t, u, a, omega) @ zeta

    def gap(a):
        T = u.max() + C.convergencePeriod
        f = -(np.log(curve(a, [T + 0.001])[0]) - np.log(curve(a, [T - 0.001])[0])) / 0.002
        return abs(f - omega) - C.convergenceTolerance
    if alpha is None:
        alpha = C.alphaMin if gap(C.alphaMin) <= 0 else brentq(gap, C.alphaMin, 1.0)
    P = curve(alpha, out)
    return P ** (-1 / np.asarray(out, float)) - 1, alpha


def shockCurve(r, shocks, direction):
    s = shocks.set_index("maturite")
    fac = np.array([s.loc[m, "chocHausse" if direction == "up" else "chocBaisse"] if m <= 90 else 0.20 for m in mats[:len(r)]])
    if direction == "up":
        return r + np.maximum(r * fac, C.upShockMin)
    return np.where(r > 0, r * (1 - fac), r)



def run():
    banner("ÉTAPE 1.1 : COURBE EIOPA AU 30/06/2026")
    hist = pd.read_csv(C.dataRaw / "eiopaRfrFranceHistorique.csv")
    row = hist[hist.reference_date == C.valuationDate].iloc[0]
    pil = np.array([1, 5, 10, 20]); pr = row[["rate_1y", "rate_5y", "rate_10y", "rate_20y"]].values.astype(float)
    rNoVa, a1 = smithWilson(pil, pr)
    rVa, a2 = smithWilson(pil, pr + row.va)
    shocks = pd.read_csv(C.dataRaw / "eiopaChocsTauxFormuleStandard.csv")
    curves = pd.DataFrame({"maturite": mats, "tauxSansVa": rNoVa, "tauxAvecVa": rVa,
                           "tauxAvecVaChocHausse": shockCurve(rVa, shocks, "up"), "tauxAvecVaChocBaisse": shockCurve(rVa, shocks, "down")})
    curves.to_pickle(C.dataProc / "courbes.pkl")
    saveTable(curves.round(6), "e1CourbesEiopa")
    log.info("VA %.4f ; alpha %.4f / %.4f ; taux 1, 10, 30 ans avec VA : %s", row.va, a1, a2, curves.tauxAvecVa.values[[0, 9, 29]].round(4))
    return curves
