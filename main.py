import argparse
import os
import pandas as pd
from src.loader import load_and_clean_data
from src.suspicious import detect_suspicious_players
from src.leaderboard import generate_leaderboard
from src.matchmaking import generate_matchmaking_groups
from src.utils import ensure_directory_exists

def main():
    parser = argparse.ArgumentParser(description="Game Ops System CLI Runner")
    parser.add_argument(
        "--data", 
        type=argparse.FileType('r'), 
        default=os.path.join("data", "players.csv"),
        help="Path to the input players match CSV file (default: data/players.csv)"
    )
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default="output",
        help="Directory to save generated CSV reports (default: output)"
    )
    
    # Extract file path string from file type object
    args = parser.parse_args()
    data_path = args.data.name
    args.data.close()  # Close the handle opened by argparse
    
    output_dir = args.output_dir
    ensure_directory_exists(output_dir)

    print("=" * 80)
    print("                      GAME OPS PIPELINE RUNNER                      ")
    print("=" * 80)
    print(f"Loading data from: {data_path}")
    print(f"Output directory : {output_dir}")
    print("-" * 80)

    try:
        # Step 1: Load and clean data
        df = load_and_clean_data(data_path)
        
        # Step 2: Detect suspicious players
        flagged_players_map, suspicious_df = detect_suspicious_players(df)
        
        # Step 3: Generate leaderboards
        global_lb, region_lb = generate_leaderboard(df, flagged_players_map)
        
        # Step 4: Generate matchmaking groups
        lobbies_map, matchmaking_df = generate_matchmaking_groups(df, flagged_players_map)
        
        # Step 5: Export reports to CSV
        global_lb.to_csv(os.path.join(output_dir, "leaderboard_global.csv"), index=False)
        region_lb.to_csv(os.path.join(output_dir, "leaderboard_region.csv"), index=False)
        suspicious_df.to_csv(os.path.join(output_dir, "suspicious_players.csv"), index=False)
        matchmaking_df.to_csv(os.path.join(output_dir, "matchmaking_groups.csv"), index=False)
        
        # Step 6: Console reports
        print("\n" + "=" * 40)
        print("          SUSPICIOUS PLAYERS REPORT        ")
        print("=" * 40)
        if not suspicious_df.empty:
            print(suspicious_df.to_string(index=False))
        else:
            print("No suspicious players flagged.")

        print("\n" + "=" * 40)
        print("        GLOBAL LEADERBOARD (TOP 10)       ")
        print("=" * 40)
        if not global_lb.empty:
            print(global_lb.head(10).to_string(index=False))
        else:
            print("Leaderboard is empty.")

        print("\n" + "=" * 40)
        print("           MATCHMAKING SUGGESTIONS         ")
        print("=" * 40)
        if not matchmaking_df.empty:
            print(matchmaking_df.to_string(index=False))
        else:
            print("No match lobbies formed.")

        print("\n" + "=" * 80)
        print("                               PIPELINE SUMMARY                             ")
        print("-" * 80)
        print(f"Total Matches Processed     : {len(df)}")
        print(f"Total Unique Players        : {df['player_id'].nunique()}")
        print(f"Suspicious Players Flagged  : {len(suspicious_df)}")
        print(f"Match Lobbies Created       : {len(matchmaking_df)}")
        print(f"Files written successfully to '{output_dir}/'")
        print("=" * 80)

    except Exception as e:
        print(f"\n[ERROR] Pipeline run failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
