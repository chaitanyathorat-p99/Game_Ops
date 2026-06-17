import pandas as pd
import numpy as np
from typing import Dict, Any, Set, List, Tuple

def check_match_rules(row: pd.Series) -> List[str]:
    """
    Checks per-match thresholds and returns list of triggered rule descriptions.
    """
    flags = []
    
    # Rule 1: Score-per-second spike (typical is ~7-10; cheater P003 is 1650)
    if row['score_per_second'] > 50:
        flags.append(f"Score rate spike: {row['score_per_second']:.2f} score/sec (Limit: 50)")
        
    # Rule 2: Impossible K/D with zero deaths
    if row['kills'] >= 20 and row['deaths'] == 0:
        flags.append(f"High-kill zero-death K/D: {row['kills']} kills, 0 deaths")
        
    # Rule 3: Short match + very high score
    if row['match_duration_seconds'] < 120 and row['score'] > 5000:
        flags.append(f"Short match high score: {row['score']} score in {row['match_duration_seconds']}s")
        
    # Rule 4: Extreme kill count in a single match
    if row['kills'] > 50:
        flags.append(f"Extreme kills: {row['kills']} kills in a match (Limit: 50)")
        
    # Rule 5: Ping anomaly (network metric)
    if row['ping'] < 5 or row['ping'] > 500:
        flags.append(f"Ping anomaly: {row['ping']}ms (Limits: 5-500ms)")
        
    return flags

def compute_historical_zscores(df: pd.DataFrame) -> pd.Series:
    """
    Computes per-player historical Z-scores for score and kills.
    Returns a pandas Series where each element is a list of statistical flags if any,
    otherwise empty list.
    """
    statistical_flags = [[] for _ in range(len(df))]
    
    # Group by player to calculate statistics
    player_groups = df.groupby('player_id')
    
    for player_id, group in player_groups:
        if len(group) < 3:
            # Not enough history for statistical standard deviation
            continue
            
        # Stats for score
        mean_score = group['score'].mean()
        std_score = group['score'].std()
        
        # Stats for kills
        mean_kills = group['kills'].mean()
        std_kills = group['kills'].std()
        
        for idx in group.index:
            row = df.loc[idx]
            match_flags = []
            
            # Score z-score
            if std_score > 0:
                z_score = (row['score'] - mean_score) / std_score
                if abs(z_score) > 3.0:
                    match_flags.append(f"Historical score outlier: Z-Score = {z_score:.2f} (Limit: +/-3.0)")
            
            # Kills z-score
            if std_kills > 0:
                z_kills = (row['kills'] - mean_kills) / std_kills
                if abs(z_kills) > 3.0:
                    match_flags.append(f"Historical kills outlier: Z-Score = {z_kills:.2f} (Limit: +/-3.0)")
                    
            if match_flags:
                statistical_flags[idx] = match_flags
                
    return pd.Series(statistical_flags, index=df.index)

def detect_suspicious_players(df: pd.DataFrame) -> Tuple[Dict[str, Dict[str, Any]], pd.DataFrame]:
    """
    Analyzes match data for suspicious player activities.
    
    Returns:
    - Dict[str, Dict[str, Any]]: A map of player_id -> {
         'severity': 'High' | 'Medium' | 'Low',
         'reasons': List[str],
         'flagged_matches_count': int,
         'total_matches_count': int
      }
    - pd.DataFrame: A flat DataFrame of suspicious players for easy export
    """
    if df.empty:
        empty_flat = pd.DataFrame(columns=[
            'player_id', 'severity', 'flagged_matches_count', 
            'total_matches_count', 'flag_reasons'
        ])
        return {}, empty_flat

    # 1. Apply match-level rule checks
    df_checks = df.copy()
    df_checks['rule_flags'] = df_checks.apply(check_match_rules, axis=1)
    
    # 2. Apply statistical Z-score checks
    df_checks['stat_flags'] = compute_historical_zscores(df_checks)
    
    # Combine all flags for each match
    df_checks['all_flags'] = df_checks['rule_flags'] + df_checks['stat_flags']
    
    # 3. Aggregate results per player
    player_stats = df_checks.groupby('player_id')
    flagged_players_map = {}
    
    for player_id, group in player_stats:
        total_matches = len(group)
        # Find matches with any flags
        flagged_matches = group[group['all_flags'].apply(len) > 0]
        
        if flagged_matches.empty:
            continue
            
        # Collect all unique reason strings
        reasons_set = set()
        for flag_list in flagged_matches['all_flags']:
            for flag in flag_list:
                reasons_set.add(flag)
                
        reasons = sorted(list(reasons_set))
        
        # Determine raw severity from match flags
        severity_candidates = []
        gameplay_flagged_count = 0
        
        for idx, row in flagged_matches.iterrows():
            # Gameplay rules (Rule 1-4)
            rule_flags = row['rule_flags']
            has_gameplay = False
            for rf in rule_flags:
                if "Score rate spike" in rf or "High-kill zero-death" in rf:
                    severity_candidates.append("High")
                    has_gameplay = True
                elif "Short match" in rf or "Extreme kills" in rf:
                    severity_candidates.append("Medium")
                    has_gameplay = True
                elif "Ping anomaly" in rf:
                    severity_candidates.append("Low")
            
            # Statistical rules (Z-score)
            stat_flags = row['stat_flags']
            if stat_flags:
                severity_candidates.append("Low")
                
            if has_gameplay:
                gameplay_flagged_count += 1
                
        # Base severity: highest of candidates (High > Medium > Low)
        if "High" in severity_candidates:
            base_severity = "High"
        elif "Medium" in severity_candidates:
            base_severity = "Medium"
        else:
            base_severity = "Low"
            
        # Escalation Rule:
        # If player has >= 5 matches AND > 50% of them triggered gameplay cheat rules, escalate to High
        if total_matches >= 5 and (gameplay_flagged_count / total_matches) > 0.5:
            if base_severity != "High":
                base_severity = "High"
                reasons.append("Escalation: Repeated gameplay anomalies across multiple matches (>50%)")
                
        flagged_players_map[player_id] = {
            'severity': base_severity,
            'reasons': reasons,
            'flagged_matches_count': len(flagged_matches),
            'total_matches_count': total_matches
        }
        
    # Convert map to flat dataframe
    flat_rows = []
    for pid, info in flagged_players_map.items():
        flat_rows.append({
            'player_id': pid,
            'severity': info['severity'],
            'flagged_matches_count': info['flagged_matches_count'],
            'total_matches_count': info['total_matches_count'],
            'flag_reasons': "; ".join(info['reasons'])
        })
        
    flat_df = pd.DataFrame(flat_rows)
    if not flat_df.empty:
        # Sort by severity severity hierarchy (High, Medium, Low) then flagged_matches_count
        severity_order = {'High': 0, 'Medium': 1, 'Low': 2}
        flat_df['sev_rank'] = flat_df['severity'].map(severity_order)
        flat_df = flat_df.sort_values(by=['sev_rank', 'flagged_matches_count'], ascending=[True, False]).reset_index(drop=True)
        flat_df = flat_df.drop(columns=['sev_rank'])
    else:
        flat_df = pd.DataFrame(columns=[
            'player_id', 'severity', 'flagged_matches_count', 
            'total_matches_count', 'flag_reasons'
        ])
        
    return flagged_players_map, flat_df
