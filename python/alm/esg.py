"""
esg.py : ÉTAPE 2, générateur de scénarios économiques (GSE) risque-neutre.

POURQUOI : le fonds en euros contient des OPTIONS vendues aux assurés (taux minimum garanti, rachat à tout moment,
participation aux bénéfices). Leur coût dépend de la dispersion des scénarios futurs : un calcul sur un seul scénario
central l'ignore. Solvabilité II impose une valorisation « market-consistent » : moyenne, sous probabilité
risque-neutre, des flux actualisés par des DÉFLATEURS, sur des scénarios qui reproduisent les prix de marché.

Modèles (pas annuel, 50 ans, 1 000 scénarios dont 500 antithétiques) :
  * taux : Hull-White à un facteur calé EXACTEMENT sur la courbe EIOPA + VA du 30/06/2026 ; retour à la moyenne
    a = 3 %, volatilité normale 85 pb (hypothèses de place pour l'euro, faute de prix de swaptions dans les données) ;
    simulation EXACTE du taux court et de son intégrale (pas d'erreur de discrétisation) ;
  * actions : indice à rendement total, dérive égale au taux court, volatilité 18 % ;
  * immobilier : même principe, volatilité 10 % ;
  * corrélations : taux-actions 0,10, taux-immobilier 0,05, actions-immobilier 0,40.
Les tirages gaussiens sont enregistrés : la version R reconstruit exactement les mêmes scénarios.
Tests de validation (martingale) : E[déflateur(t)] = prix zéro-coupon du marché ; E[déflateur x indice] = 1 ;
E[déflateur(t) x P(t, t+10)] = P(0, t+10).
"""
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import config as C
from .utils import log, banner, saveTable, saveFig


class HullWhite:
    def __init__(self, rates, a, sigma):
        self.rates, self.a, self.s = np.asarray(rates, float), a, sigma

    def P(self, T):
        T = np.asarray(T, float)
        r = np.interp(np.maximum(T, 1.0), np.arange(1, len(self.rates) + 1), self.rates)
        return (1 + r) ** -T

    def fwd(self, t, h=1e-3):
        t = np.asarray(t, float)
        lo = np.maximum(t - h, 1e-6)
        return -(np.log(self.P(t + h)) - np.log(self.P(lo))) / (t + h - lo)

    def B(self, t, T):
        return (1 - np.exp(-self.a * (T - t))) / self.a

    def Ptr(self, t, T, r):
        """Prix en t du zéro-coupon d'échéance T sachant r(t) (vectorisé sur r)."""
        B = self.B(t, T)
        if t == 0:
            return self.P(T) * np.ones_like(r)
        lnA = np.log(self.P(T) / self.P(t)) + B * self.fwd(t) - self.s ** 2 / (4 * self.a) * (1 - np.exp(-2 * self.a * t)) * B ** 2
        return np.exp(lnA - B * r)

    def phi(self, t):
        return self.fwd(t) + self.s ** 2 / (2 * self.a ** 2) * (1 - np.exp(-self.a * t)) ** 2

    def intPhi(self, t):
        a, s = self.a, self.s
        t = np.asarray(t, float)
        return -np.log(self.P(np.maximum(t, 1e-9))) * (t > 0) + s ** 2 / (2 * a ** 2) * (t - 2 * (1 - np.exp(-a * t)) / a + (1 - np.exp(-2 * a * t)) / (2 * a))


def normals(n, H, rng):
    half = n // 2
    z = rng.standard_normal((half, H, 4))
    return np.concatenate([z, -z], axis=0)


def simulate(hw, Z, eqVol=None, prVol=None):
    """Z : (n, H, 4) gaussiens indépendants -> scénarios de taux, déflateurs, indices actions et immobilier."""
    n, H, _ = Z.shape
    a, s = hw.a, hw.s
    eqVol = C.equityVolatility if eqVol is None else eqVol
    prVol = C.propertyVolatility if prVol is None else prVol
    rho = np.array([[1, C.corrRateEquity, C.corrRateProperty], [C.corrRateEquity, 1, C.corrEquityProperty], [C.corrRateProperty, C.corrEquityProperty, 1]])
    L = np.linalg.cholesky(rho)
    x, ix = np.zeros(n), np.zeros(n)
    X, IX = [x.copy()], [ix.copy()]
    eq, pr = np.ones(n), np.ones(n)
    EQ, PR = [eq.copy()], [pr.copy()]
    e = np.exp(-a)
    vx = s ** 2 / (2 * a) * (1 - e ** 2)
    vI = s ** 2 / a ** 2 * (1 - 2 * (1 - e) / a + (1 - e ** 2) / (2 * a))
    cov = s ** 2 / (2 * a ** 2) * (1 - e) ** 2
    rhoXI = cov / np.sqrt(vx * vI)
    t = np.arange(H + 1)
    iphi = hw.intPhi(t)
    for k in range(H):
        zc = Z[:, k, [0, 2, 3]] @ L.T                      # taux, actions, immobilier corrélés
        z1, zI = zc[:, 0], Z[:, k, 1]
        mI = x * (1 - e) / a
        ixNew = ix + mI + np.sqrt(vI) * (rhoXI * z1 + np.sqrt(1 - rhoXI ** 2) * zI)
        xNew = x * e + np.sqrt(vx) * z1
        intR = (ixNew - ix) + (iphi[k + 1] - iphi[k])       # intégrale du taux court sur l'année
        eq = eq * np.exp(intR - eqVol ** 2 / 2 + eqVol * zc[:, 1])
        pr = pr * np.exp(intR - prVol ** 2 / 2 + prVol * zc[:, 2])
        x, ix = xNew, ixNew
        X.append(x.copy()); IX.append(ix.copy()); EQ.append(eq.copy()); PR.append(pr.copy())
    X, IX, EQ, PR = (np.array(v).T for v in (X, IX, EQ, PR))
    r = X + hw.phi(np.maximum(t, 1e-6))[None, :]
    D = np.exp(-(IX + iphi[None, :]))
    return {"r": r, "D": D, "equity": EQ, "property": PR}


