import pytest
import pandas as pd
import numpy as np
import io

from src.loader import load_and_clean_data
from src.suspicious import check_match_rules, detect_suspicious_players
from src.leaderboard import generate_leaderboard
from src.matchmaking import generate_matchmaking_groups

# Mock CSV string helper
def make_mock_csv(data_rows: list) -> str:
    header = "player_id,match_id,region,device,ping,score,kills,deaths,match_duration_seconds"
    return "\n".join([header] + data_rows)

def test_loader_validation(tmp_path):
    # Valid CSV content
    valid_csv = make_mock_csv([
        "P001,M001,India,Android,50,3000,10,2,400",
        "P002,M001,India,iOS,60,2500,8,3,410"
    ])
    p = tmp_path / "valid.csv"
    p.write_text(valid_csv)

    df = load_and_clean_data(str(p))
    assert len(df) == 2
    assert "score_per_second" in df.columns
    assert "kd_ratio" in df.columns
    assert df.loc[0, 'score_per_second'] == 3000 / 400
    assert df.loc[0, 'kd_ratio'] == 10 / 2

    # Invalid CSV (missing column)
    invalid_csv = "player_id,match_id,score\nP001,M001,3000"
    p_invalid = tmp_path / "invalid.csv"
    p_invalid.write_text(invalid_csv)

    with pytest.raises(ValueError, match="Missing required columns"):
        load_and_clean_data(str(p_invalid))

def test_suspicious_rule_checks():
    # Rule 1: Score/sec spike
    r1 = pd.Series({'score_per_second': 55.0, 'kills': 5, 'deaths': 2, 'match_duration_seconds': 100, 'score': 5500, 'ping': 50})
    flags = check_match_rules(r1)
    assert any("Score rate spike" in f for f in flags)

    # Rule 2: High K/D zero death
    r2 = pd.Series({'score_per_second': 5.0, 'kills': 25, 'deaths': 0, 'match_duration_seconds': 300, 'score': 1500, 'ping': 50})
    flags = check_match_rules(r2)
    assert any("High-kill zero-death" in f for f in flags)

    # Rule 3: Short match high score
    r3 = pd.Series({'score_per_second': 45.0, 'kills': 5, 'deaths': 2, 'match_duration_seconds': 90, 'score': 5500, 'ping': 50})
    flags = check_match_rules(r3)
    assert any("Short match high score" in f for f in flags)

    # Rule 4: Extreme kills
    r4 = pd.Series({'score_per_second': 5.0, 'kills': 60, 'deaths': 5, 'match_duration_seconds': 300, 'score': 1500, 'ping': 50})
    flags = check_match_rules(r4)
    assert any("Extreme kills" in f for f in flags)

    # Rule 5: Ping anomaly
    r5 = pd.Series({'score_per_second': 5.0, 'kills': 5, 'deaths': 2, 'match_duration_seconds': 300, 'score': 1500, 'ping': 600})
    flags = check_match_rules(r5)
    assert any("Ping anomaly" in f for f in flags)

def test_historical_zscore_flagging():
    # Construct a dataset where player P001 has 10 normal matches and 1 extraordinary match (N=11)
    # This mathematically allows the Z-score to exceed 3.0 (max possible Z for N=11 is ~3.015)
    rows = []
    # 10 normal matches
    for i in range(1, 11):
        rows.append({
            'player_id': 'P001', 'match_id': f'M{i}', 'region': 'India', 'device': 'PC', 'ping': 40,
            'score': 1000.0, 'kills': 5, 'deaths': 3, 'match_duration_seconds': 300,
            'score_per_second': 3.33, 'kd_ratio': 1.66
        })
    # 1 outlier match
    rows.append({
        'player_id': 'P001', 'match_id': 'M11', 'region': 'India', 'device': 'PC', 'ping': 40,
        'score': 10000.0, 'kills': 50, 'deaths': 1, 'match_duration_seconds': 300,
        'score_per_second': 33.33, 'kd_ratio': 50.0
    })
    df = pd.DataFrame(rows)
    
    # Run suspicious players detection
    flagged_map, flagged_df = detect_suspicious_players(df)
    
    # P001 should be flagged due to Z-score outlier on score and kills
    assert 'P001' in flagged_map
    reasons = flagged_map['P001']['reasons']
    assert any("Historical score outlier" in r or "Historical kills outlier" in r for r in reasons)
    assert flagged_map['P001']['severity'] == 'Low' # Z-score deviation is Low severity by default

