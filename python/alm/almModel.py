"""
almModel.py : ÉTAPE 3, modèle ALM de projection d'un fonds en euros (moteur vectorisé sur les scénarios).

Chaque année, pour chaque scénario :
  1. RÉÉQUILIBRAGE de l'actif vers l'allocation cible (plus-values réalisées sur actions et immobilier en résultat ;
     plus ou moins-values obligataires vers la réserve de capitalisation, comme en normes françaises) ;
  2. REVENUS : coupons, remboursements, dividendes, loyers, intérêts monétaires ; pertes de crédit (au taux du spread,
     ce qui rend la valorisation cohérente avec le marché) ;
  3. PRESTATIONS : décès (TH/TF 00-02), rachats structurels (selon l'ancienneté fiscale) et CONJONCTURELS (fonction
     ACPR de l'écart entre le taux servi l'an passé et le taux concurrent) ; les sortants reçoivent leur PM
     revalorisée au taux garanti ;
  4. RÉSULTAT TECHNIQUE : chargements sur encours (0,63 %) moins frais (0,35 % inflatés) ;
  5. PARTICIPATION AUX BÉNÉFICES : minimum réglementaire = 85 % du résultat financier + 90 % du résultat technique ;
     taux servi cible = taux concurrent ; si le minimum ne suffit pas : reprise de PPE, puis réalisation de
     plus-values latentes actions, puis renoncement de l'assureur à sa marge financière ; si le minimum dépasse la
     cible : dotation de la PPE ; toute dotation doit être distribuée sous 8 ans (règle FIFO) ; les contrats reçoivent
     au moins leur taux garanti (coût supporté par l'assureur) ;
  6. RÉSULTAT de l'assureur, impôt (25,83 %), distribution aux actionnaires.
À l'horizon (50 ans) : les PM et la PPE restantes reviennent aux assurés, le reste des actifs aux actionnaires.
Toutes les grandeurs sont conservées pour la valorisation (étape 4) : flux assurés, frais, impôts, flux actionnaires.
"""
import numpy as np
import pandas as pd
from . import config as C
from .portfolio import qx, structuralLapse

TAX = 0.2583
NB = 30


def dynamicLapse(gap):
    """Rachats conjoncturels (ONC ACPR) : moyenne des bornes haute et basse ; gap = taux servi - taux concurrent."""
    out = 0.0
    for key, w in (("plafond", C.dynamicLapseWeight), ("plancher", 1 - C.dynamicLapseWeight)):
        p = C.dynamicLapse[key]
        rc = np.where(gap < p["alpha"], p["rcMax"],
             np.where(gap < p["beta"], p["rcMax"] * (gap - p["beta"]) / (p["alpha"] - p["beta"]),
             np.where(gap <= p["gamma"], 0.0,
             np.where(gap <= p["delta"], p["rcMin"] * (gap - p["gamma"]) / (p["delta"] - p["gamma"]), p["rcMin"]))))
        out = out + w * rc
    return out


def initialBondBuckets(bonds, n):
    N, Cp, S = np.zeros(NB), np.zeros(NB), np.zeros(NB)
    for _, b in bonds.iterrows():
        k = int(b.maturiteResiduelle) - 1
        N[k] += b.nominal; Cp[k] += b.coupon * b.nominal; S[k] += b.spread * b.nominal
    S = np.divide(S, N, out=np.zeros(NB), where=N > 0)
    return np.tile(N, (n, 1)), np.tile(Cp, (n, 1)), np.tile(S, (n, 1))


def bondMarketValue(N, Cp, S, P):
    """P : (n, NB) prix zéro-coupon P(t, t+j), j = 1..NB."""
    mv = np.zeros(N.shape[0])
    for k in range(NB):
        if not N[:, k].any():
            continue
        j = np.arange(1, k + 2)
        surv = (1 - S[:, k:k + 1]) ** j[None, :]
        mv += Cp[:, k] * (P[:, :k + 1] * surv).sum(axis=1) + N[:, k] * P[:, k] * surv[:, -1]
    return mv


def solveServedRate(pm, tmg, amount, target):
    """Taux servi R tel que somme PM x max(tmg, R) = montant disponible, borné par la cible (bissection vectorisée)."""
    lo, hi = np.full(pm.shape[0], -0.05), np.maximum(target, 0.0) + 0.0
    need = lambda R: (pm * np.maximum(tmg[None, :], R[:, None])).sum(axis=1)
    ok = need(hi) <= amount + 1e-6
    for _ in range(40):
        mid = (lo + hi) / 2
        big = need(mid) > amount
        hi = np.where(big, mid, hi); lo = np.where(big, lo, mid)
    return np.where(ok, np.maximum(target, 0.0), lo)


