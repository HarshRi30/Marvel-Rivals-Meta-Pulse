-- ============================================================
-- analysis.sql
-- Marvel Rivals Meta Pulse
-- Author: Rishi Agrawal (HarshRi30)
--
-- 22 queries across 5 sections:
--   Section 1 : Meta Overview        (Q1  – Q4)
--   Section 2 : Role Balance         (Q5  – Q8)
--   Section 3 : Hero Power & Tiers   (Q9  – Q12)
--   Section 4 : Ban & Pick Anomalies (Q13 – Q17)
--   Section 5 : Team-Up Analysis     (Q18 – Q22)
--
-- All queries run on v_comp_all (competitive + All Ranks)
-- unless stated otherwise.
-- ============================================================


-- ============================================================
-- SECTION 1 — META OVERVIEW
-- ============================================================

-- Q1: Hero count and match volume per season
SELECT
    s.season_label,
    s.season_name,
    COUNT(DISTINCT h.hero)              AS hero_count,
    SUM(h.matches)                      AS total_matches,
    ROUND(AVG(h.win_rate),  2)          AS avg_win_rate,
    ROUND(AVG(h.pick_rate), 2)          AS avg_pick_rate,
    ROUND(AVG(h.ban_rate),  2)          AS avg_ban_rate
FROM v_comp_all h
JOIN dim_season s USING (season_label)
GROUP BY s.season_label, s.season_name, s.season_num
ORDER BY s.season_num;


-- Q2: Tier distribution per season
-- How many heroes sit in S / A / B / C / D each season?
SELECT
    season_label,
    tier,
    COUNT(*)                                                    AS hero_count,
    ROUND(COUNT(*) * 100.0 /
          SUM(COUNT(*)) OVER (PARTITION BY season_label), 1)   AS pct_of_season
FROM v_comp_all
GROUP BY season_label, tier, tier_num
ORDER BY season_label, tier_num DESC;


-- Q3: Top 10 most picked heroes (avg pick rate across all seasons)
SELECT
    hero,
    role,
    ROUND(AVG(pick_rate), 2)    AS avg_pick_rate,
    ROUND(AVG(win_rate),  2)    AS avg_win_rate,
    ROUND(AVG(ban_rate),  2)    AS avg_ban_rate,
    ROUND(AVG(power_score), 2)  AS avg_power_score
FROM v_comp_all
GROUP BY hero, role
ORDER BY avg_pick_rate DESC
LIMIT 10;


-- Q4: Meta stability — avg win rate shift per hero between consecutive seasons
-- High shift = volatile meta, low shift = stable meta
WITH ranked AS (
    SELECT
        hero,
        season_num,
        win_rate,
        LAG(win_rate) OVER (PARTITION BY hero ORDER BY season_num) AS prev_win_rate
    FROM v_comp_all
),
shifts AS (
    SELECT
        hero,
        season_num,
        ABS(win_rate - prev_win_rate) AS win_rate_shift
    FROM ranked
    WHERE prev_win_rate IS NOT NULL
)
SELECT
    hero,
    ROUND(AVG(win_rate_shift), 3)   AS avg_season_shift,
    ROUND(MAX(win_rate_shift), 3)   AS max_season_shift,
    COUNT(*)                        AS seasons_tracked
FROM shifts
GROUP BY hero
ORDER BY avg_season_shift DESC
LIMIT 15;


-- ============================================================
-- SECTION 2 — ROLE BALANCE
-- ============================================================

-- Q5: Average win/pick/ban rate per role per season
SELECT
    season_label,
    season_num,
    role,
    COUNT(DISTINCT hero)            AS heroes_in_role,
    ROUND(AVG(win_rate),  2)        AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)        AS avg_pick_rate,
    ROUND(AVG(ban_rate),  2)        AS avg_ban_rate,
    ROUND(AVG(power_score), 2)      AS avg_power_score
FROM v_comp_all
GROUP BY season_label, season_num, role
ORDER BY season_num, role;


-- Q6: Which role dominates the S-tier each season?
SELECT
    season_label,
    role,
    COUNT(*)                        AS s_tier_heroes,
    ROUND(AVG(win_rate),  2)        AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)        AS avg_pick_rate
FROM v_comp_all
WHERE tier = 'S'
GROUP BY season_label, role
ORDER BY season_label, s_tier_heroes DESC;


-- Q7: Role win rate gap vs 50% baseline each season
-- Positive = above 50%, negative = below
SELECT
    season_label,
    season_num,
    role,
    ROUND(AVG(win_rate), 2)                     AS avg_win_rate,
    ROUND(AVG(win_rate) - 50.0, 2)              AS gap_from_50,
    ROUND(AVG(pick_rate), 2)                    AS avg_pick_rate
