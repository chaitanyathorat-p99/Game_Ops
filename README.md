# 🎮 Game Ops System

A hybrid rule-based Python system for processing multiplayer game match data during live events. Produces a fair leaderboard, detects suspicious players, suggests matchmaking groups, and is designed to scale from 2,000 to 200,000+ concurrent players.

---

## 📋 Table of Contents

- [Problem Statement](#-problem-statement)
- [Approach & Design Philosophy](#-approach--design-philosophy)
- [System Architecture](#-system-architecture)
- [Project Structure](#-project-structure)
- [Features](#-features)
- [Data Schema](#-data-schema)
- [Core Modules](#-core-modules)
  - [Data Loader](#1-data-loader--loaderpy)
  - [Suspicious Player Detection](#2-suspicious-player-detection--suspiciouspy)
  - [Leaderboard](#3-leaderboard--leaderboardpy)
  - [Matchmaking](#4-matchmaking--matchmakingpy)
- [Configuration](#-configuration)
- [API Endpoints](#-api-endpoints)
- [Scaling Plan](#-scaling-plan)
- [Getting Started](#-getting-started)
- [Running Tests](#-running-tests)
- [Sample Output](#-sample-output)
- [Diagrams](#-diagrams)
- [Assumptions & Limitations](#-assumptions--limitations)
- [Tech Stack](#-tech-stack)

---

## 🎯 Problem Statement

During a weekend gaming event, thousands of players submit match scores simultaneously. The game ops team needs a system that can:

1. Generate a **fair leaderboard** (global + region-wise)
2. **Detect suspicious or cheating players** automatically
3. **Suggest balanced matchmaking groups** based on skill, region, and ping
4. **Scale reliably** as player count grows from thousands to hundreds of thousands

---

## 🧠 Approach & Design Philosophy

The system uses a **hybrid rule-based approach** — deliberately chosen over ML/anomaly models for three reasons:

- **Explainability** — every flag can be justified in plain English during a demo ("P003 scored 1,650 points per second; the threshold is 50")
- **No training data required** — a weekend event doesn't generate enough history to train a meaningful model
- **Live tunability** — all thresholds live in `config.py`, so changing a single value and re-running instantly shows the impact

The architecture is a **Python script/module pipeline** with an optional FastAPI layer, producing CSV outputs that can be fed into any downstream dashboard or reporting tool.

---

## 🏗 System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                             │
│                      players.csv (raw match data)               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                       PROCESSING LAYER                          │
│                                                                 │
│  ┌─────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  loader.py  │    │  config.py   │    │   suspicious.py  │   │
│  │ ─────────── │    │ ──────────── │    │ ──────────────── │   │
│  │ Validate    │───▶│ Thresholds   │──▶ │ 5 Rule Checks    │   │
│  │ Clean       │    │ Centralized  │    │ Z-Score Outliers │   │
│  │ Normalize   │    └──────────────┘    │ Severity Rating  │   │
│  │ Deduplicate │                        └────────┬─────────┘   │
│  │ Derive cols │─────────────────────────────────┤             │
│  └─────────────┘                                 │ flagged_ids │
│         │                            ┌───────────┘             │
│         ▼                            ▼                         │
│  ┌──────────────────┐    ┌─────────────────────┐               │
│  │  leaderboard.py  │    │   matchmaking.py     │               │
│  │ ──────────────── │    │ ─────────────────── │               │
│  │ Aggregate Stats  │    │ Percentile Skill     │               │
│  │ Sort + Tiebreak  │    │ Region → Ping Band   │               │
│  │ Global + Region  │    │ → Skill Tier Groups  │               │
│  └──────────────────┘    └─────────────────────┘               │
└────────┬───────────────────────────┬────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                            │
│  suspicious_players.csv   leaderboard_global.csv                │
│  leaderboard_region.csv   matchmaking_groups.csv                │
└─────────────────────────────────────────────────────────────────┘
         │
         ▼ (optional)
┌─────────────────────────────────────────────────────────────────┐
│                       REST API LAYER                            │
│  POST /submit-score    GET /leaderboard?region=                 │
│  GET /flagged-players  GET /matchmaking?region=                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
Game/
├── data/
│   └── players.csv                 ← raw match input data
├── src/
│   ├── __init__.py
│   ├── config.py                   ← all thresholds in one place
│   ├── loader.py                   ← CSV ingestion, validation, cleaning
│   ├── leaderboard.py              ← ranking and tiebreaker logic
│   ├── suspicious.py               ← cheat detection and severity rating
│   ├── matchmaking.py              ← player grouping algorithm
│   └── utils.py                    ← shared helpers
├── api/
│   ├── __init__.py
│   ├── app.py                      ← FastAPI application entry point
│   └── routes.py                   ← endpoint definitions + Pydantic models
├── tests/
│   └── test_logic.py               ← 10 unit tests covering all core rules
├── output/
│   ├── suspicious_players.csv
│   ├── leaderboard_global.csv
│   ├── leaderboard_region.csv
│   └── matchmaking_groups.csv
├── design_doc.md                   ← short technical document (~1.5 pages)
├── requirements.txt
├── main.py                         ← CLI entry point
└── README.md
```

---

## ✨ Features

| Feature | Description |
|---|---|
| **Fair Leaderboard** | Global and region-wise rankings with a 4-level tiebreaker. Flagged players are shown separately — never mixed into clean ranks |
| **Cheat Detection** | 5 explicit rule-based checks + per-player z-score statistical outlier detection. All rules are transparent and explainable |
| **Severity Tiers** | Flags are rated High / Medium / Low with automatic escalation if a player is flagged in >50% of their matches |
| **Smart Matchmaking** | 3-pass bucketing: Region → Ping Band (Low/Med/High) → Skill Tier. Small pools skip tiering to avoid meaningless splits |
| **Percentile Skill Score** | Skill is normalized by percentile rank so score, kills, and deaths each contribute their actual weighted share |
| **Central Config** | All thresholds in `config.py` — tune one value, re-run, see the impact live |
| **REST API** | Optional FastAPI layer with Pydantic input validation for all four endpoints |
| **CSV Outputs** | All results exported to `output/` for reporting or dashboard integration |

---

## 📊 Data Schema

Each match record contains:

| Field | Type | Description |
|---|---|---|
| `player_id` | string | Unique player identifier |
| `match_id` | string | Unique match identifier |
| `region` | string | Player region (India, SEA, Europe, …) |
| `device` | string | Device type (Android, iOS, PC, Console) |
| `ping` | float | Network latency in milliseconds |
| `score` | float | Final match score |
| `kills` | int | Number of kills in the match |
| `deaths` | int | Number of deaths in the match |
| `match_duration_seconds` | float | Total match time in seconds |

**Derived columns** (computed by `loader.py`):

| Field | Formula | Purpose |
|---|---|---|
| `score_per_second` | `score / match_duration_seconds` | Core cheat detection signal |
| `kd_ratio` | `kills / max(deaths, 1)` | Secondary cheat detection signal |

**Sample input:**

```csv
player_id,match_id,region,device,ping,score,kills,deaths,match_duration_seconds
P001,M001,India,Android,55,3200,18,4,420
P002,M001,India,Android,70,2800,14,5,430
P003,M002,SEA,iOS,90,99000,250,0,60
P004,M002,India,PC,40,3500,20,6,460
P005,M003,Europe,Android,130,1200,6,8,390
```

> P003 is the obvious outlier: 99,000 points in 60 seconds = **1,650 points/second** (threshold is 50).

---

## 🔧 Core Modules

### 1. Data Loader — `loader.py`

Handles all ingestion, validation, and cleaning before any logic runs.

**Pipeline:**
1. Read CSV with `pd.read_csv`
2. Validate required columns — raise `ValueError` if any are missing
3. Drop rows with nulls in any required field *(never fill with 0 — it's a valid score and corrupts statistics)*
4. Enforce numeric types; drop rows that fail coercion
5. Drop corrupt rows: `match_duration_seconds <= 0` or any negative numeric field
6. Deduplicate on `(player_id, match_id)` — treat repeats as duplicate submissions
7. Normalize `region` and `device` strings via `.strip().title()`
8. Compute derived columns: `score_per_second`, `kd_ratio`

```python
df = loader.load_and_clean("data/players.csv")
# Output: "[loader] Dropped 1 invalid/incomplete rows out of 6"
```

---

### 2. Suspicious Player Detection — `suspicious.py`

Two-phase detection: per-match rule checks, then player-level severity aggregation.

#### Phase 1 — Per-Match Rules (run independently on every row)

| Rule | Condition | Severity |
|---|---|---|
| Score spike | `score_per_second > 50` | **High** |
| Impossible K/D | `kills >= 20 AND deaths == 0` | **High** |
| Short match abuse | `duration < 120s AND score > 5,000` | Medium |
| Extreme kills | `kills > 50` | Medium |
| Ping anomaly | `ping < 5 OR ping > 500` | Data quality (not cheat severity) |

#### Phase 2 — Z-Score Outlier Check (per player, requires ≥ 5 matches)

Computes the player's own historical mean and standard deviation for `score` and `kills`. Any match where `|z| > 3` is flagged as a statistical outlier.

> This catches players who are normally average but had one suspiciously extraordinary match — without needing cross-player training data.

#### Severity Aggregation Rules

- Highest severity across all triggered rules wins (High > Medium > Low)
- If a player is flagged in **>50% of their matches**, severity auto-escalates to **High** regardless of which rules fired

#### Matchmaking impact of severity

| Severity | Leaderboard | Matchmaking |
|---|---|---|
| High | Shown unranked (under review) | Excluded entirely |
| Medium | Shown unranked (under review) | Isolated under-review pool |
| Low | Shown unranked (under review) | Matched normally, tagged |

---

### 3. Leaderboard — `leaderboard.py`

Produces two tables: global and region-wise.

#### Tiebreaker Order (applied to clean players only)

| Priority | Field | Direction |
|---|---|---|
| 1st | `total_score` | Descending |
| 2nd | `total_deaths` | Ascending (fewer = better) |
| 3rd | `total_kills` | Descending |
| 4th | `matches_played` | Descending |

#### Fairness Rule

Flagged players are **never assigned a numeric rank**. They appear below clean players in an "under review" block. A flagged player's presence cannot shift any clean player's rank number.

```
Rank 1  →  P004   Score: 3,500   Deaths: 6    Status: clean
Rank 2  →  P001   Score: 3,200   Deaths: 4    Status: clean
Rank 3  →  P002   Score: 2,800   Deaths: 5    Status: clean
────────────────────────────────────────────────────────────
Unranked → P003   Score: 99,000               Status: under_review
```

---

### 4. Matchmaking — `matchmaking.py`

Groups players into fair lobbies using a 3-pass bucketing algorithm.

#### Skill Score (percentile-normalized)

```
skill_score = (avg_score_percentile × 0.5)
            + (avg_kills_percentile × 0.3)
            − (avg_deaths_percentile × 0.2)
```

Each component is converted to a percentile rank (0–1) within the player pool before weighting. This ensures kills and deaths actually influence the result — not just score.

#### 3-Pass Grouping Algorithm

```
Pass 1 — Region Bucket
  Group by region to minimize latency

Pass 2 — Ping Band (hard rule — never mix bands)
  LowPing  : ping ≤ 80ms
  MedPing  : 81ms – 150ms
  HighPing : > 150ms

Pass 3 — Skill Tier (only if bucket ≥ 6 players)
  Beginner     : bottom 33% skill score
  Intermediate : middle 33%
  Advanced     : top 33%
  Small Pool   : < 6 players → skip tiering, tag "skill_mixed_small_pool"
```

**Final group name format:** `Region_PingBand_SkillTier`
Example: `India_LowPing_Advanced → [P001, P004]`

Groups with fewer than 4 players are tagged `"waiting_for_more_players"` and not dispatched.

---

## ⚙️ Configuration

All thresholds are centralized in `src/config.py`. Change any value and re-run — no code edits needed elsewhere.

```python
# src/config.py

# Cheat detection thresholds
SCORE_PER_SECOND_THRESHOLD      = 50     # Rule 1: score/sec above this → High flag
KD_ZERO_DEATH_KILL_THRESHOLD    = 20     # Rule 2: kills >= this with 0 deaths → High flag
SHORT_MATCH_SECONDS             = 120    # Rule 3: match shorter than this...
SHORT_MATCH_SCORE_THRESHOLD     = 5000   # Rule 3: ...with score above this → Medium flag
EXTREME_KILL_THRESHOLD          = 50     # Rule 4: kills above this → Medium flag
PING_MIN_VALID                  = 5      # Rule 5: ping below this → data quality flag
PING_MAX_VALID                  = 500    # Rule 5: ping above this → data quality flag

# Z-score detection
ZSCORE_MIN_MATCHES              = 5      # minimum matches before z-score is applied
ZSCORE_THRESHOLD                = 3      # |z| above this → statistical outlier flag

# Repeat-offense escalation
REPEAT_FLAG_RATIO_FOR_ESCALATION = 0.5  # >50% matches flagged → escalate to High

# Ping bands for matchmaking
PING_BAND_LOW_MAX               = 80     # ≤ 80ms = LowPing
PING_BAND_MEDIUM_MAX            = 150    # 81–150ms = MedPing, >150ms = HighPing

# Matchmaking pool rules
MIN_BUCKET_SIZE_FOR_TIERING     = 6      # buckets smaller than this skip skill tiering
MIN_MATCH_GROUP_SIZE            = 4      # groups smaller than this → waiting for players
```

---

## 🌐 API Endpoints

The optional FastAPI layer wraps the same core functions. Run with: `uvicorn api.app:app --reload`

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/submit-score` | Submit a new match result. Validated by Pydantic before processing |
| `GET` | `/leaderboard?region=India` | Returns ranked leaderboard. Omit `region` for global |
| `GET` | `/flagged-players` | Returns all suspicious players with reasons and severity |
| `GET` | `/matchmaking?region=India` | Returns suggested match groups for a region |

**Request body for `POST /submit-score`:**

```json
{
  "player_id": "P006",
  "match_id": "M004",
  "region": "India",
  "device": "PC",
  "ping": 45,
  "score": 3100,
  "kills": 17,
  "deaths": 5,
  "match_duration_seconds": 410
}
```

> Note: The prototype uses an in-memory DataFrame. In a real deployment, swap for PostgreSQL + Redis (see Scaling Plan below).

---

## 📈 Scaling Plan

| Today | Tomorrow |
|---|---|
| 2,000 players | 200,000+ players |
| Single Python script | Distributed microservices |
| In-memory DataFrame | PostgreSQL + Redis |
| No queue | Kafka / AWS SQS |

### Production Architecture

```
Game Clients
     │  HTTP POST /submit-score
     ▼
Load Balancer  →  FastAPI Pods (stateless, horizontally scaled)
                         │
                         ▼  async write
                  Kafka / AWS SQS  ──────────────────┐
                                                     │
                         ┌───────────────────────────┘
                         ▼                          ▼
                  Worker Service           Anomaly Detection Worker
                  (writes match records)   (runs rule checks)
                         │                          │
                         └──────────┬───────────────┘
                                    ▼
                             PostgreSQL (primary store)
                             - matches table
                             - player_aggregates table
                             - flagged_players table
                             - Partitioned by region + date
                                    │
                        background refresh (every 30s)
                                    ▼
                             Redis Sorted Set
                             - Hot leaderboard cache
                             - Top-100 reads in < 5ms
                                    │
                  GET /leaderboard ──┤ cache hit → Redis
                                     └ cache miss → PostgreSQL

Monitoring: Prometheus (metrics) → Grafana (API latency, queue lag, error rate)
```

### Key scaling decisions

- **Redis sorted sets** — `ZADD` and `ZREVRANGE` give O(log N) rank updates and instant top-N reads without scanning the full table
- **Kafka/SQS queue** — decouples write ingestion from API response time; 200k+ submissions/day processed asynchronously without blocking clients
- **Stateless API pods** — no session state means horizontal scaling behind a load balancer is trivial
- **PostgreSQL partitioning** — partition by `region` and `match_date` so region leaderboard queries scan only the relevant partition
- **Background leaderboard refresh** — pre-compute and cache top-100 every 30 seconds via a scheduled job; full re-rank only on demand

---

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- pip

### Install dependencies

```bash
pip install -r requirements.txt
```

### Run the pipeline

```bash
python main.py --data data/players.csv
```

**Example output:**

```
[loader] Dropped 0 invalid/incomplete rows out of 5

=== SUSPICIOUS PLAYERS ===
player_id  flagged_matches  flag_reasons              severity
P003       1                score_or_kd_impossible    High

=== GLOBAL LEADERBOARD ===
rank  player_id  total_score  total_deaths  status
1     P004       3500         6             clean
2     P001       3200         4             clean
3     P002       2800         5             clean
4     P005       1200         8             clean
-     P003       99000        0             under_review

=== MATCHMAKING GROUPS ===
group_id                      players
India_LowPing_Mixed           [P004, P001, P002]
Europe_HighPing_Mixed         [P005]
Under_Review_Pool             [P003]

Summary: 5 processed | 0 dropped | 1 flagged | 2 active groups
```

### Run the API server (optional)

```bash
uvicorn api.app:app --reload
# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

**Test coverage (10 tests):**

| Test | What it verifies |
|---|---|
| `test_flag_score_per_second` | P003-style score spike triggers Rule 1 |
| `test_no_flag_normal_player` | Normal player passes all rules clean |
| `test_leaderboard_tiebreaker` | Player with fewer deaths ranks above equal-score player |
| `test_matchmaking_region_separation` | India and Europe players land in different groups |
| `test_kd_zero_death_flag` | 25 kills + 0 deaths triggers Rule 2 |
| `test_zero_duration_dropped` | `match_duration_seconds=0` row is dropped, no ZeroDivisionError |
| `test_zscore_std_zero_no_crash` | Player with 5 identical matches causes no exception |
| `test_small_bucket_skips_tiering` | 2-player bucket tagged `skill_mixed_small_pool`, not tiered |
| `test_severity_takes_highest` | Player triggering Medium + High rules → severity is High |
| `test_repeat_offense_escalates` | Player flagged in 6/10 matches escalates to High |

---

## 📄 Sample Output

### suspicious_players.csv

```csv
player_id,flagged_matches,flag_reasons,severity
P003,1,score_or_kd_impossible,High
```

### leaderboard_global.csv

```csv
rank,player_id,total_score,total_kills,total_deaths,matches_played,status
1,P004,3500,20,6,1,clean
2,P001,3200,18,4,1,clean
3,P002,2800,14,5,1,clean
4,P005,1200,6,8,1,clean
,P003,99000,250,0,1,under_review
```

### matchmaking_groups.csv

```csv
group_id,player_ids,status
India_LowPing_Mixed,"P004,P001,P002",active
Europe_HighPing_Mixed,P005,waiting_for_more_players
Under_Review_Pool,P003,isolated
```

---

## 📐 Diagrams

PlantUML source code for all 7 system diagrams is in [`diagram.txt`](./diagram.txt).

| # | Diagram | Render at |
|---|---|---|
| 1 | System Architecture Overview | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 2 | Data Cleaning Pipeline | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 3 | Suspicious Player Detection Logic | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 4 | Leaderboard Ranking Logic | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 5 | Matchmaking Grouping Algorithm | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 6 | Scaling Architecture (Production) | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |
| 7 | End-to-End Demo Flow (Swimlane) | [plantuml.com](https://www.plantuml.com/plantuml/uml/) |

To render: copy any `@startuml ... @enduml` block from `diagram.txt` and paste at [plantuml.com/plantuml/uml](https://www.plantuml.com/plantuml/uml/).

---

## ⚠️ Assumptions & Limitations

### Assumptions

- CSV is the data source — no real-time stream is assumed for the prototype
- A "fair leaderboard" means clean players get numeric ranks; flagged players are shown separately, never mixed in
- Ranking is by **total accumulated score** across all matches — this rewards both skill and participation, which is the right model for a weekend score event (not a skill ladder)
- Z-score outlier detection requires at least **5 matches** of history per player; fewer matches are checked against absolute rule thresholds only
- The "weekend event" framing means there is not enough historical data to train an ML anomaly model meaningfully — hence the rule-based approach

### Limitations

- Thresholds in `config.py` are manually set based on the sample data. A production system would calibrate them from historical match data per game mode
- Skill score is percentile-based **within the current player pool** — it is relative, not absolute, so it shifts as the pool changes
- Small region+ping buckets (fewer than 6 players) skip skill tiering entirely rather than producing meaningless thirds
- The prototype API uses an **in-memory DataFrame** that is not persisted across restarts — swap for PostgreSQL in a real deployment
- No authentication or rate limiting on API endpoints
- Matchmaking is **static bucketing**, not a live queue with wait-time optimization

---

## 🛠 Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Data processing | Python, pandas, numpy | Fast DataFrame operations, wide ecosystem |
| Statistics | scipy (`zscore`) | Reliable, battle-tested statistical functions |
| API | FastAPI + Pydantic | Automatic validation, OpenAPI docs at `/docs` |
| Server | uvicorn | ASGI server for async FastAPI |
| Testing | pytest | Standard Python test runner |
| Production DB | PostgreSQL | ACID compliance, partition support, rich query planner |
| Leaderboard cache | Redis Sorted Set | O(log N) rank ops, sub-5ms top-N reads |
| Message queue | Kafka / AWS SQS | Async ingestion, decouples writes from API latency |
| Monitoring | Prometheus + Grafana | Industry standard, works with FastAPI metrics middleware |

---

## 🗂 Related Files

| File | Purpose |
|---|---|
| `implementation_plan.txt` | Full phased implementation guide with annotated code snippets |
| `diagram.txt` | PlantUML source for all 7 system diagrams |
| `design_doc.md` | Short technical document (~1.5 pages) for submission |
| `data/players.csv` | Sample input data |
| `output/` | All generated CSV outputs |