def project(sc, hw, mp, bonds, other, allocation=None, shocks=None, H=C.horizon, guaranteedOnly=False, detail=False):
    """Projection ALM. sc : scénarios (r, D, equity, property) ; shocks : dict de chocs instantanés à t = 0."""
    from .esg import zeroRate
    allocation = allocation or C.targetAllocation
    shocks = shocks or {}
    n = sc["D"].shape[0]
    M = len(mp)
    pm = np.tile(mp.pm.values.astype(float), (n, 1)) * shocks.get("pmMult", 1.0)
    tmg = mp.tmg.values.astype(float)
    age = np.tile(mp.age.values.astype(float), (n, 1)); anc = np.tile(mp.anciennete.values.astype(float), (n, 1))
    isH = (mp.sexe.values == "H")
    N, Cp, S = initialBondBuckets(bonds, n)
    P0 = np.tile(hw.P(np.arange(1, NB + 1)), (n, 1))
    bondBook = N.sum(axis=1)
    eqMv = np.full(n, float(other.loc[other.classe == "actions", "valeurMarche"].iloc[0])) * (1 - shocks.get("equity", 0.0))
    eqBook = np.full(n, float(other.loc[other.classe == "actions", "valeurComptable"].iloc[0]))
    prMv = np.full(n, float(other.loc[other.classe == "immobilier", "valeurMarche"].iloc[0])) * (1 - shocks.get("property", 0.0))
    prBook = np.full(n, float(other.loc[other.classe == "immobilier", "valeurComptable"].iloc[0]))
    cash = np.full(n, float(other.loc[other.classe == "monetaire", "valeurMarche"].iloc[0]))
    rcRes = np.full(n, C.totalReserves * C.capitalisationReservePct)
    ppe = np.zeros((n, C.ppeMaxYears)); ppe[:, -1] = C.totalReserves * C.ppeInitialPct   # PPE initiale dans le seau le plus récent
    comp = np.full(n, C.marketRate2025); served = np.full(n, C.marketRate2025)
    mv0 = bondMarketValue(N, Cp, S, P0) + eqMv + prMv + cash
    out = {k: np.zeros((n, H)) for k in ("prestations", "frais", "impots", "dividendes", "tauxServi", "tauxConcurrent", "pm", "ppe", "rc",
                                         "resultat", "resultatFinancier", "pvl", "actifMarche", "rachatsTotaux", "tauxRachatConjoncturel", "chargements", "coutGarantie")}
    infl = 1.0
    for t in range(H):
        D0, D1 = sc["D"][:, t], sc["D"][:, t + 1]
        Pt = np.stack([hw.Ptr(t, t + j, sc["r"][:, t]) for j in range(1, NB + 1)], axis=1) if t > 0 else P0
        # ---- 1. rééquilibrage (début d'année) ----
        bondMv = bondMarketValue(N, Cp, S, Pt)
        total = bondMv + eqMv + prMv + cash
        realized = np.zeros(n)
        for mvName, bookName, w in (("eq", "eqB", allocation["actions"]), ("pr", "prB", allocation["immobilier"])):
            mvv = eqMv if mvName == "eq" else prMv
            bk = eqBook if mvName == "eq" else prBook
            tgt = w * total
            sell = np.maximum(mvv - tgt, 0.0); buy = np.maximum(tgt - mvv, 0.0)
            frac = np.divide(sell, mvv, out=np.zeros(n), where=mvv > 0)
            realized += frac * (mvv - bk)
            bk = bk * (1 - frac) + buy
            mvv = mvv - sell + buy
            cash = cash + sell - buy
            if mvName == "eq":
                eqMv, eqBook = mvv, bk
            else:
                prMv, prBook = mvv, bk
        tgtBond = allocation["obligations"] * total
        buyB = np.maximum(tgtBond - bondMv, 0.0); sellB = np.maximum(bondMv - tgtBond, 0.0)
        fracB = np.divide(sellB, bondMv, out=np.zeros(n), where=bondMv > 0)
        gainB = fracB * (bondMv - bondBook)
        N *= (1 - fracB)[:, None]; Cp *= (1 - fracB)[:, None]; bondBook *= (1 - fracB)
        rcRes = rcRes + np.where(gainB > 0, gainB, 0.0); lossB = np.where(gainB < 0, -gainB, 0.0)
        takeRc = np.minimum(lossB, rcRes); rcRes -= takeRc; realized -= (lossB - takeRc)
        cash = cash + sellB - buyB
        par = (1 - Pt[:, C.newBondMaturity - 1]) / Pt[:, :C.newBondMaturity].sum(axis=1)
        k = C.newBondMaturity - 1
        S[:, k] = np.divide(S[:, k] * N[:, k], N[:, k] + buyB, out=np.zeros(n), where=(N[:, k] + buyB) > 0)
        N[:, k] += buyB; Cp[:, k] += par * buyB; bondBook += buyB
        # ---- 2. revenus de l'année ----
        loss = (S * N).sum(axis=1)
        N *= (1 - S); Cp *= (1 - S); bondBook -= loss
        coupons = Cp.sum(axis=1); redemption = N[:, 0].copy()
        bondBook -= redemption
        N = np.concatenate([N[:, 1:], np.zeros((n, 1))], axis=1); Cp = np.concatenate([Cp[:, 1:], np.zeros((n, 1))], axis=1)
        S = np.concatenate([S[:, 1:], np.zeros((n, 1))], axis=1)
        gE, gP = sc["equity"][:, t + 1] / sc["equity"][:, t], sc["property"][:, t + 1] / sc["property"][:, t]
        eqMv = eqMv * gE; div = eqMv * C.equityDividendYield / (1 + C.equityDividendYield); eqMv -= div
        prMv = prMv * gP; rent = prMv * C.propertyRentYield / (1 + C.propertyRentYield); prMv -= rent
        cashInt = cash * (D0 / D1 - 1)
        cash = cash + cashInt + coupons + redemption + div + rent
        finRes = coupons + div + rent + cashInt + realized - loss
        # ---- 3. prestations ----
        q = np.where(isH[None, :], qx("H", age), qx("F", age))
        gap = served - comp
        dyn = 0.0 if guaranteedOnly else dynamicLapse(gap)
        lap = np.clip(structuralLapse(anc) + dyn[:, None] if not guaranteedOnly else structuralLapse(anc), 0.0, 1.0) * (1 - q)
        leavers = pm * (q + lap)
        benefits = (leavers * (1 + tmg[None, :])).sum(axis=1)
        pm = pm - leavers
        # ---- 4. résultat technique ----
        loadings = (pm * C.loadingOnReserves).sum(axis=1)
        expenses = (pm.sum(axis=1)) * C.expenseOnReserves * infl * shocks.get("expenseMult", 1.0)
        tech = loadings - expenses
        # ---- 5. participation aux bénéfices et taux servi ----
        interestLeavers = (leavers * tmg[None, :]).sum(axis=1)
        pmTot = pm.sum(axis=1)
        share = np.divide(pmTot, pmTot + rcRes + C.totalReserves * C.socialEquityPct, out=np.zeros(n), where=pmTot > 0)
        minPb = np.maximum(C.pbFinancial * finRes * share + C.pbTechnical * np.maximum(tech, 0) - interestLeavers, 0.0)
        forced = ppe[:, 0].copy(); ppe[:, 0] = 0.0                     # dotation de plus de 8 ans : distribution obligatoire
        comp = C.competitorSmoothing * comp + (1 - C.competitorSmoothing) * (zeroRate(hw, t, 10, sc["r"][:, t]) + C.competitorMargin)
        target = np.maximum(comp + C.targetSpread, 0.0)
        pmNet = pm * (1 - C.loadingOnReserves)                          # les chargements sont prélevés sur l'encours
        needTarget = (pmNet * np.maximum(tmg[None, :], target[:, None])).sum(axis=1)
        guaranteedCost = (pmNet * tmg[None, :]).sum(axis=1)
        avail = minPb + forced
        if guaranteedOnly:
            credited = guaranteedCost; dotPpe = np.zeros(n); repPpe = np.zeros(n); realizeExtra = np.zeros(n)
            ppe[:, :] = 0.0
        else:
            short = np.maximum(needTarget - avail, 0.0)
            ppeTot = ppe.sum(axis=1)
            repPpe = np.minimum(short, ppeTot)
            rem = repPpe.copy()
            for kk in range(C.ppeMaxYears):                             # reprise FIFO
                take = np.minimum(rem, ppe[:, kk]); ppe[:, kk] -= take; rem -= take
            short2 = short - repPpe
            pvlEq = np.maximum(eqMv - eqBook, 0.0)
            realizeExtra = np.minimum(pvlEq, short2 / C.pbFinancial)
            eqBook = eqBook + realizeExtra                                  # vente et rachat : la plus-value réalisée remonte la valeur comptable
            finRes = finRes + realizeExtra
            short3 = np.maximum(short2 - C.pbFinancial * realizeExtra, 0.0)
            margin = np.maximum((1 - C.pbFinancial) * finRes * share, 0.0)
            sacrifice = np.minimum(short3, margin)
            creditedPb = avail + repPpe + C.pbFinancial * realizeExtra + sacrifice
            dotPpe = np.maximum(creditedPb - np.maximum(needTarget, forced), 0.0)   # l'excédent est mis en réserve (PPE)
            creditedAmt = np.maximum(creditedPb - dotPpe, 0.0)
            credited = np.maximum(creditedAmt, guaranteedCost)
            ppe = np.concatenate([ppe[:, 1:], dotPpe[:, None]], axis=1)
        servedNew = solveServedRate(pmNet, tmg, credited, np.maximum(credited / np.maximum(pmNet.sum(axis=1), 1e-9) + 0.05, 0.0))
        rateMp = np.maximum(tmg[None, :], servedNew[:, None])
        pm = pmNet * (1 + rateMp)
        creditedTot = (pmNet * rateMp).sum(axis=1)
        funded = avail + repPpe + C.pbFinancial * realizeExtra + (sacrifice if not guaranteedOnly else 0.0)
        costGuarantee = np.maximum(creditedTot - funded, 0.0) if not guaranteedOnly else np.zeros(n)
        served = np.divide(creditedTot, pmNet.sum(axis=1), out=np.zeros(n), where=pmNet.sum(axis=1) > 0)
        # ---- 6. résultat, impôt, dividendes ----
        result = finRes + loadings - expenses - interestLeavers - creditedTot - (dotPpe - repPpe - forced)
        tax = TAX * np.maximum(result, 0.0)
        dividend = result - tax
        cash = cash - benefits - expenses - tax - dividend
        infl *= 1 + C.expenseInflation
        age += 1; anc += 1
        for key, v in (("prestations", benefits), ("frais", expenses), ("impots", tax), ("dividendes", dividend), ("tauxServi", served), ("tauxConcurrent", comp),
                       ("pm", pm.sum(axis=1)), ("ppe", ppe.sum(axis=1)), ("rc", rcRes), ("resultat", result), ("resultatFinancier", finRes),
                       ("pvl", bondMarketValue(N, Cp, S, np.stack([hw.Ptr(t + 1, t + 1 + j, sc["r"][:, t + 1]) for j in range(1, NB + 1)], axis=1)) - bondBook + eqMv - eqBook + prMv - prBook),
                       ("rachatsTotaux", leavers.sum(axis=1)), ("tauxRachatConjoncturel", dyn if not guaranteedOnly else np.zeros(n)),
                       ("chargements", loadings), ("coutGarantie", costGuarantee)):
            out[key][:, t] = v
        out["actifMarche"][:, t] = out["pvl"][:, t] + bondBook + eqBook + prBook + cash
    PH = np.stack([hw.Ptr(H, H + j, sc["r"][:, H]) for j in range(1, NB + 1)], axis=1)
    mvH = bondMarketValue(N, Cp, S, PH) + eqMv + prMv + cash
    out["terminalAssures"] = pm.sum(axis=1) + ppe.sum(axis=1)
    out["terminalActionnaires"] = mvH - out["terminalAssures"]
    out["mv0"] = mv0
    return out


def valuation(out, sc, H=C.horizon):
    D = sc["D"][:, 1:H + 1]
    be = (D * (out["prestations"] + out["frais"])).sum(axis=1) + sc["D"][:, H] * out["terminalAssures"]
    pvfp = (D * out["dividendes"]).sum(axis=1) + sc["D"][:, H] * out["terminalActionnaires"]
    tax = (D * out["impots"]).sum(axis=1)
    return {"be": be, "pvfp": pvfp, "impots": tax, "fuite": out["mv0"] - be - pvfp - tax}