FROM v_comp_all
GROUP BY season_label, season_num, role
ORDER BY season_num, gap_from_50 DESC;


-- Q8: Attack type win rate comparison
-- Melee vs Projectile vs Hitscan — which fights best?
SELECT
    h.attack_type,
    f.role,
    COUNT(DISTINCT f.hero)              AS hero_count,
    ROUND(AVG(f.win_rate),  2)          AS avg_win_rate,
    ROUND(AVG(f.pick_rate), 2)          AS avg_pick_rate,
    ROUND(AVG(f.ban_rate),  2)          AS avg_ban_rate
FROM v_comp_all f
JOIN dim_hero h ON f.hero = h.hero_name
GROUP BY h.attack_type, f.role
ORDER BY f.role, avg_win_rate DESC;


-- ============================================================
-- SECTION 3 — HERO POWER & TIERS
-- ============================================================

-- Q9: Top 10 heroes by power score (competitive, all seasons avg)
SELECT
    hero,
    role,
    ROUND(AVG(win_rate),     2)     AS avg_win_rate,
    ROUND(AVG(pick_rate),    2)     AS avg_pick_rate,
    ROUND(AVG(ban_rate),     2)     AS avg_ban_rate,
    ROUND(AVG(power_score),  3)     AS avg_power_score,
    ROUND(AVG(dominance_score), 3)  AS avg_dominance
FROM v_comp_all
GROUP BY hero, role
ORDER BY avg_power_score DESC
LIMIT 10;


-- Q10: Biggest overrated heroes (high pick, low win — pick_win_gap > 0)
-- These heroes are picked often but don't deliver wins
SELECT
    hero,
    role,
    ROUND(AVG(pick_rate),    2)     AS avg_pick_rate,
    ROUND(AVG(win_rate),     2)     AS avg_win_rate,
    ROUND(AVG(pick_win_gap), 2)     AS avg_pick_win_gap
FROM v_comp_all
GROUP BY hero, role
HAVING AVG(pick_win_gap) > 0
ORDER BY avg_pick_win_gap DESC
LIMIT 10;


-- Q11: Biggest underrated heroes (low pick, high win — pick_win_gap < 0)
-- Strong heroes the playerbase ignores
SELECT
    hero,
    role,
    ROUND(AVG(pick_rate),    2)     AS avg_pick_rate,
    ROUND(AVG(win_rate),     2)     AS avg_win_rate,
    ROUND(AVG(pick_win_gap), 2)     AS avg_pick_win_gap
FROM v_comp_all
GROUP BY hero, role
HAVING AVG(pick_win_gap) < 0
ORDER BY avg_pick_win_gap ASC
LIMIT 10;


-- Q12: Win rate by rank tier for top 5 heroes
-- Does Peni Parker dominate at low rank but fall off at high rank?
SELECT
    hero,
    rank,
    rank_num,
    ROUND(AVG(win_rate),  2)    AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)    AS avg_pick_rate,
    SUM(matches)                AS total_matches
FROM fact_hero_stats
WHERE mode = 'competitive'
  AND hero IN (
      SELECT hero FROM v_comp_all
      GROUP BY hero ORDER BY AVG(power_score) DESC LIMIT 5
  )
GROUP BY hero, rank, rank_num
ORDER BY hero, rank_num;


-- ============================================================
-- SECTION 4 — BAN & PICK ANOMALIES
-- ============================================================

-- Q13: Heroes with highest ban rate (ban > 10%)
-- Being banned = community considers you broken
SELECT
    hero,
    role,
    ROUND(AVG(ban_rate),  2)    AS avg_ban_rate,
    ROUND(AVG(win_rate),  2)    AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)    AS avg_pick_rate,
    COUNT(*)                    AS seasons_high_ban
FROM v_comp_all
WHERE is_high_ban = 1
GROUP BY hero, role
ORDER BY avg_ban_rate DESC;


-- Q14: Ban rate vs win rate — are high-ban heroes actually winning?
-- High ban + high win = genuinely broken
-- High ban + low win = perception problem (feared but not dominant)
SELECT
    hero,
    role,
    ROUND(AVG(ban_rate),  2)    AS avg_ban_rate,
    ROUND(AVG(win_rate),  2)    AS avg_win_rate,
    CASE
        WHEN AVG(ban_rate) > 10 AND AVG(win_rate) > 51 THEN 'Genuinely Broken'
        WHEN AVG(ban_rate) > 10 AND AVG(win_rate) <= 51 THEN 'Feared Not Dominant'
        WHEN AVG(ban_rate) <= 10 AND AVG(win_rate) > 51 THEN 'Hidden OP'
        ELSE 'Normal'
    END                         AS power_label
