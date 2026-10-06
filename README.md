<<<<<<< HEAD
# Projet ALM : fonds en euros d'un assureur vie

Gestion actif-passif complète d'un fonds en euros de 1 milliard d'euros, en **Python** et en **R** (double implémentation réconciliée à la précision machine).

| Étape | Contenu | Résultats clés au 30/06/2026 |
|---|---|---|
| 1. Fondations | Courbe EIOPA, model points (taux garantis jusqu'à 3,5 %), actifs, bilan social, adossement | Écart de duration -3,5 ans ; moins-values obligataires -78,8 M€ |
| 2. Générateur de scénarios | Hull-White calé sur la courbe EIOPA, actions, immobilier, 1 000 scénarios, tests de martingale | Martingales vérifiées |
| 3. Modèle de projection | Comptabilité française, participation aux bénéfices, PPE (8 ans), réserve de capitalisation, rachats conjoncturels ACPR | PPE épuisée en 5 ans en équivalent certain |
| 4. Valorisation | Best estimate stochastique, TVOG, FDB, PVFP, test de fuite, convergence | BE 980 M€ ; FDB 216 M€ ; fuite 0,02 % |
| 5. Pilotage | SCR de marché par le modèle ALM, stress tests, liquidité, allocation stratégique | SCR de marché 47,5 M€ ; 47 % des chocs absorbés |

```bash
pip install -r requirements.txt
cd python && python main.py        # étapes 1 à 5 (environ 3 minutes)
cd .. && Rscript R/main.R          # version R et réconciliation (environ 15 minutes)
```

Organisation :
- `python/alm/` : package Python.
- `R/` : version R.
- `data/raw/` : données et provenance.
- `docs/notesMethodologiques/` : notes par étape.
- `docs/fichesRevisionWord/` : fiches Word et compilation.
- `outputs/` : résultats et réconciliation Python / R.
=======
# ALM
ALM_Project
>>>>>>> ad1ee7e61a47c53ff589396fc59e4be6c5141095
