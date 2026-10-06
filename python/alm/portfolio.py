"""
portfolio.py : ÉTAPE 1.2, portefeuille de contrats (model points), actifs, bilan social et analyse de l'adossement.

  * PASSIF : fonds en euros de 1 milliard d'euros de provisions mathématiques, regroupé en MODEL POINTS (âge, sexe,
    ancienneté fiscale, taux minimum garanti). Les contrats anciens portent des taux garantis élevés (jusqu'à 3,5 %),
    les récents 0 % : c'est la source de l'option de taux vendue par l'assureur.
  * ACTIF : obligations achetées au pair entre 2014 et 2025 (coupons de l'époque, donc faibles pour 2016-2021),
    valorisées sur la courbe EIOPA + spread ; actions et immobilier en plus-values latentes ; monétaire.
  * BILAN SOCIAL : PM, provision pour participation aux excédents (PPE, 4 % des PM, niveau ACPR fin 2025), réserve de
    capitalisation, fonds propres.
  * ADOSSEMENT : flux garantis du passif (taux garanti seul, rachats structurels, décès) contre flux de l'actif :
    durations, convexités, écart de duration et sensibilité de la valeur nette à ±100 pb.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from . import config as C
from .utils import log, banner, saveTable, saveFig

TH = pd.read_csv(C.dataRaw / "tableTH0002.csv").set_index("age").qx
TF = pd.read_csv(C.dataRaw / "tableTF0002.csv").set_index("age").qx


def qx(sex, age):
    t = TH if sex == "H" else TF
    return np.minimum(np.interp(age, t.index.values, t.values), 1.0)


def structuralLapse(anc):
    anc = np.asarray(anc, float)
    return np.where(anc < 8, C.structuralLapse["avant8Ans"], np.where(anc < 9, C.structuralLapse["a8Ans"], C.structuralLapse["apres8Ans"]))


def modelPoints():
    ages = {35: 0.10, 45: 0.17, 55: 0.22, 65: 0.24, 75: 0.17, 85: 0.10}
    ancs = {2: (0.22, {0.0: 1.0}), 5: (0.20, {0.0: 1.0}), 8: (0.18, {0.0: 0.6, 0.005: 0.4}),
            12: (0.20, {0.005: 0.35, 0.01: 0.40, 0.015: 0.25}), 20: (0.20, {0.015: 0.35, 0.025: 0.35, 0.035: 0.30})}
    rows = []
    for a, wa in ages.items():
        for anc, (wn, tm) in ancs.items():
            if a - anc < 18:
                continue
            for tmg, wt in tm.items():
                for sex, ws in (("F", 0.55), ("H", 0.45)):
                    rows.append({"age": a, "sexe": sex, "anciennete": anc, "tmg": tmg, "poids": wa * wn * wt * ws})
    mp = pd.DataFrame(rows)
    mp["pm"] = mp.poids / mp.poids.sum() * C.totalReserves
    mp["nbContrats"] = (mp.pm / 40000).round()
    mp.insert(0, "modelPoint", [f"MP{i + 1:03d}" for i in range(len(mp))])
    return mp.drop(columns="poids")


def bondPortfolio(rng, rNoVa, bondBook):
    yld = {2014: 0.017, 2015: 0.009, 2016: 0.005, 2017: 0.008, 2018: 0.008, 2019: 0.003, 2020: 0.0025, 2021: 0.003,
           2022: 0.018, 2023: 0.030, 2024: 0.029, 2025: 0.032}
    rows = []
    n = 48
    for k in range(n):
        typ = "etat FR" if k % 2 == 0 else ("etat DE" if k % 8 == 1 else "entreprise")
        yr = int(rng.choice(list(yld)))
        orig = int(rng.choice([10, 12, 15, 20]))
        rem = orig - (2026 - yr)
        if rem < 1:
            rem = int(rng.integers(1, 4))
        sp = C.creditSpreadCorporate if typ == "entreprise" else (0.004 if typ == "etat FR" else 0.0)
        cpn = round(yld[yr] + sp, 4)
        rows.append({"ligne": f"OBL{k + 1:03d}", "type": typ, "anneeAchat": yr, "coupon": cpn, "maturiteResiduelle": rem, "spread": sp})
    b = pd.DataFrame(rows)
    b["nominal"] = bondBook / n
    b["valeurComptable"] = b.nominal
    b["valeurMarche"] = [bondValue(r, rNoVa) for _, r in b.iterrows()]
    return b


def bondCashflows(b):
    t = np.arange(1, int(b.maturiteResiduelle) + 1)
    cf = np.full(len(t), b.coupon * b.nominal); cf[-1] += b.nominal
    return t, cf


def bondValue(b, r, shift=0.0):
    t, cf = bondCashflows(b)
    return float((cf / (1 + r[t - 1] + b.spread + shift) ** t).sum())


def guaranteedLiabilityCashflows(mp, horizon=C.horizon):
    cf = np.zeros(horizon)
    for _, m in mp.iterrows():
        pm, age, anc = m.pm, m.age, m.anciennete
        for t in range(horizon):
            q = qx(m.sexe, age)
            lap = structuralLapse(anc) * (1 - q)
            out = pm * (q + lap) * (1 + m.tmg)
            cf[t] += out
            pm = pm * (1 - q - lap) * (1 + m.tmg)
            age += 1; anc += 1
    return cf


def run(curves):
    banner("ÉTAPE 1.2 : MODEL POINTS, ACTIFS, BILAN SOCIAL, ADOSSEMENT ACTIF-PASSIF")
    rng = np.random.default_rng(C.seed)
    rNoVa, rVa = curves.tauxSansVa.values, curves.tauxAvecVa.values
    mp = modelPoints()
    book = C.totalReserves * (1 + C.ppeInitialPct + C.capitalisationReservePct + C.socialEquityPct)
    al = C.targetAllocation
    bonds = bondPortfolio(rng, rNoVa, book * al["obligations"])
    other = pd.DataFrame([
        {"classe": "actions", "valeurComptable": book * al["actions"], "valeurMarche": book * al["actions"] * 1.25},
        {"classe": "immobilier", "valeurComptable": book * al["immobilier"], "valeurMarche": book * al["immobilier"] * 1.20},
        {"classe": "monetaire", "valeurComptable": book * al["monetaire"], "valeurMarche": book * al["monetaire"]}])
    mp.to_csv(C.dataRaw / "modelPoints.csv", index=False); bonds.to_csv(C.dataRaw / "actifsObligations.csv", index=False)
    other.to_csv(C.dataRaw / "actifsAutres.csv", index=False)
    social = pd.DataFrame([("Obligations", bonds.valeurComptable.sum(), bonds.valeurMarche.sum()),
                           ("Actions", *other.iloc[0, 1:].values), ("Immobilier", *other.iloc[1, 1:].values), ("Monétaire", *other.iloc[2, 1:].values)],
                          columns=["actif", "valeurComptable", "valeurMarche"])
    social["plusMoinsValuesLatentes"] = social.valeurMarche - social.valeurComptable
    social.loc[len(social)] = ["Total", social.valeurComptable.sum(), social.valeurMarche.sum(), social.plusMoinsValuesLatentes.sum()]
    passif = pd.DataFrame([("Provisions mathématiques", C.totalReserves), ("Provision pour participation aux excédents (PPE)", C.totalReserves * C.ppeInitialPct),
                           ("Réserve de capitalisation", C.totalReserves * C.capitalisationReservePct), ("Fonds propres", C.totalReserves * C.socialEquityPct)],
                          columns=["passif", "montant"])
    # ---------------- adossement ----------------
    lcf = guaranteedLiabilityCashflows(mp)
    t = np.arange(1, C.horizon + 1)
    acf = np.zeros(C.horizon)
    for _, b in bonds.iterrows():
        tt, cf = bondCashflows(b)
        acf[tt - 1] += cf
    def stats(cf, r):
        df = (1 + r[:len(cf)]) ** -t
        pv = (cf * df).sum(); dur = (t * cf * df).sum() / pv
        conv = (t * (t + 1) * cf * df / (1 + r[:len(cf)]) ** 2).sum() / pv
        return pv, dur, conv
    pvL, dL, cL = stats(lcf, rVa)
    pvA, dA, cA = stats(acf, rNoVa)
    sens = []
    for sh in (-0.01, 0.01):
        pA = sum(bondValue(b, rNoVa, sh) for _, b in bonds.iterrows())
        pL = (lcf * (1 + rVa[:C.horizon] + sh) ** -t).sum()
        sens.append({"choc": f"{sh * 1e4:+.0f} pb", "variationObligations": pA - bonds.valeurMarche.sum(), "variationPassifGaranti": pL - pvL,
                     "variationValeurNette": (pA - bonds.valeurMarche.sum()) - (pL - pvL)})
    gap = pd.DataFrame([{"element": "passif garanti (taux minimum, sans participation)", "valeurActuelle": pvL, "duration": dL, "convexite": cL},
                        {"element": "obligations", "valeurActuelle": pvA, "duration": dA, "convexite": cA},
                        {"element": "écart de duration (obligations x A/L - passif)", "valeurActuelle": np.nan, "duration": dA * pvA / pvL - dL, "convexite": np.nan}])
    tmgMix = mp.groupby("tmg").pm.sum() / C.totalReserves
    kpi = pd.DataFrame([{"indicateur": "provisions mathématiques", "valeur": mp.pm.sum()}, {"indicateur": "nombre de contrats", "valeur": mp.nbContrats.sum()},
                        {"indicateur": "taux garanti moyen pondéré", "valeur": (mp.pm * mp.tmg).sum() / mp.pm.sum()},
                        {"indicateur": "âge moyen pondéré", "valeur": (mp.pm * mp.age).sum() / mp.pm.sum()},
                        {"indicateur": "plus ou moins-values latentes totales", "valeur": social.plusMoinsValuesLatentes.iloc[-1]},
                        {"indicateur": "plus ou moins-values latentes obligataires", "valeur": social.plusMoinsValuesLatentes.iloc[0]},
                        *[{"indicateur": f"part des PM au taux garanti {k:.1%}", "valeur": v} for k, v in tmgMix.items()]])
    qual = pd.DataFrame([("PM des model points = PM cible", abs(mp.pm.sum() - C.totalReserves) < 1),
                         ("âges dans [18 ; 110]", bool(mp.age.between(18, 110).all())), ("maturités résiduelles positives", bool((bonds.maturiteResiduelle > 0).all())),
                         ("actif comptable = passif comptable", abs(social.valeurComptable.iloc[-1] - passif.montant.sum()) < 1)], columns=["controle", "valide"])
    for n, df in (("e1ModelPoints", mp), ("e1Obligations", bonds), ("e1BilanSocialActif", social), ("e1BilanSocialPassif", passif),
                  ("e1Adossement", gap), ("e1SensibiliteAdossement", sens := pd.DataFrame(sens)), ("e1Indicateurs", kpi), ("e1QualiteDonnees", qual)):
        saveTable(df, n)
    pd.DataFrame({"annee": t, "fluxPassifGaranti": lcf, "fluxObligations": acf}).to_csv(C.dataProc / "fluxAdossement.csv", index=False)
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.8))
    axes[0].bar(tmgMix.index * 100, tmgMix.values * 100, width=0.35, color="#1f3b73"); axes[0].set_xlabel("taux minimum garanti (%)")
    axes[0].set_title("Répartition des PM par taux garanti (%)")
    axes[1].bar(t[:30] - 0.2, lcf[:30] / 1e6, width=0.4, color="#c8102e", label="passif garanti")
    axes[1].bar(t[:30] + 0.2, acf[:30] / 1e6, width=0.4, color="#1f3b73", label="obligations")
    axes[1].set_title(f"Flux annuels (M€) ; duration passif {dL:.1f}, obligations {dA:.1f}"); axes[1].legend()
    x = np.arange(4)
    axes[2].bar(x - 0.2, social.valeurComptable[:4] / 1e6, width=0.4, color="#6c757d", label="comptable")
    axes[2].bar(x + 0.2, social.valeurMarche[:4] / 1e6, width=0.4, color="#2a9d8f", label="marché")
    axes[2].set_xticks(x); axes[2].set_xticklabels(social.actif[:4]); axes[2].legend(); axes[2].set_title("Actifs : valeur comptable et de marché (M€)")
    saveFig(fig, "e1PortefeuilleEtAdossement")
    log.info("\n%s\n%s\n%s\n%s\n%s", kpi.round(4).to_string(index=False), social.round(0).to_string(index=False), gap.round(3).to_string(index=False),
             sens.round(0).to_string(index=False), qual.to_string(index=False))
