# Marvel Rivals Meta Pulse

> A full data engineering + ML pipeline analyzing hero and team-up performance across **12 seasons** of Marvel Rivals — built with Python, PostgreSQL, and scikit-learn.

---

## Table of Contents
- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Database Schema](#database-schema)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Key Findings](#key-findings)
  - [Hero Analysis](#hero-analysis)
  - [Team-Up Analysis](#team-up-analysis)
  - [ML Clustering](#ml-clustering)
  - [Win Rate Regression](#win-rate-regression)
  - [Dev Watch Flags](#dev-watch-flags)
- [Data Limitations](#data-limitations)
- [Updating for New Seasons](#updating-for-new-seasons)
- [Author](#author)

---

## Overview

Marvel Rivals Meta Pulse is an end-to-end data pipeline that scrapes competitive statistics from [rivalsmeta.com](https://rivalsmeta.com), stores them in a normalized PostgreSQL warehouse, runs 22 SQL analysis questions, and applies machine learning to cluster heroes, predict win rates, and flag balance intervention candidates.

**Coverage:** S0 through S6.5 (12 seasons, S5.5 excluded due to data integrity issues)

**Scale:**
| Table | Rows |
|---|---|
| `dim_hero` | 49 heroes |
| `dim_season` | 12 seasons |
| `fact_hero_stats` | 9,770 rows |
| `fact_teamup_stats` | 360 rows |

---

## Tech Stack

| Layer | Tools |
|---|---|
| Scraping | Python, Playwright (Chromium) |
| Storage | PostgreSQL 16, pgAdmin |
| Analysis | SQL (22 analytical queries) |
| ML | scikit-learn, pandas, matplotlib |
| Pipeline | SQLAlchemy, psycopg2 |

---

## Database Schema

```
dim_season          dim_hero
──────────          ────────
season_id (PK)      hero_id (PK)
season_label        hero_name
                    role (Vanguard / Duelist / Strategist)

fact_hero_stats                     fact_teamup_stats
───────────────                     ─────────────────
stat_id (PK)                        teamup_id (PK)
season_label                        season_label
mode (competitive / quickplay)      mode
rank (All Ranks → One Above All)    teamup (e.g. "Hela + Loki + Thor")
rank_num                            hero_count
hero_name                           tier
role                                win_rate
tier (S/A/B/C/D)                    pick_rate
tier_num                            matches
win_rate                            synergy_score
pick_rate
ban_rate
matches
win_rate_rank
```

---

## Project Structure

```
marvel-rivals-meta-pulse/
│
├── setup_db.py           # Run once — creates DB, tables, constraints
├── update_pipeline.py    # Run anytime — scrapes new seasons, upserts to DB
├── ml_analysis.py        # Clustering, regression, dev watch flags
│
├── analysis.sql          # All 22 SQL analytical queries
│
├── outputs/
│   ├── cluster_selection.png     # Elbow + silhouette plots
│   ├── hero_clusters_pca.png     # PCA cluster scatter (dark theme)
│   ├── feature_importance.png    # Random Forest feature importance
│   ├── regression_comparison.png # Model comparison bar chart
│   └── hero_ml_results.csv       # Full ML results per hero
│
└── README.md
```

---

## Getting Started

### Prerequisites
- Python 3.9+
- PostgreSQL 16+

### 1. Install dependencies
```bash
pip install playwright pandas sqlalchemy psycopg2-binary scikit-learn matplotlib nest_asyncio
playwright install chromium
```

### 2. Configure credentials
Open `setup_db.py` and `update_pipeline.py`. Update the config block at the top of each file:
```python
PG_USER     = "postgres"
PG_PASSWORD = "your_password"
PG_HOST     = "localhost"
PG_PORT     = "5432"
DB_NAME     = "marvel_rivals_meta"
```

### 3. Set up the database (first time only)
```bash
python setup_db.py
```
This creates the database, all 4 tables, and unique constraints required for upsert.

### 4. Scrape and load data
```bash
python update_pipeline.py
```
Auto-detects all seasons on rivalsmeta.com, compares with what's in your DB, scrapes only what's new, and upserts directly into PostgreSQL. Safe to re-run anytime.

### 5. Run ML analysis
```bash
python ml_analysis.py
```
Outputs clustering plots, regression comparison, feature importance chart, and `hero_ml_results.csv`.

---

## Key Findings

### Hero Analysis

**The most banned hero isn't the strongest one.**
Hawkeye holds the highest ban rate in the dataset at 43% — but his average win rate across all seasons sits at 48.1%, well below the S-tier threshold. This is a textbook case of reputation-based banning: players ban what they fear, not what the data says is strongest.

**Two heroes were genuinely broken, not just popular.**
Daredevil (54.4% avg win rate, 19.3% avg ban rate) and Elsa Bloodstone (51.4% avg win rate, 17.6% pick rate) sustained elite performance across multiple seasons rather than spiking in a single patch. High win rate with high banning — the community correctly identified them as threats.

**Peni Parker is a sleeper pick.**
Despite a 55.6% average win rate across tracked seasons (highest in the dataset), Peni Parker maintained a relatively low ban rate of 6%. She was winning consistently while flying under the community radar — the definition of an exploitable pick for informed players.

**Black Widow is in a class of her own — for the wrong reasons.**
40.2% average win rate across all 12 seasons. Never recovered. Never climbed above the bottom tier. KMeans clustering placed her as the sole member of the *Chronic Underperformer* cluster, statistically isolated from every other hero in the game.

**Pick rate and win rate are weakly correlated.**
Popular heroes consistently underperformed their expected win rate. The most-picked heroes were driven by kit feel and character appeal, not competitive strength. High familiarity leads to off-meta picks and suboptimal matchups, which drag win rates down — visible in the negative pick_rate coefficient (-0.115) in the regression model.

---

### Team-Up Analysis

**The best duo in recent meta: Peni Parker + Spider-Man**
63.71% win rate in S6.5, 63.04% in S6. Two consecutive seasons at the top. The highest sustained duo win rate in the dataset.

**The most reliable 3-hero combo ever: Hela + Loki + Thor**
Appeared in 4 top-10 seasonal rankings. 12 seasons of data, 60.06% average win rate. The backbone of the aggressive dive comp meta throughout the game's competitive history.

**3-hero combos outperform 2-hero combos on average.**
3-hero team-ups averaged 56.36% win rate vs 54.97% for 2-hero combos. However, only 2 unique 3-hero combinations exist in the dataset vs 29 two-hero combinations. The pool is small and elite — this comparison should be interpreted with caution.

**Most consistent team-up over time: Mantis + Loki**
6 seasons, 60.69% average win rate, with a narrow min–max range (58.84%–62.34%). Low variance, high floor — the mark of a genuinely reliable combo rather than a patch-dependent spike.

**Team-up mode data carries no differential signal.**
Win rates for competitive and quickplay modes in `fact_teamup_stats` are identical across all 360 rows. The scraper collected aggregate win rates and stored them under both mode labels. Mode is a dead dimension for team-up analysis — all team-up findings are based on aggregated data only.

---

### ML Clustering

Heroes were clustered using KMeans (k=5, selected by silhouette score) on 5 features: average win rate, pick rate, ban rate, tier number, and win rate standard deviation. PCA reduced to 2 dimensions for visualization (72.2% variance explained).

| Cluster | Heroes | Avg Win Rate | Avg Ban Rate | Avg Pick Rate | Defining Trait |
|---|---|---|---|---|---|
| Meta Tyrant | 13 | 52.42% | 1.60% | 11.13% | High tier, consistent winners, low fear-banning |
| Consistent Carry | 9 | 50.70% | 9.27% | 12.20% | Heavily banned because they reliably win |
| Niche Sleeper | 7 | 48.97% | 1.79% | 34.38% | Extremely popular, moderate win rate |
| Average Joe | 19 | 47.43% | 1.25% | 11.81% | Functional, unremarkable, bulk of the roster |
| Chronic Underperformer | 1 | 40.21% | 0.17% | 2.73% | Black Widow — statistically isolated |

**Notable cluster assignments:**

*Meta Tyrant:* Angela, Captain America, Elsa Bloodstone, Iron Fist, Loki, Magik, Mantis, Mister Fantastic, Peni Parker, Rogue, Storm, Thor, Ultron

*Consistent Carry:* Black Panther, Daredevil, Emma Frost, Groot, Hela, Hulk, Human Torch, Spider-Man, Wolverine

*Niche Sleeper:* Cloak & Dagger, Doctor Strange, Gambit, Invisible Woman, Luna Snow, Magneto, Rocket Raccoon

The Consistent Carry cluster having the highest average ban rate (9.27%) is the most analytically interesting finding — these heroes earn their bans through sustained winning, not reputation. Contrast with Hawkeye (Average Joe, 1.9% ban rate relative to his fear reputation) — the data doesn't support the community's fear of him.

---

### Win Rate Regression

Three models were evaluated to predict hero average win rate from pick rate, ban rate, tier number, win rate standard deviation, seasons tracked, and teamup count. All models were evaluated using 5-fold cross-validation on the 49-hero aggregated dataset.

| Model | Avg R² (5-fold CV) | Std | Avg MAE |
|---|---|---|---|
| Linear Regression | 0.8126 | ±0.190 | 0.683% |
| Polynomial Regression (deg=2) | **0.8209** | ±0.163 | **0.674%** |
| Random Forest (max_depth=3) | 0.3961 | ±0.847 | 1.146% |

**Best model: Polynomial Regression (R²=0.82, MAE=0.67%)**

Random Forest underperformed due to dataset size — with n=49 heroes and 5-fold CV, each training fold contains ~39 samples. Even with depth constrained to 3, RF cannot generalize reliably at this scale.

**Key regression findings:**

- `tier_num` is the dominant predictor (RF importance: 0.86, LR coefficient: +4.46) — every tier level is worth ~4.5% win rate
- `pick_rate` has a negative coefficient (-0.115) — the overplay effect: popular heroes get picked into unfavorable matchups, suppressing win rates
- `ban_rate` has a negative coefficient (-0.064) — heavily banned heroes face more counterplay when they do appear
- `teamup_count` contributes zero signal to individual hero win rate prediction
- High fold variance (especially fold 2 consistently weaker) is attributable to Black Widow being an extreme outlier — unavoidable with n=49

---

### Dev Watch Flags

Heroes were flagged using rule-based logic applied to their aggregated stats. Flags represent balance intervention signals a developer team would realistically monitor.

**🟢 Buff Candidates — chronic underperformers**
| Hero | Avg Win Rate | Signal |
|---|---|---|
| Black Widow | 40.21% | 12 seasons below D-tier average. Sole Chronic Underperformer cluster member. |
| Deadpool (Duelist) | 43.87% | Consistently bottom-tier, almost never played. |

**⚪ Volatile — high win rate swing across seasons**
Peni Parker, Mantis, Thor, Black Panther, Mister Fantastic, Iron Fist, Ultron, Human Torch, Iron Man, Venom, Scarlet Witch, Moon Knight, Blade, Squirrel Girl — these heroes are patch-dependent. Strong when tuned, weak otherwise. Devs likely have no stable baseline for them.

**🟡 Rework Signal — popular but underperforming**
28 heroes flagged including Captain America, Elsa Bloodstone, Loki, Rogue, Spider-Man, Hela, Doctor Strange, Iron Man, Groot, Wolverine and others. Note: the pick_rate threshold for this flag (≥8%) is intentionally broad. The highest-priority rework candidates based on the gap between pick rate and win rate are:

| Hero | Pick Rate | Win Rate | Gap |
|---|---|---|---|
| Cloak & Dagger | 44.78% | 47.14% | Niche Sleeper — loved, not dominant |
| Invisible Woman | 39.98% | 48.05% | Niche Sleeper — loved, not dominant |
| Magneto | 31.48% | 48.23% | Niche Sleeper — loved, not dominant |
| Gambit | 38.43% | 49.60% | Niche Sleeper — popular, not winning |
| Doctor Strange | 25.96% | 49.94% | Popular, not winning |

**Note on missing flags:** No Nerf Candidates were flagged because the threshold requires avg_win_rate ≥ 60% sustained across all seasons — no hero meets this bar when averaged over 12 seasons. Heroes like Daredevil and Peni Parker appear broken in recent seasons but their historical averages are pulled down by earlier, weaker seasons. A season-weighted or recency-biased dev watch would surface these more accurately.

---

## Data Limitations

| Limitation | Detail |
|---|---|
| Mode data for team-ups | Win rates are identical for competitive and quickplay in `fact_teamup_stats`. Scraper collected aggregate data only. Mode is a non-functional dimension for team-up analysis. |
| S5.5 excluded | Removed from `fact_hero_stats` due to data integrity issues. |
| n=49 for ML | Hero-level ML operates on 49 data points. RF cross-validation is unreliable at this scale. Polynomial regression is preferred. |
| Dev Watch thresholds | Rule-based flags use fixed thresholds that don't account for recency. A hero broken in S6.5 may not flag if their earlier seasons were weak. |
| Synergy score formula | `(win_rate / 50) × log1p(matches) × pick_rate / 10` — engineered metric, not an official game statistic. |

---

## Updating for New Seasons

When a new season drops, run:
```bash
python update_pipeline.py
```

The pipeline will:
1. Connect to your DB and check existing seasons
2. Detect all seasons available on rivalsmeta.com
3. Scrape only the new season(s)
4. Upsert heroes and team-ups into PostgreSQL
5. Automatically add any new heroes to `dim_hero`
6. Save a timestamped backup CSV

Then re-run the ML analysis:
```bash
python ml_analysis.py
```

**Adding a new hero to the role lookup:**
Open `update_pipeline.py` and add the hero to `ROLE_LOOKUP` (if Vanguard or Strategist) and `SLUG_TO_NAME` (for team-up parsing). Duelists are the default and require no entry.

---

## Author

**Rishi Agrawal**

- GitHub: [github.com/HarshRi30](https://github.com/HarshRi30)
- LinkedIn: [linkedin.com/in/rishi-agrawal30](https://linkedin.com/in/rishi-agrawal30)
- Email: rishiagra30@gmail.com

---

*Built as a data engineering project. Not affiliated with NetEase Games or Marvel.*
