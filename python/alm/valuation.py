"""
valuation.py : ÉTAPE 4, valorisation économique « market-consistent » du fonds en euros.

  * BEST ESTIMATE = moyenne sur les 1 000 scénarios des flux versés aux assurés (prestations, frais, PM et PPE
    restituées à l'horizon), actualisés par les déflateurs du GSE ;
  * ÉQUIVALENT CERTAIN : même calcul sur le scénario sans volatilité ;
  * TVOG (valeur temps des options et garanties) : coût des garanties (taux minimum, rachats conjoncturels) qui
    n'apparaît qu'en présence de volatilité ; mesurée côté actionnaires (PVFP équivalent certain - PVFP stochastique,
    définition MCEV) et côté assurés (BE stochastique - BE équivalent certain) ;
  * FDB (prestations discrétionnaires futures) = BE total - BE des seules prestations garanties (taux minimum, sans
    participation ni rachats conjoncturels) : la part du BE qui absorbe les pertes (capacité d'absorption des provisions) ;
  * PVFP (valeur actuelle des profits futurs des actionnaires) et impôts ;
  * TEST DE FUITE : valeur de marché des actifs = BE + PVFP + impôts actualisés ; tout écart signale une création ou
    une perte de valeur dans le modèle ;
  * CONVERGENCE : BE et intervalle de confiance selon le nombre de scénarios.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import config as C
from .esg import certaintyEquivalent
from .almModel import project, valuation
from .projection import loadAll
from .utils import log, banner, saveTable, saveFig


def run():
    banner("ÉTAPE 4 : VALORISATION ÉCONOMIQUE (BE, TVOG, FDB, PVFP, TEST DE FUITE)")
    cur, hw, sc, mp, b, o = loadAll()
    st = project(sc, hw, mp, b, o); vs = valuation(st, sc)
    hw0, sc0 = certaintyEquivalent(cur.tauxAvecVa.values)
    ce = project(sc0, hw0, mp, b, o); vc = valuation(ce, sc0)
    gu = project(sc, hw, mp, b, o, guaranteedOnly=True); vg = valuation(gu, sc)
    n = C.nScenarios
    be, beCe, beG = vs["be"].mean(), vc["be"][0], vg["be"].mean()
    tab = pd.DataFrame([
        ("Valeur de marché des actifs", st["mv0"][0]), ("Best estimate stochastique", be), ("Best estimate équivalent certain", beCe),
        ("Écart BE stochastique - BE équivalent certain (vision assurés)", be - beCe),
        ("TVOG, vision actionnaires (PVFP équivalent certain - PVFP stochastique)", vc["pvfp"][0] - vs["pvfp"].mean()), ("BE des prestations garanties", beG), ("FDB (prestations discrétionnaires futures)", be - beG),
        ("PVFP stochastique", vs["pvfp"].mean()), ("PVFP équivalent certain", vc["pvfp"][0]), ("Impôts actualisés (stochastique)", vs["impots"].mean()), ("Impôts actualisés (équivalent certain)", vc["impots"][0]),
        ("Écart du test de fuite (moyenne)", vs["fuite"].mean()), ("Écart du test de fuite (en % des actifs)", vs["fuite"].mean() / st["mv0"][0]),
        ("Erreur standard du BE", vs["be"].std() / np.sqrt(n)), ("Provisions sociales (PM + PPE)", C.totalReserves * (1 + C.ppeInitialPct))], columns=["poste", "montant"])
    conv = []
    for k in (50, 100, 200, 400, 600, 800, 1000):
        idx = np.r_[0:k // 2, n // 2:n // 2 + k // 2]                     # paires antithétiques conservées
        x = vs["be"][idx]
        conv.append({"nombreScenarios": k, "be": x.mean(), "erreurStandard": x.std() / np.sqrt(k), "fuiteMoyenne": vs["fuite"][idx].mean()})
    conv = pd.DataFrame(conv)
    saveTable(tab, "e4Valorisation"); saveTable(conv, "e4Convergence")
    pd.DataFrame({"be": vs["be"], "pvfp": vs["pvfp"], "impots": vs["impots"], "fuite": vs["fuite"]}).to_csv(C.dataProc / "valorisationParScenario.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    labels = ["BE garanti", "FDB", "BE total", "PVFP", "Impôts", "Actifs"]
    vals = [beG, be - beG, be, vs["pvfp"].mean(), vs["impots"].mean(), st["mv0"][0]]
    axes[0].bar(labels, np.array(vals) / 1e6, color=["#1f3b73", "#3e95cd", "#1f3b73", "#2a9d8f", "#6c757d", "#c8102e"])
    axes[0].set_title("Décomposition de la valeur des actifs (M€)"); axes[0].tick_params(axis="x", rotation=20)
    axes[1].hist(vs["be"] / 1e6, bins=40, color="#1f3b73", alpha=.8); axes[1].axvline(beCe / 1e6, color="#c8102e", ls="--", label="équivalent certain")
    axes[1].axvline(be / 1e6, color="k", label="moyenne"); axes[1].legend(); axes[1].set_title(f"BE par scénario (M€) ; TVOG actionnaires {(vc['pvfp'][0] - vs['pvfp'].mean()) / 1e6:.1f} M€")
    axes[2].errorbar(conv.nombreScenarios, conv.be / 1e6, yerr=1.96 * conv.erreurStandard / 1e6, fmt="o-", color="#1f3b73")
    axes[2].set_title("Convergence du BE (intervalle à 95 %)"); axes[2].set_xlabel("nombre de scénarios")
    saveFig(fig, "e4Valorisation")
    log.info("\n%s\n%s", tab.round(4).to_string(index=False), conv.round(0).to_string(index=False))
    return tab