FROM v_comp_all
GROUP BY hero, role
ORDER BY avg_ban_rate DESC
LIMIT 15;


-- Q15: Heroes with biggest ban rate vs pick rate gap
-- High ban + low pick = banned before they can even be picked
SELECT
    hero,
    role,
    ROUND(AVG(ban_rate),  2)                    AS avg_ban_rate,
    ROUND(AVG(pick_rate), 2)                    AS avg_pick_rate,
    ROUND(AVG(ban_rate) - AVG(pick_rate), 2)    AS ban_pick_gap
FROM v_comp_all
GROUP BY hero, role
ORDER BY ban_pick_gap DESC
LIMIT 10;


-- Q16: Pick rate vs win rate correlation per role
-- Pearson correlation: does being popular mean you win more?
SELECT
    role,
    ROUND(CORR(pick_rate, win_rate)::NUMERIC, 4)    AS pick_win_corr,
    COUNT(*)                                         AS sample_size
FROM v_comp_all
GROUP BY role
ORDER BY pick_win_corr DESC;


-- Q17: Heroes with consistently D/C tier across all seasons
-- Chronic underperformers — never got a buff that worked
SELECT
    hero,
    role,
    COUNT(*)                        AS total_seasons,
    SUM(CASE WHEN tier IN ('C','D') THEN 1 ELSE 0 END) AS low_tier_seasons,
    ROUND(AVG(win_rate), 2)         AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)        AS avg_pick_rate
FROM v_comp_all
GROUP BY hero, role
HAVING SUM(CASE WHEN tier IN ('C','D') THEN 1 ELSE 0 END) >= 5
ORDER BY low_tier_seasons DESC, avg_win_rate ASC;


-- ============================================================
-- SECTION 5 — TEAM-UP ANALYSIS
-- ============================================================

-- Q18: Top 10 team-ups by win rate (competitive)
SELECT
    season_label,
    teamup,
    hero_count,
    tier,
    win_rate,
    pick_rate,
    matches,
    synergy_score
FROM fact_teamup_stats
WHERE mode = 'competitive'
ORDER BY win_rate DESC
LIMIT 10;


-- Q19: Average win rate by team-up size (2-hero vs 3-hero)
-- Do 3-hero team-ups outperform 2-hero ones?
SELECT
    hero_count,
    mode,
    COUNT(DISTINCT teamup)          AS unique_combos,
    ROUND(AVG(win_rate),  2)        AS avg_win_rate,
    ROUND(AVG(pick_rate), 2)        AS avg_pick_rate,
    ROUND(AVG(synergy_score), 3)    AS avg_synergy
FROM fact_teamup_stats
GROUP BY hero_count, mode
ORDER BY hero_count, mode;


-- Q20: Most consistent team-ups — high win rate across all seasons
SELECT
    teamup,
    hero_count,
    COUNT(DISTINCT season_label)        AS seasons_present,
    ROUND(AVG(win_rate),      2)        AS avg_win_rate,
    ROUND(MIN(win_rate),      2)        AS min_win_rate,
    ROUND(MAX(win_rate),      2)        AS max_win_rate,
    ROUND(AVG(pick_rate),     2)        AS avg_pick_rate,
    ROUND(AVG(synergy_score), 3)        AS avg_synergy
FROM fact_teamup_stats
WHERE mode = 'competitive'
GROUP BY teamup, hero_count
HAVING COUNT(DISTINCT season_label) >= 4
ORDER BY avg_win_rate DESC
LIMIT 10;


-- Q21: Team-up tier distribution
-- What % of team-ups land in each tier?
SELECT
    tier,
    tier_num,
    COUNT(*)                                                    AS combo_count,
    ROUND(AVG(win_rate), 2)                                     AS avg_win_rate,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1)         AS pct_of_total
FROM fact_teamup_stats
WHERE mode = 'competitive'
GROUP BY tier, tier_num
ORDER BY tier_num DESC;


-- Q22: Quickplay vs Competitive win rate delta for team-ups
-- Do some team-ups perform wildly differently in casual vs ranked?
WITH comp AS (
    SELECT teamup, ROUND(AVG(win_rate), 2) AS comp_wr
    FROM fact_teamup_stats WHERE mode = 'competitive'
    GROUP BY teamup
),
qp AS (
    SELECT teamup, ROUND(AVG(win_rate), 2) AS qp_wr
    FROM fact_teamup_stats WHERE mode = 'quickplay'
    GROUP BY teamup
)
SELECT
    c.teamup,
    c.comp_wr,
    q.qp_wr,
    ROUND(c.comp_wr - q.qp_wr, 2)  AS comp_minus_qp
FROM comp c
JOIN qp q USING (teamup)
ORDER BY ABS(c.comp_wr - q.qp_wr) DESC
LIMIT 15;
