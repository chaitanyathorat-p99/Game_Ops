from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel, Field
import pandas as pd
import io
import os
from typing import List, Optional, Dict, Any

from src.loader import load_and_clean_data
from src.suspicious import detect_suspicious_players
from src.leaderboard import generate_leaderboard
from src.matchmaking import generate_matchmaking_groups

router = APIRouter()

# Global in-memory state
# We try to load data/players.csv on startup
DEFAULT_CSV_PATH = os.path.join("data", "players.csv")
current_df = pd.DataFrame()

def load_initial_data():
    global current_df
    if os.path.exists(DEFAULT_CSV_PATH):
        try:
            current_df = load_and_clean_data(DEFAULT_CSV_PATH)
            print(f"Loaded initial dataset from {DEFAULT_CSV_PATH}: {len(current_df)} rows.")
        except Exception as e:
            print(f"Warning: Failed to load initial data from {DEFAULT_CSV_PATH}: {e}")
            current_df = pd.DataFrame()
    else:
        current_df = pd.DataFrame()

# Initialize data on import
load_initial_data()

class ScoreSubmission(BaseModel):
    player_id: str = Field(..., example="P999")
    match_id: str = Field(..., example="M999")
    region: str = Field(..., example="India")
    device: str = Field(..., example="Android")
    ping: int = Field(..., ge=0, example=65)
    score: float = Field(..., ge=0, example=3500.0)
    kills: int = Field(..., ge=0, example=15)
    deaths: int = Field(..., ge=0, example=3)
    match_duration_seconds: int = Field(..., gt=0, example=400)

@router.get("/status")
def get_status():
    global current_df
    return {
        "is_loaded": not current_df.empty,
        "total_records": len(current_df),
        "unique_players": int(current_df['player_id'].nunique()) if not current_df.empty else 0
    }

@router.post("/upload-csv")
async def upload_csv(file: UploadFile = File(...)):
    global current_df
    try:
        contents = await file.read()
        # Parse into a dataframe
        raw_df = pd.read_csv(io.BytesIO(contents))
        
        # Save temp copy or write directly to data/players.csv to keep it persistent
        os.makedirs("data", exist_ok=True)
        with open(DEFAULT_CSV_PATH, "wb") as f:
            f.write(contents)
            
        # Run loader pipeline
        current_df = load_and_clean_data(DEFAULT_CSV_PATH)
        return {
            "status": "success",
            "message": f"Successfully uploaded and cleaned dataset. Loaded {len(current_df)} records."
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process CSV: {str(e)}")

@router.post("/submit-score")
def submit_score(data: ScoreSubmission):
    global current_df
    try:
        # Create a single row DataFrame
        new_row = pd.DataFrame([{
            'player_id': data.player_id.strip(),
            'match_id': data.match_id.strip(),
            'region': data.region.strip().title(),
            'device': data.device.strip().title(),
            'ping': int(data.ping),
            'score': float(data.score),
            'kills': int(data.kills),
            'deaths': int(data.deaths),
            'match_duration_seconds': int(data.match_duration_seconds)
        }])
        
        # Calculate derived fields
        new_row['score_per_second'] = new_row['score'] / new_row['match_duration_seconds']
        new_row['kd_ratio'] = new_row['kills'] / max(new_row['deaths'].iloc[0], 1)
        
        # If match already exists for player, drop it (deduplicate)
        if not current_df.empty:
            match_mask = (current_df['player_id'] == new_row['player_id'].iloc[0]) & \
                         (current_df['match_id'] == new_row['match_id'].iloc[0])
            if match_mask.any():
                current_df = current_df[~match_mask]
                
        # Append new row
        current_df = pd.concat([current_df, new_row], ignore_index=True)
        
        # Detect if this submission itself triggers immediate cheat rules
        from src.suspicious import check_match_rules
        triggered_rules = check_match_rules(new_row.iloc[0])
        
        # Also run global detection to check if player overall is flagged
        flagged_players_map, _ = detect_suspicious_players(current_df)
        player_flag = flagged_players_map.get(data.player_id)
        
        is_flagged = len(triggered_rules) > 0 or (player_flag is not None)
        severity = player_flag['severity'] if player_flag else "None"
        reasons = player_flag['reasons'] if player_flag else triggered_rules
        
        # Save updated dataframe back to file
        current_df.to_csv(DEFAULT_CSV_PATH, index=False)
        
        return {
            "status": "flagged" if is_flagged else "clean",
            "player_id": data.player_id,
            "severity": severity,
            "reasons": reasons,
            "message": "Score submission processed successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit score: {str(e)}")

@router.get("/leaderboard")
def get_leaderboard(region: Optional[str] = None):
    global current_df
    if current_df.empty:
        return {"global": [], "regional": []}
        
    flagged_players_map, _ = detect_suspicious_players(current_df)
    global_lb, region_lb = generate_leaderboard(current_df, flagged_players_map)
    
    # Filter regional if query param specified
    if region:
        region_title = region.strip().title()
        region_lb = region_lb[region_lb['primary_region'] == region_title]
        
    # Replace NaN in rank with None for JSON compatibility
    global_lb_dict = global_lb.replace({np.nan: None}).to_dict(orient='records')
    region_lb_dict = region_lb.replace({np.nan: None}).to_dict(orient='records')
    
    return {
        "global": global_lb_dict,
        "regional": region_lb_dict
    }

@router.get("/flagged-players")
def get_flagged_players():
    global current_df
    if current_df.empty:
        return []
        
    _, suspicious_df = detect_suspicious_players(current_df)
    return suspicious_df.to_dict(orient='records')

@router.get("/matchmaking")
def get_matchmaking():
    global current_df
    if current_df.empty:
        return []
        
    flagged_players_map, _ = detect_suspicious_players(current_df)
    _, matchmaking_df = generate_matchmaking_groups(current_df, flagged_players_map)
    
    return matchmaking_df.to_dict(orient='records')

@router.post("/reset")
def reset_data():
    global current_df
    # Reload default data
    load_initial_data()
    return {"status": "success", "message": "In-memory database reset to initial values."}

@router.get("/download/{report_name}")
def download_report(report_name: str):
    from fastapi.responses import FileResponse
    report_mapping = {
        "leaderboard_global": "output/leaderboard_global.csv",
        "leaderboard_region": "output/leaderboard_region.csv",
        "suspicious_players": "output/suspicious_players.csv",
        "matchmaking_groups": "output/matchmaking_groups.csv",
        "players": "data/players.csv"
    }
    
    if report_name not in report_mapping:
        raise HTTPException(status_code=404, detail="Report not found")
        
    file_path = report_mapping[report_name]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail=f"File {file_path} not generated yet. Please run the pipeline or interact with the dashboard first.")
        
    return FileResponse(
        path=file_path, 
        filename=os.path.basename(file_path), 
        media_type="text/csv"
    )
