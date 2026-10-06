# Sources des données

| Fichier | Contenu | Source |
|---|---|---|
| `eiopaRfrFranceHistorique.csv` | Courbe des taux sans risque EIOPA (France, euro), points 1, 5, 10, 20, 30 ans et correction pour volatilité, 2023-2026 | EIOPA (copie github.com/SlimSaanouni/EIOPA_MONITORING) |
| `eiopaChocsTauxFormuleStandard.csv` | Chocs de taux de la formule standard (hausse, baisse) par maturité | Fichier officiel EIOPA du 31/12/2021 |
| `tableTH0002.csv`, `tableTF0002.csv` | Tables de mortalité réglementaires TH 00-02 et TF 00-02 | Réglementation française (copie github.com/mehdijac/mortables) |

Paramètres de place (publications officielles) :
- UFR 2026 de l'euro : 3,30 % (EIOPA).
- Taux moyen de revalorisation des fonds en euros en 2025 : 2,63 % ; provision pour participation aux bénéfices : 4,0 % des provisions des contrats individuels ; chargement de gestion moyen : 0,63 % de l'encours ; taux technique moyen : 0,32 % (ACPR, « Revalorisation 2025 », juin 2026).
- Durée de vie moyenne d'un contrat d'assurance vie : 12,8 ans (France Assureurs, 2026).
- Rachats conjoncturels : paramètres des Orientations nationales complémentaires de l'ACPR (2013), bornes haute et basse.
- Participation aux bénéfices réglementaire : 85 % du résultat financier et 90 % du résultat technique (Code des assurances, art. A132-11) ; provision pour participation aux excédents distribuée dans un délai de 8 ans.

Données générées : portefeuille de contrats (model points), portefeuille d'actifs, bilan social, volatilités du générateur de scénarios (hypothèses de place documentées dans la note de l'étape 2).