def certaintyEquivalent(rates):
    """Scénario équivalent certain : taux forward, actifs risqués au taux sans risque, aucune volatilité."""
    hw0 = HullWhite(rates, C.hwMeanReversion, 1e-9)
    return hw0, simulate(hw0, np.zeros((1, C.horizon, 4)), 0.0, 0.0)


def zeroRate(hw, t, T, r):
    return hw.Ptr(t, t + T, r) ** (-1 / T) - 1


def run():
    banner("ÉTAPE 2 : GÉNÉRATEUR DE SCÉNARIOS ÉCONOMIQUES RISQUE-NEUTRE")
    curves = pd.read_pickle(C.dataProc / "courbes.pkl")
    hw = HullWhite(curves.tauxAvecVa.values, C.hwMeanReversion, C.hwVolatility)
    rng = np.random.default_rng(C.seed)
    Z = normals(C.nScenarios, C.horizon, rng)
    np.savetxt(C.dataProc / "tiragesGaussiens.csv", Z.reshape(C.nScenarios, -1), delimiter=",", fmt="%.10f")
    sc = simulate(hw, Z)
    with open(C.dataProc / "scenarios.pkl", "wb") as fh:
        pickle.dump(sc, fh)
    t = np.arange(C.horizon + 1)
    D, n = sc["D"], C.nScenarios
    mart = []
    for T in (1, 5, 10, 20, 30, 40, 50):
        dm, dse = D[:, T].mean(), D[:, T].std() / np.sqrt(n)
        eqm = (D[:, T] * sc["equity"][:, T]).mean(); prm = (D[:, T] * sc["property"][:, T]).mean()
        z10 = (D[:, T] * hw.Ptr(T, T + 10, sc["r"][:, T])).mean() if T + 10 <= 150 else np.nan
        mart.append({"horizon": T, "prixZcMarche": float(hw.P(T)), "moyenneDeflateur": dm, "ecartEnErreursStandard": (dm - hw.P(T)) / dse,
                     "martingaleActions": eqm, "martingaleImmobilier": prm, "zc10AnsDiffereMarche": float(hw.P(T + 10)), "zc10AnsDiffereSimule": z10})
    mart = pd.DataFrame(mart)
    r10 = np.array([zeroRate(hw, k, 10, sc["r"][:, k]) for k in t]).T
    dist = pd.DataFrame([{"horizon": k, "taux10AnsMoyen": r10[:, k].mean(), "quantile5": np.percentile(r10[:, k], 5), "quantile95": np.percentile(r10[:, k], 95),
                          "probabiliteTauxCourtNegatif": (sc["r"][:, k] < 0).mean()} for k in (1, 5, 10, 20, 30)])
    params = pd.DataFrame([{"parametre": "Hull-White : retour à la moyenne a", "valeur": C.hwMeanReversion}, {"parametre": "Hull-White : volatilité normale", "valeur": C.hwVolatility},
                           {"parametre": "volatilité normale implicite du taux 10 ans", "valeur": C.hwVolatility * (1 - np.exp(-10 * C.hwMeanReversion)) / (10 * C.hwMeanReversion)},
                           {"parametre": "volatilité actions", "valeur": C.equityVolatility}, {"parametre": "volatilité immobilier", "valeur": C.propertyVolatility},
                           {"parametre": "nombre de scénarios (dont antithétiques)", "valeur": n}])
    saveTable(mart, "e2TestsMartingale"); saveTable(dist, "e2DistributionTaux10Ans"); saveTable(params, "e2ParametresGse")
    np.save(C.dataProc / "taux10Ans.npy", r10)

    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    for q, col in ((5, "#9fb3d9"), (50, "#1f3b73"), (95, "#9fb3d9")):
        axes[0].plot(t, np.percentile(r10, q, axis=0) * 100, color=col, lw=2 if q == 50 else 1)
    for i in range(12):
        axes[0].plot(t, r10[i] * 100, lw=.4, alpha=.6)
    axes[0].set_title("Taux 10 ans simulés (médiane, 5 %, 95 %)"); axes[0].set_xlabel("années")
    axes[1].plot(t, hw.P(t), "k-", label="prix zéro-coupon EIOPA")
    axes[1].plot(t, D.mean(axis=0), "o", ms=3, color="#c8102e", label="moyenne des déflateurs")
    axes[1].plot(t, (D * sc["equity"]).mean(axis=0), color="#2a9d8f", label="déflateur x actions (doit valoir 1)")
    axes[1].set_title("Tests de martingale"); axes[1].legend(fontsize=8)
    axes[2].hist(np.log(sc["equity"][:, 10]), bins=50, color="#1f3b73", alpha=.6, label="actions")
    axes[2].hist(np.log(sc["property"][:, 10]), bins=50, color="#e9a03b", alpha=.6, label="immobilier")
    axes[2].set_title("Log-performance à 10 ans"); axes[2].legend()
    saveFig(fig, "e2GenerateurScenarios")
    log.info("\n%s\n%s\n%s", mart.round(5).to_string(index=False), dist.round(4).to_string(index=False), params.round(4).to_string(index=False))
    return hw, sc
