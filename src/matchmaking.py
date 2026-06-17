import pandas as pd
import numpy as np
from typing import Dict, Any, List, Tuple, Set

def get_ping_band(avg_ping: float) -> str:
    if avg_ping <= 80:
        return "LowPing"
    elif avg_ping <= 150:
        return "MedPing"
    else:
        return "HighPing"

def generate_matchmaking_groups(
    df: pd.DataFrame,
    flagged_players: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, List[Dict[str, Any]]], pd.DataFrame]:
    """
    Creates matchmaking lobbies based on Region, Ping Band, and Skill Tier.
    Excludes High severity cheaters and isolates Medium severity players.
    
    Returns:
    - Dict[str, List[Dict[str, Any]]]: Map of lobby_name -> List of player details
    - pd.DataFrame: Flat DataFrame for CSV output
    """
    if df.empty:
        empty_df = pd.DataFrame(columns=[
            'lobby_name', 'region', 'ping_band', 'skill_tier', 
            'player_count', 'status', 'player_ids'
        ])
        return {}, empty_df

    # 1. Aggregate player stats
    def get_mode(series):
        modes = series.mode()
        return modes.iloc[0] if not modes.empty else "Unknown"

    player_stats = df.groupby('player_id').agg(
        avg_score=('score', 'mean'),
        avg_kills=('kills', 'mean'),
        avg_deaths=('deaths', 'mean'),
        avg_ping=('ping', 'mean'),
        primary_region=('region', get_mode),
        device=('device', get_mode)
    ).reset_index()

    # 2. Compute skill scores
    # skill_score = avg_score * 0.5 + avg_kills * 3.0 - avg_deaths * 1.0
    player_stats['skill_score'] = (
        player_stats['avg_score'] * 0.5 + 
        player_stats['avg_kills'] * 3.0 - 
        player_stats['avg_deaths'] * 1.0
    )

    # 3. Partition players by flagging severity
    high_cheaters = set()
    med_cheaters = set()
    low_cheaters = set()
    
    for pid, info in flagged_players.items():
        sev = info.get('severity', 'Low')
        if sev == 'High':
            high_cheaters.add(pid)
        elif sev == 'Medium':
            med_cheaters.add(pid)
        else:
            low_cheaters.add(pid)

    # Exclude high severity cheaters
    active_players = player_stats[~player_stats['player_id'].isin(high_cheaters)].copy()
    
    # Isolate medium severity cheaters
    isolated_pool = active_players[active_players['player_id'].isin(med_cheaters)].copy()
    
    # Standard matching pool (clean and low severity)
    matching_pool = active_players[~active_players['player_id'].isin(med_cheaters)].copy()

    # Add tag for display
    def get_player_tag(row):
        pid = row['player_id']
        if pid in low_cheaters:
            return f"{pid} (Flagged: Low)"
        return pid

    matching_pool['player_label'] = matching_pool.apply(get_player_tag, axis=1)
    isolated_pool['player_label'] = isolated_pool['player_id'] + " (Isolated)"

    lobbies: Dict[str, List[Dict[str, Any]]] = {}

    # 4. Generate Standard Lobbies (3-Pass Bucketing)
    if not matching_pool.empty:
        # Pass 1 & 2: Region and Ping Band
        matching_pool['ping_band'] = matching_pool['avg_ping'].apply(get_ping_band)
        
        # Group by Region and Ping Band
        grouped = matching_pool.groupby(['primary_region', 'ping_band'])
        
        for (region, ping_band), group in grouped:
            n_players = len(group)
            
            # Pass 3: Skill Tier
            if n_players >= 6:
                # Calculate tier thresholds
                sorted_grp = group.sort_values(by='skill_score').reset_index(drop=True)
                # Assign tiers by percentile splits (approx 33% each)
                # cut on quantiles
                q33 = sorted_grp['skill_score'].quantile(0.33)
                q66 = sorted_grp['skill_score'].quantile(0.66)
                
                def get_skill_tier(score):
                    if score <= q33:
                        return "Beginner"
                    elif score <= q66:
                        return "Intermediate"
                    else:
                        return "Advanced"
                        
                sorted_grp['skill_tier'] = sorted_grp['skill_score'].apply(get_skill_tier)
                
                # Create separate lobbies for each tier
                tier_groups = sorted_grp.groupby('skill_tier')
                for tier, tier_group in tier_groups:
                    lobby_name = f"{region}_{ping_band}_{tier}"
                    lobbies[lobby_name] = tier_group.to_dict(orient='records')
            else:
                # If pool is small (< 6), keep as Mixed skill tier
                lobby_name = f"{region}_{ping_band}_Mixed"
                lobbies[lobby_name] = group.to_dict(orient='records')

    # 5. Generate Isolated Lobby for Medium severity players
    if not isolated_pool.empty:
        lobby_name = "Isolated_UnderReview"
        lobbies[lobby_name] = isolated_pool.to_dict(orient='records')

    # 6. Convert lobbies to flat export DataFrame
    flat_rows = []
    for lobby_name, players in lobbies.items():
        player_labels = [p['player_label'] for p in players]
        player_count = len(players)
        
        # Lobbies with >= 4 players are 'Ready', otherwise 'Waiting' (except isolated pool which is always 'Isolated')
        if lobby_name == "Isolated_UnderReview":
            status = "Isolated"
            region = "Global"
            ping_band = "Mixed"
            skill_tier = "Under Review"
        else:
            status = "Ready" if player_count >= 4 else "Waiting"
            # Parse region, ping, skill from name
            parts = lobby_name.split('_')
            region = parts[0]
            ping_band = parts[1]
            skill_tier = parts[2]

        flat_rows.append({
            'lobby_name': lobby_name,
            'region': region,
            'ping_band': ping_band,
            'skill_tier': skill_tier,
            'player_count': player_count,
            'status': status,
            'player_ids': ", ".join(player_labels)
        })

    flat_df = pd.DataFrame(flat_rows)
    if not flat_df.empty:
        # Sort by lobby_name
        flat_df = flat_df.sort_values(by='lobby_name').reset_index(drop=True)
    else:
        flat_df = pd.DataFrame(columns=[
            'lobby_name', 'region', 'ping_band', 'skill_tier', 
            'player_count', 'status', 'player_ids'
        ])

    return lobbies, flat_df
