"""
setup_db.py
===========
Marvel Rivals Meta Pulse — First-Time Database Setup
Author: Rishi Agrawal (HarshRi30)

Run this ONCE before anything else:
    python setup_db.py

What it does:
    1. Creates the marvel_rivals_meta database
    2. Creates all 4 tables (dim_hero, dim_season, fact_hero_stats, fact_teamup_stats)
    3. Adds unique constraints needed for upsert
    4. Verifies everything is ready

Requirements:
    pip install sqlalchemy psycopg2-binary
"""

from sqlalchemy import create_engine, text
from datetime import datetime

# ─────────────────────────────────────────────────────────────────
# CONFIG — update your PostgreSQL credentials
# ─────────────────────────────────────────────────────────────────
PG_USER     = "postgres"
PG_PASSWORD = "password"
PG_HOST     = "localhost"
PG_PORT     = "5432"
DB_NAME     = "marvel_rivals_meta"

# ─────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────
def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─────────────────────────────────────────────────────────────────
# STEP 1 — CREATE DATABASE
# ─────────────────────────────────────────────────────────────────
def create_database():
    # Connect to default postgres DB first to create our DB
    default_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"
    engine = create_engine(default_url, isolation_level="AUTOCOMMIT")

    with engine.connect() as conn:
        exists = conn.execute(text(
            "SELECT 1 FROM pg_database WHERE datname = :name"
        ), {"name": DB_NAME}).fetchone()

        if exists:
            log(f"Database '{DB_NAME}' already exists — skipping creation")
        else:
            conn.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
            log(f"✅ Database '{DB_NAME}' created")

    engine.dispose()


# ─────────────────────────────────────────────────────────────────
# STEP 2 — CREATE TABLES
# ─────────────────────────────────────────────────────────────────
SCHEMA_SQL = """

-- ── dim_season ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_season (
    season_id    SERIAL PRIMARY KEY,
    season_label VARCHAR(10) NOT NULL,
    CONSTRAINT uq_season_label UNIQUE (season_label)
);

-- ── dim_hero ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dim_hero (
    hero_id   SERIAL PRIMARY KEY,
    hero_name VARCHAR(100) NOT NULL,
    role      VARCHAR(20),
    CONSTRAINT uq_hero_name UNIQUE (hero_name)
);

-- ── fact_hero_stats ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_hero_stats (
    stat_id        SERIAL PRIMARY KEY,
    season_label   VARCHAR(10)  NOT NULL,
    mode           VARCHAR(20)  NOT NULL,
    rank           VARCHAR(30)  NOT NULL,
    rank_num       SMALLINT,
    hero_name      VARCHAR(100) NOT NULL,
    role           VARCHAR(20),
    tier           VARCHAR(2),
    tier_num       SMALLINT,
    win_rate       NUMERIC(5,2),
    pick_rate      NUMERIC(5,2),
    ban_rate       NUMERIC(5,2),
    matches        INTEGER,
    win_rate_rank  SMALLINT,
    CONSTRAINT uq_hero_stats
        UNIQUE (season_label, mode, rank, hero_name)
);

-- ── fact_teamup_stats ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fact_teamup_stats (
    teamup_id     SERIAL PRIMARY KEY,
    season_label  VARCHAR(10)  NOT NULL,
    mode          VARCHAR(20)  NOT NULL,
    teamup        VARCHAR(200),
    hero_count    SMALLINT,
    tier          VARCHAR(2),
    win_rate      NUMERIC(5,2),
    pick_rate     NUMERIC(5,2),
    matches       INTEGER,
    synergy_score NUMERIC(6,3),
    CONSTRAINT uq_teamup_stats
        UNIQUE (season_label, mode, teamup)
);

"""


def create_tables(engine):
    with engine.begin() as conn:
        conn.execute(text(SCHEMA_SQL))
    log("✅ All tables created (or already existed)")


# ─────────────────────────────────────────────────────────────────
# STEP 3 — VERIFY
# ─────────────────────────────────────────────────────────────────
EXPECTED_TABLES = [
    "dim_season", "dim_hero",
    "fact_hero_stats", "fact_teamup_stats"
]

def verify_setup(engine):
    print("\n" + "─" * 40)
    log("Verifying setup ...")
    all_good = True

    with engine.connect() as conn:
        for table in EXPECTED_TABLES:
            exists = conn.execute(text("""
                SELECT 1 FROM information_schema.tables
                WHERE table_name = :t AND table_schema = 'public'
            """), {"t": table}).fetchone()

            status = "✅" if exists else "❌"
            if not exists:
                all_good = False
            log(f"  {status}  {table}")

        # Check constraints
        constraints = conn.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE constraint_type = 'UNIQUE'
            AND table_schema = 'public'
        """)).fetchall()
        constraint_names = [r[0] for r in constraints]

        for c in ["uq_hero_stats", "uq_teamup_stats"]:
            status = "✅" if c in constraint_names else "❌"
            if c not in constraint_names:
                all_good = False
            log(f"  {status}  constraint: {c}")

    return all_good


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("Marvel Rivals Meta Pulse — Database Setup")
    print(f"Run time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    # Step 1 — Create DB
    log("Step 1: Creating database ...")
    try:
        create_database()
    except Exception as e:
        print(f"\n❌ Could not create database: {e}")
        print("   Check your PG_USER / PG_PASSWORD in the CONFIG block.")
        return

    # Step 2 — Create tables
    log("Step 2: Creating tables ...")
    db_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{DB_NAME}"
    engine = create_engine(db_url)

    try:
        create_tables(engine)
    except Exception as e:
        print(f"\n❌ Could not create tables: {e}")
        return

    # Step 3 — Verify
    ok = verify_setup(engine)

    print("\n" + "=" * 55)
    if ok:
        log("✅ Setup complete — database is ready")
        print("""
Next steps:
    1. Run the scraper to load all data:
           python update_pipeline.py

    2. Once data is loaded, run ML analysis:
           python ml_analysis.py
""")
    else:
        log("❌ Setup incomplete — check errors above")

    engine.dispose()


if __name__ == "__main__":
    main()
