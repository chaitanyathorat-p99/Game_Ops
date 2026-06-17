import pandas as pd
import numpy as np
from typing import List, Set, Dict, Any, Tuple

def aggregate_player_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregates match-level data to player-level summaries.
    Computes total_score, total_kills, total_deaths, matches_played,
    avg_score_per_match, and primary_region (mode of regions played).
    """
    if df.empty:
        return pd.DataFrame(columns=[
            'player_id', 'total_score', 'total_kills', 'total_deaths',
            'matches_played', 'avg_score_per_match', 'primary_region'
        ])

    # Custom aggregation for primary region (mode)
    def get_primary_region(series):
        modes = series.mode()
        return modes.iloc[0] if not modes.empty else "Unknown"

    agg_df = df.groupby('player_id').agg(
        total_score=('score', 'sum'),
        total_kills=('kills', 'sum'),
        total_deaths=('deaths', 'sum'),
        matches_played=('match_id', 'count'),
        primary_region=('region', get_primary_region)
    ).reset_index()

    agg_df['avg_score_per_match'] = agg_df['total_score'] / agg_df['matches_played']
    
    return agg_df

def generate_leaderboard(
    df: pd.DataFrame, 
    flagged_players: Dict[str, Dict[str, Any]]
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates global and region-wise leaderboards.
    
    Parameters:
    - df: The clean match-level DataFrame.
    - flagged_players: Dict mapping player_id -> flag metadata (e.g. {'severity': 'High', 'reasons': [...]})
    
    Returns:
    - Tuple[pd.DataFrame, pd.DataFrame]: (global_leaderboard, region_leaderboard)
    """
    # 1. Aggregate stats
    stats_df = aggregate_player_stats(df)
    
    if stats_df.empty:
        empty_lb = pd.DataFrame(columns=[
            'rank', 'player_id', 'total_score', 'total_kills', 'total_deaths',
            'matches_played', 'primary_region', 'avg_score_per_match', 'status'
        ])
        return empty_lb, empty_lb

    # 2. Split into clean and flagged sets
    flagged_ids = set(flagged_players.keys())
    
    clean_players = stats_df[~stats_df['player_id'].isin(flagged_ids)].copy()
    flagged_players_df = stats_df[stats_df['player_id'].isin(flagged_ids)].copy()
    
    # 3. Sort clean players using tie-breakers
    # - total_score (descending)
    # - total_deaths (ascending) -> fewer is better, so ascending=True
    # - total_kills (descending)
    # - matches_played (descending)
    clean_players = clean_players.sort_values(
        by=['total_score', 'total_deaths', 'total_kills', 'matches_played'],
        ascending=[False, True, False, False]
    ).reset_index(drop=True)
    
    # Assign global ranks to clean players
    clean_players['rank'] = clean_players.index + 1
    clean_players['status'] = 'clean'
    
    # 4. Sort flagged players (for display consistency at the bottom)
    flagged_players_df = flagged_players_df.sort_values(
        by=['total_score', 'total_deaths', 'total_kills', 'matches_played'],
        ascending=[False, True, False, False]
    ).reset_index(drop=True)
    
    # Flagged players get no numerical rank and status is 'under_review'
    flagged_players_df['rank'] = np.nan
    flagged_players_df['status'] = 'under_review'
    
    # 5. Combine for Global Leaderboard
    global_lb = pd.concat([clean_players, flagged_players_df], ignore_index=True)
    
    # Reorder columns for presentation
    columns_order = [
        'rank', 'player_id', 'total_score', 'total_kills', 'total_deaths',
        'matches_played', 'primary_region', 'avg_score_per_match', 'status'
    ]
    global_lb = global_lb[columns_order]
    
    # 6. Generate Region-Wise Leaderboard
    # Group clean players by region and assign ranks within each region
    region_lb_list = []
    
    # Get all unique regions present
    all_regions = stats_df['primary_region'].unique()
    
    for r in all_regions:
        r_clean = clean_players[clean_players['primary_region'] == r].copy()
        r_clean = r_clean.sort_values(
            by=['total_score', 'total_deaths', 'total_kills', 'matches_played'],
            ascending=[False, True, False, False]
        ).reset_index(drop=True)
        r_clean['rank'] = r_clean.index + 1
        
        r_flagged = flagged_players_df[flagged_players_df['primary_region'] == r].copy()
        r_flagged['rank'] = np.nan
        
        region_lb_list.append(pd.concat([r_clean, r_flagged], ignore_index=True))
        
    if region_lb_list:
        region_lb = pd.concat(region_lb_list, ignore_index=True)
        # Sort by primary_region, then rank (nans will sort to the bottom within region by default or we specify)
        region_lb = region_lb.sort_values(
            by=['primary_region', 'rank', 'total_score'],
            ascending=[True, True, False],
            na_position='last'
        ).reset_index(drop=True)
        region_lb = region_lb[columns_order]
    else:
        region_lb = pd.DataFrame(columns=columns_order)
        
    return global_lb, region_lb
