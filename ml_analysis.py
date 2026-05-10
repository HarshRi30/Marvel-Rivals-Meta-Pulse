"""
Marvel Rivals Meta Pulse — Stage 5: ML Analysis
================================================
1. Hero Clustering (KMeans + PCA visualization)
2. Win Rate Regression
3. Dev Watch Flags
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_error
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────
# CONFIG — update your credentials if needed
# ─────────────────────────────────────────────
DB_URL = "postgresql://postgres:7020@localhost:5432/Rivals"
engine = create_engine(DB_URL)

# ─────────────────────────────────────────────
# 1. LOAD & AGGREGATE DATA
# ─────────────────────────────────────────────
print("=" * 55)
print("LOADING DATA FROM POSTGRESQL")
print("=" * 55)

hero_stats = pd.read_sql("SELECT * FROM fact_hero_stats", engine)
teamup_stats = pd.read_sql("SELECT * FROM fact_teamup_stats", engine)
dim_hero = pd.read_sql("SELECT * FROM dim_hero", engine)

print(f"fact_hero_stats: {len(hero_stats)} rows")
print(f"fact_teamup_stats: {len(teamup_stats)} rows")
print(f"dim_hero: {len(dim_hero)} rows")

# Map tier to numeric
tier_map = {"S": 5, "A": 4, "B": 3, "C": 2, "D": 1}
hero_stats["tier_num"] = hero_stats["tier"].map(tier_map)

# Count how many team-ups each hero appears in
teamup_counts = pd.concat([
    teamup_stats["teamup"].str.split(" + ").explode()
]).value_counts().reset_index()
teamup_counts.columns = ["hero", "teamup_count"]

# Aggregate per hero across all seasons
agg = hero_stats.groupby("hero").agg(
    avg_win_rate    = ("win_rate",   "mean"),
    avg_pick_rate   = ("pick_rate",  "mean"),
    avg_ban_rate    = ("ban_rate",   "mean"),
    avg_tier_num    = ("tier_num",   "mean"),
    win_rate_std    = ("win_rate",   "std"),   # consistency signal
    seasons_tracked = ("season_label", "count"),
    max_win_rate    = ("win_rate",   "max"),
    min_win_rate    = ("win_rate",   "min"),
).reset_index()

# Fill std NaN (heroes with only 1 season)
agg["win_rate_std"] = agg["win_rate_std"].fillna(0)

# Merge teamup involvement
agg = agg.merge(teamup_counts, on="hero", how="left")
agg["teamup_count"] = agg["teamup_count"].fillna(0)

print(f"\nAggregated hero features: {agg.shape}")
print(agg[["hero", "avg_win_rate", "avg_ban_rate",
           "avg_tier_num", "seasons_tracked"]].head(10).to_string(index=False))


# ─────────────────────────────────────────────
# 2. CLUSTERING
# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("SECTION 1: HERO CLUSTERING")
print("=" * 55)

features = ["avg_win_rate", "avg_pick_rate", "avg_ban_rate",
            "avg_tier_num", "win_rate_std"]

X = agg[features].copy()
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Elbow + Silhouette to find best k
inertias, silhouettes = [], []
k_range = range(2, 9)

for k in k_range:
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    inertias.append(km.inertia_)
    silhouettes.append(silhouette_score(X_scaled, labels))

# Plot elbow + silhouette
fig, axes = plt.subplots(1, 2, figsize=(12, 4))
fig.suptitle("Elbow & Silhouette — Choosing Optimal k", fontsize=13, fontweight="bold")

axes[0].plot(k_range, inertias, marker="o", color="#e74c3c")
axes[0].set_xlabel("Number of Clusters (k)")
axes[0].set_ylabel("Inertia")
axes[0].set_title("Elbow Method")
axes[0].grid(alpha=0.3)

axes[1].plot(k_range, silhouettes, marker="o", color="#2ecc71")
axes[1].set_xlabel("Number of Clusters (k)")
axes[1].set_ylabel("Silhouette Score")
axes[1].set_title("Silhouette Score")
axes[1].grid(alpha=0.3)

best_k_idx = silhouettes.index(max(silhouettes))
best_k = list(k_range)[best_k_idx]
axes[1].axvline(x=best_k, color="orange", linestyle="--",
                label=f"Best k={best_k}")
axes[1].legend()

plt.tight_layout()
plt.savefig("cluster_selection.png", dpi=150, bbox_inches="tight")
plt.close()
print(f"\nBest k by silhouette: {best_k}")

# Final clustering
km_final = KMeans(n_clusters=best_k, random_state=42, n_init=10)
agg["cluster"] = km_final.fit_predict(X_scaled)

# Label clusters based on avg win rate of each cluster
cluster_profile = agg.groupby("cluster")["avg_win_rate"].mean().sort_values(ascending=False)

label_map_raw = {}
label_names   = ["Meta Tyrant", "Consistent Carry", "Niche Sleeper",
                 "Average Joe",  "Chronic Underperformer"]

for rank, (cluster_id, _) in enumerate(cluster_profile.items()):
    if rank < len(label_names):
        label_map_raw[cluster_id] = label_names[rank]
    else:
        label_map_raw[cluster_id] = f"Group {rank+1}"

agg["cluster_label"] = agg["cluster"].map(label_map_raw)

print("\nCluster Profiles:")
print(agg.groupby("cluster_label")[features].mean().round(2).to_string())

print("\nHeroes per cluster:")
for label in agg["cluster_label"].unique():
    heroes = agg[agg["cluster_label"] == label]["hero"].tolist()
    print(f"\n  [{label}] ({len(heroes)} heroes)")
    print("  " + ", ".join(sorted(heroes)))


# ─────────────────────────────────────────────
# 3. PCA VISUALIZATION
# ─────────────────────────────────────────────
pca = PCA(n_components=2, random_state=42)
X_pca = pca.fit_transform(X_scaled)
agg["pca_x"] = X_pca[:, 0]
agg["pca_y"] = X_pca[:, 1]

explained = pca.explained_variance_ratio_
print(f"\nPCA explained variance: PC1={explained[0]:.1%}, PC2={explained[1]:.1%}")

COLORS = ["#e74c3c", "#3498db", "#2ecc71", "#f39c12", "#9b59b6",
          "#1abc9c", "#e67e22", "#34495e"]

fig, ax = plt.subplots(figsize=(14, 9))
ax.set_facecolor("#1a1a2e")
fig.patch.set_facecolor("#1a1a2e")

for i, label in enumerate(agg["cluster_label"].unique()):
    mask = agg["cluster_label"] == label
    ax.scatter(
        agg.loc[mask, "pca_x"],
        agg.loc[mask, "pca_y"],
        c=COLORS[i % len(COLORS)],
        label=label,
        s=120,
        alpha=0.85,
        edgecolors="white",
        linewidths=0.5
    )

# Label hero names
for _, row in agg.iterrows():
    ax.annotate(
        row["hero"],
        (row["pca_x"], row["pca_y"]),
        fontsize=6.5,
        color="white",
        alpha=0.85,
        xytext=(4, 4),
        textcoords="offset points"
    )

ax.set_title(
    f"Marvel Rivals Hero Clustering (PCA)\n"
    f"PC1 {explained[0]:.1%} + PC2 {explained[1]:.1%} variance explained",
    color="white", fontsize=13, fontweight="bold"
)
ax.set_xlabel("PC1", color="white")
ax.set_ylabel("PC2", color="white")
ax.tick_params(colors="white")
ax.spines[:].set_color("#444")
ax.legend(
    facecolor="#2c2c54", edgecolor="#444",
    labelcolor="white", fontsize=9, loc="upper right"
)
ax.grid(alpha=0.15, color="white")

plt.tight_layout()
plt.savefig("hero_clusters_pca.png", dpi=150, bbox_inches="tight",
            facecolor="#1a1a2e")
plt.close()
print("Saved: hero_clusters_pca.png")


# ─────────────────────────────────────────────
# 2. WIN RATE REGRESSION (IMPROVED)
# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("SECTION 2: WIN RATE REGRESSION (IMPROVED)")
print("=" * 55)

from sklearn.preprocessing import PolynomialFeatures
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score

# Richer feature set — use aggregated hero-level data
reg_features = [
    "avg_pick_rate", "avg_ban_rate", "avg_tier_num",
    "win_rate_std", "seasons_tracked", "teamup_count"
]

X_reg = agg[reg_features].copy()
y_reg = agg["avg_win_rate"].copy()

# ── Linear Regression with cross-validation ──
lr = LinearRegression()
lr_cv_r2  = cross_val_score(lr, X_reg, y_reg, cv=5, scoring="r2")
lr_cv_mae = cross_val_score(lr, X_reg, y_reg, cv=5,
                            scoring="neg_mean_absolute_error")

lr.fit(X_reg, y_reg)
print(f"\nLinear Regression (5-fold CV):")
print(f"  R² per fold : {[round(x,4) for x in lr_cv_r2]}")
print(f"  Avg R²      : {lr_cv_r2.mean():.4f} ± {lr_cv_r2.std():.4f}")
print(f"  Avg MAE     : {(-lr_cv_mae).mean():.4f}")
print(f"\n  Coefficients:")
for feat, coef in zip(reg_features, lr.coef_):
    print(f"    {feat:20s}: {coef:.4f}")
print(f"  Intercept: {lr.intercept_:.4f}")

# ── Polynomial Regression (degree=2) ──
poly_pipe = Pipeline([
    ("poly", PolynomialFeatures(degree=2, include_bias=False)),
    ("scaler", StandardScaler()),
    ("lr", LinearRegression())
])
poly_cv_r2  = cross_val_score(poly_pipe, X_reg, y_reg, cv=5, scoring="r2")
poly_cv_mae = cross_val_score(poly_pipe, X_reg, y_reg, cv=5,
                              scoring="neg_mean_absolute_error")

print(f"\nPolynomial Regression degree=2 (5-fold CV):")
print(f"  R² per fold : {[round(x,4) for x in poly_cv_r2]}")
print(f"  Avg R²      : {poly_cv_r2.mean():.4f} ± {poly_cv_r2.std():.4f}")
print(f"  Avg MAE     : {(-poly_cv_mae).mean():.4f}")

# ── Random Forest with cross-validation ──
rf = RandomForestRegressor(n_estimators=100, max_depth=3,
                           random_state=42)
rf_cv_r2  = cross_val_score(rf, X_reg, y_reg, cv=5, scoring="r2")
rf_cv_mae = cross_val_score(rf, X_reg, y_reg, cv=5,
                            scoring="neg_mean_absolute_error")

rf.fit(X_reg, y_reg)
print(f"\nRandom Forest (5-fold CV, max_depth=3):")
print(f"  R² per fold : {[round(x,4) for x in rf_cv_r2]}")
print(f"  Avg R²      : {rf_cv_r2.mean():.4f} ± {rf_cv_r2.std():.4f}")
print(f"  Avg MAE     : {(-rf_cv_mae).mean():.4f}")
print(f"\n  Feature Importances:")
for feat, imp in zip(reg_features, rf.feature_importances_):
    print(f"    {feat:20s}: {imp:.4f}")

# ── Summary comparison plot ──
models  = ["Linear\nRegression", "Polynomial\nDeg-2", "Random Forest\n(depth=3)"]
r2_vals = [lr_cv_r2.mean(), poly_cv_r2.mean(), rf_cv_r2.mean()]
r2_std  = [lr_cv_r2.std(),  poly_cv_r2.std(),  rf_cv_r2.std()]
colors  = ["#3498db", "#9b59b6", "#2ecc71"]

fig, ax = plt.subplots(figsize=(8, 5))
bars = ax.bar(models, r2_vals, color=colors,
              yerr=r2_std, capsize=6, alpha=0.85)
ax.set_ylabel("Mean R² (5-fold CV)")
ax.set_title("Regression Model Comparison\n(Cross-Validated, Hero-Level Features)",
             fontweight="bold")
ax.set_ylim(0, 1.05)
ax.axhline(0.7, color="gray", linestyle="--", alpha=0.5, label="R²=0.7 baseline")
ax.bar_label(bars, labels=[f"{v:.3f}" for v in r2_vals],
             padding=6, fontsize=10)
ax.legend()
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("regression_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("\nSaved: regression_comparison.png")


# ─────────────────────────────────────────────
# 5. DEV WATCH FLAGS
# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("SECTION 3: DEV WATCH FLAGS")
print("=" * 55)

def dev_flag(row):
    wr  = row["avg_win_rate"]
    br  = row["avg_ban_rate"]
    pr  = row["avg_pick_rate"]
    std = row["win_rate_std"]
    tier = row["avg_tier_num"]

    flags = []

    # Nerf candidates
    if wr >= 60 and tier >= 4.5:
        flags.append("🔴 Nerf Candidate — elite win rate, top tier")
    elif wr >= 58 and br >= 20:
        flags.append("🔴 Nerf Watch — high win + heavy banning")

    # Buff candidates
    if wr < 49 and tier <= 2:
        flags.append("🟢 Buff Candidate — chronic underperformer")
    elif wr < 51 and pr < 2:
        flags.append("🟢 Buff Watch — low win + ignored by players")

    # Rework signals
    if pr >= 8 and wr < 52:
        flags.append("🟡 Rework Signal — popular but underperforming")

    # Fear-banned signal
    if br >= 30 and wr < 58:
        flags.append("🟠 Fear-Banned — reputation > actual stats")

    # Volatile / patch-dependent
    if std >= 3.5:
        flags.append("⚪ Volatile — win rate swings heavily by season")

    return " | ".join(flags) if flags else "✅ Stable — no intervention needed"

agg["dev_watch"] = agg.apply(dev_flag, axis=1)

dev_df = agg[["hero", "avg_win_rate", "avg_ban_rate",
              "avg_pick_rate", "avg_tier_num", "cluster_label",
              "dev_watch"]].sort_values("avg_win_rate", ascending=False)

print("\nDev Watch — Full Hero Table:")
print(dev_df.to_string(index=False))

flagged = dev_df[dev_df["dev_watch"] != "✅ Stable — no intervention needed"]
print(f"\n{len(flagged)} heroes flagged for dev attention:")
for _, row in flagged.iterrows():
    print(f"  {row['hero']:30s} | WR: {row['avg_win_rate']:.2f}% | {row['dev_watch']}")


# ─────────────────────────────────────────────
# 6. EXPORT RESULTS
# ─────────────────────────────────────────────
print("\n" + "=" * 55)
print("EXPORTING RESULTS")
print("=" * 55)

export_cols = [
    "hero", "avg_win_rate", "avg_pick_rate", "avg_ban_rate",
    "avg_tier_num", "win_rate_std", "seasons_tracked",
    "max_win_rate", "min_win_rate", "teamup_count",
    "cluster", "cluster_label", "pca_x", "pca_y", "dev_watch"
]

agg[export_cols].to_csv("hero_ml_results.csv", index=False)
print("Saved: hero_ml_results.csv")

print("\n" + "=" * 55)
print("ML ANALYSIS COMPLETE")
print("=" * 55)
print("Outputs:")
print("  cluster_selection.png   — elbow + silhouette plots")
print("  hero_clusters_pca.png   — PCA cluster scatter")
print("  feature_importance.png  — RF feature importance")
print("  hero_ml_results.csv     — full results with cluster + dev flags")