def test_leaderboard_tiebreakers():
    # 2 players with exact same score. P001 has fewer deaths than P002.
    # P003 is flagged.
    df = pd.DataFrame([
        {'player_id': 'P001', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 40, 'score': 3000.0, 'kills': 10, 'deaths': 2, 'match_duration_seconds': 300, 'score_per_second': 10.0, 'kd_ratio': 5.0},
        {'player_id': 'P002', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 45, 'score': 3000.0, 'kills': 12, 'deaths': 4, 'match_duration_seconds': 300, 'score_per_second': 10.0, 'kd_ratio': 3.0},
        {'player_id': 'P003', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 40, 'score': 99000.0, 'kills': 200, 'deaths': 0, 'match_duration_seconds': 60, 'score_per_second': 1650.0, 'kd_ratio': 200.0}
    ])
    
    flagged_players = {
        'P003': {'severity': 'High', 'reasons': ['Score rate spike']}
    }
    
    global_lb, region_lb = generate_leaderboard(df, flagged_players)
    
    # Clean players should be ranked 1st and 2nd. P003 is unranked (NaN) at the bottom.
    p001_rank = global_lb[global_lb['player_id'] == 'P001']['rank'].values[0]
    p002_rank = global_lb[global_lb['player_id'] == 'P002']['rank'].values[0]
    p003_rank = global_lb[global_lb['player_id'] == 'P003']['rank'].values[0]
    
    assert p001_rank == 1.0 # Fewer deaths wins
    assert p002_rank == 2.0
    assert np.isnan(p003_rank)
    
    # Total score for P003 is still displayed
    assert global_lb[global_lb['player_id'] == 'P003']['total_score'].values[0] == 99000.0
    assert global_lb[global_lb['player_id'] == 'P003']['status'].values[0] == 'under_review'

def test_matchmaking_lobbies():
    df = pd.DataFrame([
        {'player_id': 'P001', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 40, 'score': 3000, 'kills': 10, 'deaths': 2, 'match_duration_seconds': 300},
        {'player_id': 'P002', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 50, 'score': 2800, 'kills': 8, 'deaths': 3, 'match_duration_seconds': 300},
        {'player_id': 'P003', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 42, 'score': 99000, 'kills': 250, 'deaths': 0, 'match_duration_seconds': 60}, # High cheater
        {'player_id': 'P004', 'match_id': 'M1', 'region': 'Europe', 'device': 'PC', 'ping': 220, 'score': 1500, 'kills': 5, 'deaths': 6, 'match_duration_seconds': 300}, # Europe High Ping
        {'player_id': 'P005', 'match_id': 'M1', 'region': 'India', 'device': 'PC', 'ping': 45, 'score': 10000, 'kills': 45, 'deaths': 1, 'match_duration_seconds': 300} # Med cheater
    ])
    
    flagged_players = {
        'P003': {'severity': 'High', 'reasons': ['Score rate spike']},
        'P005': {'severity': 'Medium', 'reasons': ['Extreme stats']}
    }
    
    lobbies_map, lobbies_df = generate_matchmaking_groups(df, flagged_players)
    
    # 1. P003 (High) should be completely excluded
    all_matched_players = []
    for lobby, roster in lobbies_map.items():
        for player in roster:
            all_matched_players.append(player['player_id'])
            
    assert 'P003' not in all_matched_players
    
    # 2. P005 (Medium) should be in the isolated lobby
    assert 'Isolated_UnderReview' in lobbies_map
    isolated_ids = [p['player_id'] for p in lobbies_map['Isolated_UnderReview']]
    assert 'P005' in isolated_ids
    
    # 3. P004 (Europe, High ping) and P001, P002 (India, Low ping) should be in separate lobbies
    europe_lobbies = [k for k in lobbies_map.keys() if k.startswith('Europe')]
    india_lobbies = [k for k in lobbies_map.keys() if k.startswith('India')]
    
    assert len(europe_lobbies) > 0
    assert len(india_lobbies) > 0
    
    # Validate separation
    for el in europe_lobbies:
        for player in lobbies_map[el]:
            assert player['player_id'] == 'P004'
            
    for il in india_lobbies:
        for player in lobbies_map[il]:
            assert player['player_id'] in ['P001', 'P002']
