import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional


def load_data(json_file: str) -> pd.DataFrame:
    """Load the game data from JSON"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Calculate total fouls per game
    df['total_fouls'] = df['home_fouls'] + df['visitor_fouls']
    
    return df


def find_common_games(df: pd.DataFrame, official1: str, official2: str) -> pd.DataFrame:
    """Find games where both officials worked together"""
    return df[df['officials'].apply(lambda x: official1 in x and official2 in x)]


def compare_officials(df: pd.DataFrame, officials: List[str], 
                     output_file: Optional[str] = None, min_games: int = 5) -> pd.DataFrame:
    """
    Compare fouls statistics for a list of officials
    
    Args:
        df: DataFrame with game data
        officials: List of official names to compare
        output_file: Path to save comparison CSV (optional)
        min_games: Minimum number of games an official must have worked to be included
        
    Returns:
        DataFrame with comparison data
    """
    comparison_data = []
    
    for official in officials:
        # Get games where this official worked
        official_games = df[df['officials'].apply(lambda x: official in x)]
        
        # Calculate statistics
        total_games = len(official_games)
        avg_total_fouls = official_games['total_fouls'].mean()
        max_fouls = official_games['total_fouls'].max()
        min_fouls = official_games['total_fouls'].min()
        std_fouls = official_games['total_fouls'].std()
        
        # Home vs visitor fouls
        avg_home_fouls = official_games['home_fouls'].mean()
        avg_visitor_fouls = official_games['visitor_fouls'].mean()
        home_visitor_diff = avg_home_fouls - avg_visitor_fouls
        
        # Technical fouls
        avg_technicals = (official_games['home_technicals'] + official_games['visitor_technicals']).mean()
        
        # Add to comparison data
        comparison_data.append({
            'official': official,
            'games_worked': total_games,
            'avg_fouls_per_game': avg_total_fouls,
            'min_fouls': min_fouls,
            'max_fouls': max_fouls,
            'std_fouls': std_fouls,
            'avg_home_fouls': avg_home_fouls,
            'avg_visitor_fouls': avg_visitor_fouls,
            'home_visitor_diff': home_visitor_diff,
            'avg_technicals': avg_technicals
        })
    
    # Create DataFrame
    comparison_df = pd.DataFrame(comparison_data)
    
    # Filter to include only officials with minimum number of games
    comparison_df = comparison_df[comparison_df['games_worked'] >= min_games]
    
    # Calculate overall average and standard deviation
    overall_avg = comparison_df['avg_fouls_per_game'].mean()
    overall_std = comparison_df['avg_fouls_per_game'].std()
    
    # Calculate z-score (number of standard deviations from mean)
    comparison_df['z_score'] = (comparison_df['avg_fouls_per_game'] - overall_avg) / overall_std
    
    # Add percentile ranking
    comparison_df['percentile'] = comparison_df['avg_fouls_per_game'].rank(pct=True) * 100
    
    # Sort by average fouls
    comparison_df = comparison_df.sort_values(by='avg_fouls_per_game', ascending=False)
    
    # Save to CSV if requested
    if output_file:
        comparison_df.to_csv(output_file, index=False)
        print(f"Comparison data saved to {output_file} with {len(comparison_df)} officials")
    
    return comparison_df


def plot_official_distributions(df: pd.DataFrame, officials: List[str], output_file: Optional[str] = None):
    """
    Create box plots showing the distribution of fouls for each official
    
    Args:
        df: DataFrame with game data
        officials: List of official names to compare
        output_file: Path to save the plot (optional)
    """
    # Prepare data for plotting
    plot_data = []
    
    for official in officials:
        # Get games where this official worked
        official_games = df[df['officials'].apply(lambda x: official in x)]
        
        # Add each game to the plot data
        for _, game in official_games.iterrows():
            plot_data.append({
                'Official': official,
                'Total Fouls': game['total_fouls']
            })
    
    # Convert to DataFrame
    plot_df = pd.DataFrame(plot_data)
    
    # Create the plot
    plt.figure(figsize=(12, 8))
    
    # Use seaborn for prettier plots
    sns.boxplot(x='Official', y='Total Fouls', data=plot_df)
    sns.swarmplot(x='Official', y='Total Fouls', data=plot_df, color='black', alpha=0.5, size=3)
    
    plt.title('Distribution of Total Fouls Per Game by Official')
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def analyze_official_partners(df: pd.DataFrame, official: str, n_top: int = 5, 
                            min_games_together: int = 3) -> pd.DataFrame:
    """
    Analyze how an official's average fouls change depending on who they work with
    
    Args:
        df: DataFrame with game data
        official: Name of the official to analyze
        n_top: Number of top partners to show
        min_games_together: Minimum games worked together to include partner
        
    Returns:
        DataFrame with partner analysis
    """
    print(f"DEBUG: Analyzing partners for '{official}'")
    
    # Get all games for this official
    official_games = df[df['officials'].apply(lambda x: official in x)]
    print(f"DEBUG: Found {len(official_games)} games for {official}")
    
    if len(official_games) == 0:
        print(f"WARNING: No games found for official '{official}'")
        return pd.DataFrame()
    
    # Get the overall average fouls for this official
    overall_avg = official_games['total_fouls'].mean()
    print(f"DEBUG: Overall average fouls for {official}: {overall_avg:.2f}")
    
    # Find all partners this official has worked with
    partners_data = []
    
    for _, game in official_games.iterrows():
        partners = [partner for partner in game['officials'] if partner != official]
        
        for partner in partners:
            partners_data.append({
                'partner': partner,
                'game_id': game['game_id'],
                'total_fouls': game['total_fouls']
            })
    
    print(f"DEBUG: Found {len(partners_data)} partner-game combinations")
    
    if len(partners_data) == 0:
        print(f"WARNING: No partners found for official '{official}'")
        return pd.DataFrame()
    
    # Group by partner and calculate average fouls
    partners_df = pd.DataFrame(partners_data)
    partner_stats = partners_df.groupby('partner').agg(
        games=('game_id', 'count'),
        avg_fouls=('total_fouls', 'mean')
    ).reset_index()
    
    print(f"DEBUG: Found {len(partner_stats)} unique partners")
    print(f"DEBUG: Partners before filtering (min {min_games_together} games): {len(partner_stats)}")
    
    # Calculate difference from official's overall average
    partner_stats['diff_from_avg'] = partner_stats['avg_fouls'] - overall_avg
    
    # Sort to find partners with highest and lowest fouls
    partner_stats = partner_stats.sort_values(by='avg_fouls', ascending=False)
    
    # Filter to include only partners with a minimum number of games together
    partner_stats_filtered = partner_stats[partner_stats['games'] >= min_games_together]
    print(f"DEBUG: Partners after filtering (min {min_games_together} games): {len(partner_stats_filtered)}")
    
    return partner_stats_filtered


def find_team_names(df: pd.DataFrame, search_terms: List[str] = None):
    """Helper function to find team names in the dataset"""
    all_teams = set(df['home'].tolist() + df['visitor'].tolist())
    
    if search_terms:
        print(f"Searching for teams containing: {search_terms}")
        for term in search_terms:
            matches = [team for team in all_teams if term.lower() in team.lower()]
            if matches:
                print(f"  '{term}' matches: {sorted(matches)}")
            else:
                print(f"  '{term}' matches: None found")
    else:
        print(f"All {len(all_teams)} teams in dataset:")
        for team in sorted(all_teams):
            print(f"  - {team}")


def debug_official_names(df: pd.DataFrame, target_officials: List[str]):
    """Debug function to check if official names exist and find similar ones"""
    all_officials = set()
    for officials_list in df['officials']:
        for official in officials_list:
            if official:  # Skip empty strings
                all_officials.add(official)
    
    print("\n=== DEBUGGING OFFICIAL NAMES ===")
    for target in target_officials:
        print(f"\nChecking for '{target}':")
        if target in all_officials:
            games_count = len(df[df['officials'].apply(lambda x: target in x)])
            print(f"  ✓ FOUND: {games_count} games")
        else:
            print(f"  ✗ NOT FOUND")
            # Find similar names
            similar = [name for name in all_officials if target.lower() in name.lower() or name.lower() in target.lower()]
            if similar:
                print(f"  Similar names found: {similar[:5]}")  # Show first 5 similar names


def main():
    """Main function to run the analysis"""
    json_file = "officials_202425.json"
    df = load_data(json_file)
    print(f"Loaded {len(df)} games from {json_file}")
    
    # Define the list of teams to analyze (modify this list as needed)
    target_teams = [
        "Maryland",
        "Michigan", 
        "Rutgers",
        "Iowa",
        "Illinois",
        "Wisconsin",
        "Purdue",
        "Michigan St.",
        "Indiana",
        "Ohio St.",
        "Penn St.",
        "Nebraska",
        "Northwestern",
        "Minnesota",
        "Southern California",
        "UCLA",
        "Washington",
        "Oregon"
    ]
    
    # Uncomment the line below to see all team names in your dataset
    # find_team_names(df)
    
    # Uncomment the line below to search for specific team name patterns
    # find_team_names(df, ["Duke", "Carolina", "Kentucky", "Kansas"])
    
    # Filter dataframe to only include games involving the target teams
    print(f"\nFiltering games to only include teams: {target_teams}")
    df_filtered = df[
        df['home'].isin(target_teams) & df['visitor'].isin(target_teams)
    ]
    
    print(f"Filtered from {len(df)} total games to {len(df_filtered)} games involving target teams")
    
    if len(df_filtered) == 0:
        print("ERROR: No games found for the specified teams. Check team names.")
        print("Available teams in dataset:")
        all_teams = set(df['home'].tolist() + df['visitor'].tolist())
        for team in sorted(all_teams)[:20]:  # Show first 20 teams
            print(f"  - {team}")
        return
    
    # Use the filtered dataframe for all subsequent analysis
    df = df_filtered
    
    # Get a list of all unique officials from filtered games
    all_officials = set()
    for officials_list in df['officials']:
        for official in officials_list:
            if official:  # Skip empty strings
                all_officials.add(official)
    
    print(f"Found {len(all_officials)} unique officials in games involving target teams")
    
    # Compare all officials
    print("\nComparing all officials (this may take a moment):")
    comparison_df = compare_officials(df, list(all_officials), "official_comparison_teams.csv")
    
    # Get actual high and low foul officials from the data
    print("\n=== TOP 10 HIGHEST FOUL OFFICIALS ===")
    top_10_high = comparison_df.head(10)
    print(top_10_high[['official', 'games_worked', 'avg_fouls_per_game']].to_string(index=False))
    
    print("\n=== TOP 10 LOWEST FOUL OFFICIALS ===")
    bottom_10_low = comparison_df.tail(10)
    print(bottom_10_low[['official', 'games_worked', 'avg_fouls_per_game']].to_string(index=False))
    
    # Use actual officials from the data instead of hardcoded names
    high_foul_officials = top_10_high['official'].head(3).tolist()
    low_foul_officials = bottom_10_low['official'].tail(3).tolist()
    
    print(f"\nUsing HIGH foul officials: {high_foul_officials}")
    print(f"Using LOW foul officials: {low_foul_officials}")
    
    # Debug the original hardcoded names (if you want to see why they didn't work)
    original_high = ["Keith Harris", "Zackary Clark", "Chris Iannucci"]
    original_low = ["Christopher Helinski", "Nicholas Lancaster", "Steve Call"]
    debug_official_names(df, original_high + original_low)
    
    # For visualization, use the actual high/low officials
    visualization_officials = high_foul_officials + low_foul_officials
    
    # Plot distributions
    plot_official_distributions(df, visualization_officials, "official_fouls_distribution.png")
    
    # Analyze partner effects for a high-foul official
    high_official = high_foul_officials[0]
    print(f"\n=== ANALYZING PARTNERS FOR {high_official.upper()} (HIGH-FOUL OFFICIAL) ===")
    high_partners = analyze_official_partners(df, high_official, min_games_together=2)  # Lowered threshold
    if not high_partners.empty:
        output_file = f"{high_official.replace(' ', '_').replace('.', '')}_partners.csv"
        high_partners.to_csv(output_file, index=False)
        print(f"Saved partner analysis to {output_file}")
        print(high_partners.head(5).to_string(index=False))
    else:
        print("No partner data generated!")
    
    # Analyze partner effects for a low-foul official
    low_official = low_foul_officials[0]
    print(f"\n=== ANALYZING PARTNERS FOR {low_official.upper()} (LOW-FOUL OFFICIAL) ===")
    low_partners = analyze_official_partners(df, low_official, min_games_together=2)  # Lowered threshold
    if not low_partners.empty:
        output_file = f"{low_official.replace(' ', '_').replace('.', '')}_partners.csv"
        low_partners.to_csv(output_file, index=False)
        print(f"Saved partner analysis to {output_file}")
        print(low_partners.head(5).to_string(index=False))
    else:
        print("No partner data generated!")
    
    # Find any games where a high-foul and low-foul official worked together
    print(f"\n=== CHECKING FOR COMMON GAMES ===")
    for high_off in high_foul_officials:
        for low_off in low_foul_officials:
            common_games = find_common_games(df, high_off, low_off)
            if len(common_games) > 0:
                print(f"\nFound {len(common_games)} games where {high_off} and {low_off} worked together")
                print(f"Average fouls in these games: {common_games['total_fouls'].mean():.2f}")
                
                # Compare to their individual averages
                high_off_avg = df[df['officials'].apply(lambda x: high_off in x)]['total_fouls'].mean()
                low_off_avg = df[df['officials'].apply(lambda x: low_off in x)]['total_fouls'].mean()
                print(f"{high_off}'s average: {high_off_avg:.2f}, {low_off}'s average: {low_off_avg:.2f}")


if __name__ == "__main__":
    main()