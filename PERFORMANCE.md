# OmbleCavalier — Performance Tracking

Suivi des cotes Lichess avant/après les déploiements, pour valider l'impact des optimisations NNUE.

---

## Validation NNUE

Commande de vérification :
```bash
echo -e "uci\nquit" | .venv/bin/python src/OmbleCavalierPython/omblecavalier/engines/omble_cavalier.py 2>&1 | grep "eval="
echo -e "uci\nquit" | engines/omble_cavalier++ 2>&1 | grep "eval="
```

| Bot | Moteur | eval= | Confirmé le |
|-----|--------|-------|-------------|
| OmbleCavalier (Python) | `.py` script via lichess-bot | `eval=NNUE` | 2026-05-28 |
| OmbleCavalierPP (C++) | `engines/omble_cavalier++` | `eval=NNUE` | 2026-05-28 |

---

## Historique des cotes

### 2026-05-28 — Baseline avant déploiement des optimisations NNUE

Optimisations déployées dans ce release :
- **C++** : lazy accumulator (delta-only push, matérialisation on-demand), AVX2 FMA explicite dans `nnue_eval`, cache de `staticEval` (supprime un appel `nnue_eval` double par nœud)
- **Python** : sparse gather `w1_T[indices].sum()` (~30× moins d'ops pour la couche L1), `CUDAExecutionProvider` prioritaire sur Linux
- TT augmentée de 1M → 4M entrées (~96 MB)

| Bot | Lichess | Format | Cote | Parties | RD | Relevé le |
|-----|---------|--------|------|---------|-----|-----------|
| OmbleCavalier (Python) | [@OmbleCavalier](https://lichess.org/@/OmbleCavalier) | Bullet | 1865 | 618 | 46 | 2026-05-28 |
| OmbleCavalier (Python) | [@OmbleCavalier](https://lichess.org/@/OmbleCavalier) | Blitz | 1888 | 714 | 46 | 2026-05-28 |
| OmbleCavalier (Python) | [@OmbleCavalier](https://lichess.org/@/OmbleCavalier) | Rapid | 1764 | 19 | 161 | 2026-05-28 |
| OmbleCavalierPP (C++) | [@OmbleCavalierPP](https://lichess.org/@/OmbleCavalierPP) | Bullet | 2095 | 7761 | 45 | 2026-05-28 |
| OmbleCavalierPP (C++) | [@OmbleCavalierPP](https://lichess.org/@/OmbleCavalierPP) | Blitz | 2074 | 8056 | 45 | 2026-05-28 |
| OmbleCavalierPP (C++) | [@OmbleCavalierPP](https://lichess.org/@/OmbleCavalierPP) | Rapid | 1858 | 979 | 55 | 2026-05-28 |

> **Dernière activité** : OmbleCavalier vu le 2026-01-28 · OmbleCavalierPP vu le 2026-01-24.
> Les bots ont été inactifs depuis janvier 2026 — les cotes ci-dessus sont le point de référence.

---

<!-- ENTRIES FUTURES : copier le bloc ci-dessous après chaque déploiement significatif -->
<!--
### YYYY-MM-DD — Description du changement

| Bot | Format | Cote | Δ vs baseline | Parties | RD | Relevé le |
|-----|--------|------|--------------|---------|-----|-----------|
| OmbleCavalier (Python) | Bullet |  |  |  |  | YYYY-MM-DD |
| OmbleCavalier (Python) | Blitz  |  |  |  |  | YYYY-MM-DD |
| OmbleCavalierPP (C++)  | Bullet |  |  |  |  | YYYY-MM-DD |
| OmbleCavalierPP (C++)  | Blitz  |  |  |  |  | YYYY-MM-DD |
-->
