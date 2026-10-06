"""
steering.py : ÉTAPE 5, pilotage actif-passif.

  1. SCR DE MARCHÉ PAR LE MODÈLE ALM (formule standard, revalorisation complète) : taux à la hausse et à la baisse
     (courbes EIOPA choquées, GSE recalibré sur la courbe choquée avec les mêmes tirages), actions -39 %, immobilier
     -25 % ; perte de valeur nette (actifs - BE) avec la capacité d'absorption des provisions (la participation future
     baisse) et, pour comparaison, sans elle (BE figé) ; agrégation par la matrice de marché.
  2. STRESS TESTS ALM (scénario équivalent certain choqué) : hausse durable des taux de 200 pb (rachats massifs,
     ventes forcées d'obligations en moins-value), baisse de 100 pb (coût du taux garanti), krach actions de 30 %.
  3. ALLOCATION STRATÉGIQUE (en univers risque-neutre : les actifs risqués n'y ont pas de prime de risque ; la
     comparaison porte donc sur la valeur et le risque, un GSE en probabilité réelle serait nécessaire pour les
     rendements espérés) : 15 allocations (actions 4 à 20 %, immobilier 4 à 10 %) comparées sur la valeur nette,
     le SCR de marché, le ratio valeur nette / SCR et le taux servi moyen espéré : frontière efficiente et recommandation.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import config as C
from .esg import HullWhite, simulate, certaintyEquivalent
from .almModel import project, valuation
from .projection import loadAll
from .utils import log, banner, saveTable, saveFig, aggregate


def navFor(Z, rates, mp, b, o, alloc=None, shocks=None, hwSigma=None):
    hw = HullWhite(rates, C.hwMeanReversion, C.hwVolatility if hwSigma is None else hwSigma)
    sc = simulate(hw, Z)
    out = project(sc, hw, mp, b, o, allocation=alloc, shocks=shocks)
    v = valuation(out, sc)
    return out["mv0"][0] - v["be"].mean(), v["be"].mean(), out


def marketScr(Z, cur, mp, b, o, alloc=None):
    va = cur.tauxAvecVa.values
    base, be0, out0 = navFor(Z, va, mp, b, o, alloc)
    res = {}
    for name, rates, sh in (("taux hausse", cur.tauxAvecVaChocHausse.values, None), ("taux baisse", cur.tauxAvecVaChocBaisse.values, None),
                            ("actions", va, {"equity": C.equityShock}), ("immobilier", va, {"property": C.propertyShock})):
        nav, be, _ = navFor(Z, rates, mp, b, o, alloc, sh)
        res[name] = {"perteNette": base - nav, "variationBe": be - be0}
    rate = max(res["taux hausse"]["perteNette"], res["taux baisse"]["perteNette"], 0)
    A = 0.0 if res["taux hausse"]["perteNette"] >= res["taux baisse"]["perteNette"] else 0.5
    M = np.array([[1, A, A], [A, 1, 0.75], [A, 0.75, 1]])
    scr = aggregate([rate, max(res["actions"]["perteNette"], 0), max(res["immobilier"]["perteNette"], 0)], M)
    return base, be0, res, scr, out0


def run():
    banner("ÉTAPE 5 : PILOTAGE ALM (SCR DE MARCHÉ, STRESS TESTS, ALLOCATION STRATÉGIQUE)")
    cur, hw, sc, mp, b, o = loadAll()
    Z = np.loadtxt(C.dataProc / "tiragesGaussiens.csv", delimiter=",").reshape(C.nScenarios, C.horizon, 4)
    base, be0, res, scr, out0 = marketScr(Z, cur, mp, b, o)
    mv0 = out0["mv0"][0]
    rows = []
    for k, v in res.items():
        shockAssets = {"taux hausse": None, "taux baisse": None, "actions": C.equityShock * float(o.loc[o.classe == "actions", "valeurMarche"].iloc[0]),
                       "immobilier": C.propertyShock * float(o.loc[o.classe == "immobilier", "valeurMarche"].iloc[0])}[k]
        rows.append({"choc": k, "perteValeurNette": v["perteNette"], "variationBe": v["variationBe"],
                     "perteSansAbsorptionDesProvisions": shockAssets if shockAssets is not None else np.nan,
                     "absorptionParLaParticipation": (shockAssets - v["perteNette"]) if shockAssets is not None else np.nan})
    scrTab = pd.DataFrame(rows)
    scrTab.loc[len(scrTab)] = ["SCR de marché agrégé (taux, actions, immobilier)", scr, np.nan, np.nan, np.nan]
    # ---------------- stress tests déterministes ----------------
    va = cur.tauxAvecVa.values
    stress = []
    for lab, rates, sh in (("central", va, None), ("hausse durable des taux +200 pb", va + 0.02, None), ("baisse durable des taux -100 pb", np.maximum(va - 0.01, -0.005), None),
                           ("krach actions -30 %", va, {"equity": 0.30})):
        hw0, sc0 = certaintyEquivalent(rates)
        out = project(sc0, hw0, mp, b, o, shocks=sh); v = valuation(out, sc0)
        stress.append({"scenario": lab, "tauxServiAn1": out["tauxServi"][0, 0], "tauxServiMoyen5Ans": out["tauxServi"][0, :5].mean(),
                       "rachatsAn1": out["rachatsTotaux"][0, 0], "rachatsMax5Ans": out["rachatsTotaux"][0, :5].max(), "rachatConjoncturelMax": out["tauxRachatConjoncturel"][0].max(),
                       "resultatCumule5Ans": out["resultat"][0, :5].sum(), "ppeFinAn3": out["ppe"][0, 2], "valeurNette": out["mv0"][0] - v["be"][0],
                       "plusMoinsValuesLatentesAn1": out["pvl"][0, 0]})
    stress = pd.DataFrame(stress)
    liq = stress[["scenario", "rachatsMax5Ans"]].copy()
    liq["actifsLiquidesDisponibles"] = float(o.loc[o.classe == "monetaire", "valeurMarche"].iloc[0]) + (b.maturiteResiduelle <= 1).sum() * b.nominal.iloc[0]
    liq["couvertureParLesActifsLiquides"] = liq.actifsLiquidesDisponibles / liq.rachatsMax5Ans
    liq["ventesObligationsNecessaires"] = np.maximum(liq.rachatsMax5Ans - liq.actifsLiquidesDisponibles, 0)
    # ---------------- allocation stratégique ----------------
    grid = []
    for eq in (0.04, 0.08, 0.12, 0.16, 0.20):
        for pr in (0.04, 0.07, 0.10):
            alloc = {"obligations": 1 - 0.05 - eq - pr, "actions": eq, "immobilier": pr, "monetaire": 0.05}
            nav, be, r_, s_, out = marketScr(Z, cur, mp, b, o, alloc)
            grid.append({"actions": eq, "immobilier": pr, "valeurNette": nav, "scrMarche": s_, "ratioValeurNetteSurScr": nav / s_,
                         "tauxServiMoyen10Ans": out["tauxServi"][:, :10].mean(), "tauxServiQ5Min10Ans": np.percentile(out["tauxServi"][:, :10].min(axis=1), 5)})
    grid = pd.DataFrame(grid)
    cand = grid[grid.ratioValeurNetteSurScr >= grid.ratioValeurNetteSurScr.quantile(0.5)]
    best = cand.loc[cand.tauxServiMoyen10Ans.idxmax()]
    reco = pd.DataFrame([{"allocationActuelle": "actions 12 %, immobilier 7 %", "recommandee": f"actions {best.actions:.0%}, immobilier {best.immobilier:.0%}",
                          "valeurNette": best.valeurNette, "scrMarche": best.scrMarche, "ratio": best.ratioValeurNetteSurScr, "tauxServiMoyen10Ans": best.tauxServiMoyen10Ans}])
    for nme, df in (("e5ScrMarcheAlm", scrTab), ("e5StressTests", stress), ("e5Liquidite", liq), ("e5AllocationStrategique", grid), ("e5Recommandation", reco)):
        saveTable(df, nme)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    s4 = scrTab.iloc[:4]
    axes[0].bar(s4.choc, s4.perteValeurNette / 1e6, color="#1f3b73", label="perte de valeur nette (avec absorption)")
    axes[0].bar(s4.choc, s4.perteSansAbsorptionDesProvisions.fillna(0) / 1e6, color="none", edgecolor="#c8102e", lw=2, label="choc brut sur les actifs")
    axes[0].axhline(0, color="k", lw=.6); axes[0].legend(fontsize=7); axes[0].set_title(f"SCR de marché par le modèle ALM : {scr / 1e6:.1f} M€")
    axes[1].bar(stress.scenario.str.slice(0, 22), stress.tauxServiMoyen5Ans * 100, color=["#6c757d", "#c8102e", "#1f3b73", "#e9a03b"])
    axes[1].set_title("Stress tests : taux servi moyen sur 5 ans (%)"); axes[1].tick_params(axis="x", rotation=20, labelsize=8)
    sca = axes[2].scatter(grid.scrMarche / 1e6, grid.tauxServiMoyen10Ans * 100, c=grid.actions, cmap="viridis", s=60)
    axes[2].scatter([best.scrMarche / 1e6], [best.tauxServiMoyen10Ans * 100], s=200, facecolors="none", edgecolors="#c8102e", lw=2, label="recommandée")
    cur12 = grid[(grid.actions == 0.12) & (grid.immobilier == 0.07)].iloc[0]
    axes[2].scatter([cur12.scrMarche / 1e6], [cur12.tauxServiMoyen10Ans * 100], marker="x", s=120, color="k", label="actuelle")
    plt.colorbar(sca, ax=axes[2], label="part actions"); axes[2].legend(fontsize=8)
    axes[2].set_xlabel("SCR de marché (M€)"); axes[2].set_ylabel("taux servi moyen 10 ans (%)"); axes[2].set_title("Allocation stratégique : rendement contre risque")
    saveFig(fig, "e5PilotageAlm")
    log.info("\n%s\n%s\n%s\n%s", scrTab.round(0).to_string(index=False), stress.round(4).to_string(index=False), liq.round(0).to_string(index=False),
             grid.round(4).to_string(index=False) + "\n" + reco.round(4).to_string(index=False))
    return scr
