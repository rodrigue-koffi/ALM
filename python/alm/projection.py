"""
projection.py : ÉTAPE 3, résultats du modèle ALM de projection.

Deux lectures complémentaires :
  * le scénario ÉQUIVALENT CERTAIN (taux forward, actifs risqués au taux sans risque, aucune volatilité) : c'est le
    « compte de résultat prévisionnel » lisible année par année (taux servi, PPE, rachats, résultat) ;
  * les 1 000 scénarios stochastiques : distribution du taux servi, de la PPE, des rachats conjoncturels et du coût
    des garanties, qui n'apparaissent que lorsque les marchés s'écartent du central.
"""
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import config as C
from .esg import HullWhite, certaintyEquivalent
from .almModel import project
from .utils import log, banner, saveTable, saveFig


def loadAll():
    cur = pd.read_pickle(C.dataProc / "courbes.pkl")
    hw = HullWhite(cur.tauxAvecVa.values, C.hwMeanReversion, C.hwVolatility)
    sc = pickle.load(open(C.dataProc / "scenarios.pkl", "rb"))
    mp = pd.read_csv(C.dataRaw / "modelPoints.csv"); b = pd.read_csv(C.dataRaw / "actifsObligations.csv"); o = pd.read_csv(C.dataRaw / "actifsAutres.csv")
    return cur, hw, sc, mp, b, o


def run():
    banner("ÉTAPE 3 : MODÈLE ALM DE PROJECTION (ÉQUIVALENT CERTAIN ET STOCHASTIQUE)")
    cur, hw, sc, mp, b, o = loadAll()
    hw0, sc0 = certaintyEquivalent(cur.tauxAvecVa.values)
    ce = project(sc0, hw0, mp, b, o)
    st = project(sc, hw, mp, b, o)
    yrs = np.arange(1, C.horizon + 1)
    ceTab = pd.DataFrame({"annee": yrs, "pm": ce["pm"][0], "tauxServi": ce["tauxServi"][0], "tauxConcurrent": ce["tauxConcurrent"][0],
                          "ppe": ce["ppe"][0], "reserveCapitalisation": ce["rc"][0], "prestations": ce["prestations"][0], "resultatFinancier": ce["resultatFinancier"][0],
                          "resultat": ce["resultat"][0], "plusMoinsValuesLatentes": ce["pvl"][0]}).head(20)
    stTab = pd.DataFrame({"annee": yrs, "tauxServiMoyen": st["tauxServi"].mean(0), "tauxServiQ5": np.percentile(st["tauxServi"], 5, axis=0),
                          "tauxServiQ95": np.percentile(st["tauxServi"], 95, axis=0), "ppeMoyenne": st["ppe"].mean(0),
                          "rachatConjoncturelMoyen": st["tauxRachatConjoncturel"].mean(0), "probaRachatsMassifs": (st["tauxRachatConjoncturel"] > 0.10).mean(0),
                          "coutGarantieMoyen": st["coutGarantie"].mean(0), "probaServiAuMinimum": (st["coutGarantie"] > 0).mean(0),
                          "resultatMoyen": st["resultat"].mean(0), "probaPerte": (st["resultat"] < 0).mean(0)}).head(20)
    kpi = pd.DataFrame([{"indicateur": "taux servi moyen année 1 (équivalent certain)", "valeur": ce["tauxServi"][0, 0]},
                        {"indicateur": "taux servi moyen année 1 (stochastique)", "valeur": st["tauxServi"][:, 0].mean()},
                        {"indicateur": "PM restante à 10 ans (équivalent certain)", "valeur": ce["pm"][0, 9]},
                        {"indicateur": "durée de vie moyenne des PM (années, équivalent certain)", "valeur": float((np.concatenate([[C.totalReserves], ce["pm"][0]])[:-1]).sum() / C.totalReserves)},
                        {"indicateur": "probabilité de rachats conjoncturels > 10 % une année donnée (max sur 20 ans)", "valeur": stTab.probaRachatsMassifs.max()},
                        {"indicateur": "coût moyen actualisé des garanties (stochastique)", "valeur": float((sc["D"][:, 1:] * st["coutGarantie"]).sum(1).mean())}])
    saveTable(ceTab, "e3ProjectionEquivalentCertain"); saveTable(stTab, "e3ProjectionStochastique"); saveTable(kpi, "e3Indicateurs")
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    x = yrs[:30]
    for q, col in ((5, "#9fb3d9"), (50, "#1f3b73"), (95, "#9fb3d9")):
        axes[0].plot(x, np.percentile(st["tauxServi"], q, axis=0)[:30] * 100, color=col, lw=2 if q == 50 else 1)
    axes[0].plot(x, ce["tauxServi"][0, :30] * 100, "--", color="#c8102e", label="équivalent certain")
    axes[0].plot(x, ce["tauxConcurrent"][0, :30] * 100, ":", color="k", label="taux concurrent (EC)")
    axes[0].set_title("Taux servi : médiane, 5 %-95 % (stochastique)"); axes[0].legend(fontsize=8)
    axes[1].plot(x, ce["pm"][0, :30] / 1e6, color="#1f3b73", label="PM")
    axes[1].plot(x, ce["ppe"][0, :30] / 1e6 * 10, color="#e9a03b", label="PPE (x10)")
    axes[1].plot(x, st["pm"].mean(0)[:30] / 1e6, "--", color="#6c757d", label="PM moyenne stochastique")
    axes[1].set_title("Écoulement des provisions (M€)"); axes[1].legend(fontsize=8)
    axes[2].plot(x, stTab.probaServiAuMinimum.values[:20].tolist() + [np.nan] * 10, color="#c8102e", label="proba. de servir au minimum garanti")
    axes[2].plot(x, stTab.probaPerte.values[:20].tolist() + [np.nan] * 10, color="#1f3b73", label="proba. de perte comptable")
    axes[2].plot(x, stTab.probaRachatsMassifs.values[:20].tolist() + [np.nan] * 10, color="#2a9d8f", label="proba. de rachats conjoncturels > 10 %")
    axes[2].set_title("Risques ALM par année (stochastique)"); axes[2].legend(fontsize=8)
    saveFig(fig, "e3ProjectionAlm")
    log.info("\n%s\n%s\n%s", ceTab.head(10).round(4).to_string(index=False), stTab.head(10).round(4).to_string(index=False), kpi.round(4).to_string(index=False))
    return ce, st
