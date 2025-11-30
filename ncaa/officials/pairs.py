import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Optional, Tuple
from itertools import combinations


def load_data(json_file: str) -> pd.DataFrame:
    """Load the game data from JSON"""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Calculate total fouls per game
    df['total_fouls'] = df['home_fouls'] + df['visitor_fouls']
    
    return df


def load_multiple_seasons(json_files: List[str]) -> pd.DataFrame:
    """
    Load and combine data from multiple season JSON files
    
    Args:
        json_files: List of JSON file paths
        
    Returns:
        Combined DataFrame with season information
    """
    all_data = []
    
    for json_file in json_files:
        print(f"Loading {json_file}...")
        try:
            df = load_data(json_file)
            
            # Extract season from filename (assuming format like "officials_202425.json")
            season = json_file.split('_')[-1].replace('.json', '')
            df['season'] = season
            
            all_data.append(df)
            print(f"  Loaded {len(df)} games from {season}")
            
        except FileNotFoundError:
            print(f"  Warning: File {json_file} not found, skipping...")
        except Exception as e:
            print(f"  Error loading {json_file}: {e}")
    
    if not all_data:
        raise ValueError("No data files could be loaded")
    
    # Combine all seasons
    combined_df = pd.concat(all_data, ignore_index=True)
    print(f"\nCombined total: {len(combined_df)} games across {len(all_data)} seasons")
    
    return combined_df


def create_partnership_signature(official1: str, official2: str) -> str:
    """
    Create a consistent signature for a pair of officials regardless of order
    
    Args:
        official1: First official name
        official2: Second official name
        
    Returns:
        String signature with names in alphabetical order, separated by ' & '
    """
    officials = sorted([official1.strip(), official2.strip()])
    return ' & '.join(officials)


def get_all_partnerships_from_game(officials: List[str]) -> List[str]:
    """
    Get all possible two-official partnerships from a game's official list
    
    Args:
        officials: List of official names in a game
        
    Returns:
        List of partnership signatures
    """
    partnerships = []
    
    # Generate all combinations of 2 officials from the game
    for combo in combinations(officials, 2):
        partnership_sig = create_partnership_signature(combo[0], combo[1])
        partnerships.append(partnership_sig)
    
    return partnerships


def analyze_official_partnerships(df: pd.DataFrame, min_games: int = 5, by_season: bool = False) -> pd.DataFrame:
    """
    Analyze statistics for two-official partnerships
    
    Args:
        df: DataFrame with game data
        min_games: Minimum number of games a partnership must have worked together
        by_season: Whether to analyze partnerships by season or across all seasons
        
    Returns:
        DataFrame with partnership statistics
    """
    partnership_data = []
    
    if by_season:
        # Analyze each season separately
        seasons = df['season'].unique()
        for season in seasons:
            season_df = df[df['season'] == season]
            season_partnership_data = _analyze_partnerships_for_dataset(season_df, min_games, season)
            partnership_data.extend(season_partnership_data)
    else:
        # Analyze across all seasons combined
        season_partnership_data = _analyze_partnerships_for_dataset(df, min_games, "All Seasons")
        partnership_data.extend(season_partnership_data)
    
    # Create DataFrame
    partnership_df = pd.DataFrame(partnership_data)
    
    if len(partnership_df) == 0:
        print("No partnerships found meeting the minimum games criteria")
        return partnership_df
    
    # Calculate overall statistics for comparison
    overall_avg = partnership_df['avg_fouls_per_game'].mean()
    overall_std = partnership_df['avg_fouls_per_game'].std()
    
    # Calculate z-score (number of standard deviations from mean)
    if overall_std > 0:
        partnership_df['z_score'] = (partnership_df['avg_fouls_per_game'] - overall_avg) / overall_std
    else:
        partnership_df['z_score'] = 0
    
    # Add percentile ranking
    partnership_df['percentile'] = partnership_df['avg_fouls_per_game'].rank(pct=True) * 100
    
    # Sort by average fouls
    partnership_df = partnership_df.sort_values(by='avg_fouls_per_game', ascending=False)
    
    return partnership_df


def _analyze_partnerships_for_dataset(df: pd.DataFrame, min_games: int, season_label: str) -> List[Dict]:
    """
    Helper function to analyze partnerships for a specific dataset
    
    Args:
        df: DataFrame with game data
        min_games: Minimum number of games
        season_label: Label for the season/dataset
        
    Returns:
        List of partnership data dictionaries
    """
    partnership_data = []
    partnership_games = {}
    
    for _, game in df.iterrows():
        officials = game['officials']
        
        # Get all partnerships from this game
        partnerships = get_all_partnerships_from_game(officials)
        
        for partnership_sig in partnerships:
            if partnership_sig not in partnership_games:
                partnership_games[partnership_sig] = []
            partnership_games[partnership_sig].append(game)
    
    print(f"  Found {len(partnership_games)} unique two-official partnerships in {season_label}")
    
    # Calculate statistics for each partnership
    for partnership_sig, games in partnership_games.items():
        if len(games) >= min_games:
            games_df = pd.DataFrame(games)
            
            # Basic statistics
            total_games = len(games_df)
            avg_total_fouls = games_df['total_fouls'].mean()
            max_fouls = games_df['total_fouls'].max()
            min_fouls = games_df['total_fouls'].min()
            std_fouls = games_df['total_fouls'].std()
            
            # Home vs visitor fouls
            avg_home_fouls = games_df['home_fouls'].mean()
            avg_visitor_fouls = games_df['visitor_fouls'].mean()
            home_visitor_diff = avg_home_fouls - avg_visitor_fouls
            
            # Technical fouls
            avg_technicals = (games_df['home_technicals'] + games_df['visitor_technicals']).mean()
            
            # Extract individual official names
            officials_list = partnership_sig.split(' & ')
            
            partnership_data.append({
                'season': season_label,
                'partnership_signature': partnership_sig,
                'official_1': officials_list[0],
                'official_2': officials_list[1],
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
    
    return partnership_data


def compare_individual_vs_partnership_performance(df: pd.DataFrame, partnership_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare how officials perform individually vs. as part of specific partnerships
    
    Args:
        df: DataFrame with game data
        partnership_df: DataFrame with partnership statistics
        
    Returns:
        DataFrame comparing individual vs partnership performance
    """
    comparison_data = []
    
    # Get individual official statistics first
    individual_stats = {}
    all_officials = set()
    
    for officials_list in df['officials']:
        for official in officials_list:
            if official.strip():
                all_officials.add(official.strip())
    
    # Calculate individual averages
    for official in all_officials:
        official_games = df[df['officials'].apply(lambda x: official in x)]
        if len(official_games) > 0:
            individual_stats[official] = official_games['total_fouls'].mean()
    
    # Compare partnership performance to individual averages
    for _, partnership in partnership_df.iterrows():
        officials = [partnership['official_1'], partnership['official_2']]
        
        # Calculate average individual performance
        individual_avgs = []
        for official in officials:
            if official in individual_stats:
                individual_avgs.append(individual_stats[official])
        
        if len(individual_avgs) == 2:
            avg_individual_performance = sum(individual_avgs) / 2
            partnership_performance = partnership['avg_fouls_per_game']
            performance_diff = partnership_performance - avg_individual_performance
            
            comparison_data.append({
                'partnership_signature': partnership['partnership_signature'],
                'games_worked': partnership['games_worked'],
                'partnership_avg_fouls': partnership_performance,
                'individual_avg_fouls': avg_individual_performance,
                'performance_difference': performance_diff,
                'official_1': partnership['official_1'],
                'official_2': partnership['official_2'],
                'official_1_individual': individual_stats.get(partnership['official_1'], 0),
                'official_2_individual': individual_stats.get(partnership['official_2'], 0)
            })
    
    comparison_df = pd.DataFrame(comparison_data)
    
    if len(comparison_df) > 0:
        comparison_df = comparison_df.sort_values(by='performance_difference', ascending=False)
    
    return comparison_df


def find_most_frequent_partnerships(df: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """
    Find the partnerships that work together most frequently
    
    Args:
        df: DataFrame with game data
        top_n: Number of top partnerships to return
        
    Returns:
        DataFrame with most frequent partnerships
    """
    partnership_counts = {}
    
    for _, game in df.iterrows():
        officials = game['officials']
        partnerships = get_all_partnerships_from_game(officials)
        
        for partnership_sig in partnerships:
            partnership_counts[partnership_sig] = partnership_counts.get(partnership_sig, 0) + 1
    
    # Convert to DataFrame and sort
    freq_data = []
    for partnership_sig, count in partnership_counts.items():
        officials_list = partnership_sig.split(' & ')
        freq_data.append({
            'partnership_signature': partnership_sig,
            'official_1': officials_list[0],
            'official_2': officials_list[1],
            'games_together': count
        })
    
    freq_df = pd.DataFrame(freq_data)
    freq_df = freq_df.sort_values(by='games_together', ascending=False)
    
    return freq_df.head(top_n)


def analyze_partnership_trends_over_time(df: pd.DataFrame, min_games_per_season: int = 3) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Analyze how partnership performance changes over multiple seasons
    
    Args:
        df: DataFrame with game data including season column
        min_games_per_season: Minimum games per season for a partnership to be included
        
    Returns:
        Tuple of (trends_df, trend_summary_df)
    """
    seasons = sorted(df['season'].unique())
    partnership_trends = []
    
    # Get all partnerships that appear in multiple seasons
    all_partnerships = set()
    for season in seasons:
        season_df = df[df['season'] == season]
        season_partnerships = set()
        
        for _, game in season_df.iterrows():
            partnerships = get_all_partnerships_from_game(game['officials'])
            season_partnerships.update(partnerships)
        
        all_partnerships.update(season_partnerships)
    
    # Track each partnership across seasons
    for partnership_sig in all_partnerships:
        officials_list = partnership_sig.split(' & ')
        partnership_season_data = []
        
        for season in seasons:
            season_df = df[df['season'] == season]
            partnership_games = []
            
            for _, game in season_df.iterrows():
                partnerships = get_all_partnerships_from_game(game['officials'])
                if partnership_sig in partnerships:
                    partnership_games.append(game)
            
            if len(partnership_games) >= min_games_per_season:
                games_df = pd.DataFrame(partnership_games)
                partnership_season_data.append({
                    'season': season,
                    'games': len(partnership_games),
                    'avg_fouls': games_df['total_fouls'].mean(),
                    'std_fouls': games_df['total_fouls'].std(),
                    'home_visitor_diff': games_df['home_fouls'].mean() - games_df['visitor_fouls'].mean()
                })
        
        # Only include partnerships that appear in multiple seasons
        if len(partnership_season_data) > 1:
            for season_data in partnership_season_data:
                partnership_trends.append({
                    'partnership_signature': partnership_sig,
                    'official_1': officials_list[0],
                    'official_2': officials_list[1],
                    'season': season_data['season'],
                    'games_worked': season_data['games'],
                    'avg_fouls_per_game': season_data['avg_fouls'],
                    'std_fouls': season_data['std_fouls'],
                    'home_visitor_diff': season_data['home_visitor_diff']
                })
    
    trends_df = pd.DataFrame(partnership_trends)
    
    if len(trends_df) > 0:
        # Calculate trend metrics for each partnership
        trend_summary = []
        for partnership_sig in trends_df['partnership_signature'].unique():
            partnership_data = trends_df[trends_df['partnership_signature'] == partnership_sig].sort_values('season')
            
            if len(partnership_data) > 1:
                # Calculate trend in fouls over time
                fouls = partnership_data['avg_fouls_per_game'].values
                
                # Simple linear trend
                if len(fouls) > 1:
                    slope = (fouls[-1] - fouls[0]) / (len(fouls) - 1)
                else:
                    slope = 0
                
                officials_list = partnership_sig.split(' & ')
                trend_summary.append({
                    'partnership_signature': partnership_sig,
                    'official_1': officials_list[0],
                    'official_2': officials_list[1],
                    'seasons_active': len(partnership_data),
                    'total_games': partnership_data['games_worked'].sum(),
                    'first_season_avg': fouls[0],
                    'last_season_avg': fouls[-1],
                    'trend_slope': slope,
                    'seasons_list': ', '.join(partnership_data['season'].values)
                })
        
        trend_summary_df = pd.DataFrame(trend_summary)
        trend_summary_df = trend_summary_df.sort_values('trend_slope', ascending=False)
        
        return trends_df, trend_summary_df
    
    return pd.DataFrame(), pd.DataFrame()


def analyze_partnership_chemistry(df: pd.DataFrame, min_games: int = 8) -> pd.DataFrame:
    """
    Analyze which two-official partnerships have the best and worst "chemistry"
    based on consistency and foul patterns
    
    Args:
        df: DataFrame with game data
        min_games: Minimum games to include partnership in analysis
        
    Returns:
        DataFrame with partnership chemistry analysis
    """
    partnership_chemistry = []
    
    # Group games by partnership signature directly
    partnership_games = {}
    
    for _, game in df.iterrows():
        partnerships = get_all_partnerships_from_game(game['officials'])
        
        for partnership_sig in partnerships:
            if partnership_sig not in partnership_games:
                partnership_games[partnership_sig] = []
            partnership_games[partnership_sig].append(game)
    
    # Calculate chemistry for each partnership
    for partnership_sig, games in partnership_games.items():
        if len(games) >= min_games:
            games_df = pd.DataFrame(games)
            officials = partnership_sig.split(' & ')
            
            # Calculate basic statistics
            avg_fouls = games_df['total_fouls'].mean()
            std_fouls = games_df['total_fouls'].std()
            
            # Calculate consistency metrics
            foul_variance = games_df['total_fouls'].var()
            foul_range = games_df['total_fouls'].max() - games_df['total_fouls'].min()
            
            # Calculate home/away balance
            avg_home_fouls = games_df['home_fouls'].mean()
            avg_visitor_fouls = games_df['visitor_fouls'].mean()
            home_visitor_balance = abs(avg_home_fouls - avg_visitor_fouls)
            
            # Chemistry score (lower is better) - combination of variance and imbalance
            chemistry_score = foul_variance + (home_visitor_balance * 2)
            
            partnership_chemistry.append({
                'partnership_signature': partnership_sig,
                'official_1': officials[0],
                'official_2': officials[1],
                'games_worked': len(games),
                'avg_fouls': avg_fouls,
                'foul_variance': foul_variance,
                'foul_range': foul_range,
                'home_visitor_balance': home_visitor_balance,
                'chemistry_score': chemistry_score,
                'std_fouls': std_fouls
            })
    
    chemistry_df = pd.DataFrame(partnership_chemistry)
    
    if len(chemistry_df) > 0:
        # Rank by chemistry score (lower is better)
        chemistry_df = chemistry_df.sort_values(by='chemistry_score')
        chemistry_df['chemistry_rank'] = range(1, len(chemistry_df) + 1)
    
    return chemistry_df


def plot_partnership_distributions(partnership_df: pd.DataFrame, top_n: int = 15, output_file: Optional[str] = None):
    """
    Create bar plot showing average fouls for top partnerships
    
    Args:
        partnership_df: DataFrame with partnership statistics
        top_n: Number of top partnerships to plot
        output_file: Path to save the plot (optional)
    """
    if len(partnership_df) == 0:
        print("No partnership data available for plotting")
        return
    
    # Select top partnerships by number of games worked
    top_partnerships = partnership_df.nlargest(top_n, 'games_worked')
    
    # Create the plot
    plt.figure(figsize=(15, 10))
    
    # Prepare data for plotting
    partnership_names = []
    foul_averages = []
    
    for _, partnership in top_partnerships.iterrows():
        # Create shorter partnership name for display
        officials = partnership['partnership_signature'].split(' & ')
        short_names = [name.split()[-1] for name in officials]  # Use last names only
        partnership_name = ' & '.join(short_names)
        partnership_names.append(f"{partnership_name}\n({partnership['games_worked']} games)")
        foul_averages.append(partnership['avg_fouls_per_game'])
    
    # Create bar plot
    bars = plt.bar(range(len(partnership_names)), foul_averages, 
                   color=plt.cm.viridis([i/len(partnership_names) for i in range(len(partnership_names))]))
    
    plt.xlabel('Two-Official Partnerships')
    plt.ylabel('Average Fouls Per Game')
    plt.title(f'Average Fouls Per Game - Top {top_n} Partnerships by Games Worked')
    plt.xticks(range(len(partnership_names)), partnership_names, rotation=45, ha='right')
    
    # Add value labels on bars
    for bar, value in zip(bars, foul_averages):
        plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                f'{value:.1f}', ha='center', va='bottom')
    
    plt.grid(True, alpha=0.3, axis='y')
    plt.tight_layout()
    
    if output_file:
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Plot saved to {output_file}")
    else:
        plt.show()


def analyze_official_partnership_networks(df: pd.DataFrame, min_games: int = 5) -> pd.DataFrame:
    """
    Analyze which officials work together most frequently and their network patterns
    
    Args:
        df: DataFrame with game data
        min_games: Minimum games for a partnership to be included
        
    Returns:
        DataFrame with official partnership network analysis
    """
    # Get partnership frequencies
    partnerships_df = find_most_frequent_partnerships(df, top_n=1000)  # Get many partnerships
    significant_partnerships = partnerships_df[partnerships_df['games_together'] >= min_games]
    
    # Calculate network metrics for each official
    official_networks = {}
    
    for _, partnership in significant_partnerships.iterrows():
        official1 = partnership['official_1']
        official2 = partnership['official_2']
        games = partnership['games_together']
        
        # Initialize if not exists
        if official1 not in official_networks:
            official_networks[official1] = {'partners': [], 'total_partnership_games': 0, 'unique_partners': 0}
        if official2 not in official_networks:
            official_networks[official2] = {'partners': [], 'total_partnership_games': 0, 'unique_partners': 0}
        
        # Add partnership info
        official_networks[official1]['partners'].append({'partner': official2, 'games': games})
        official_networks[official2]['partners'].append({'partner': official1, 'games': games})
        
        official_networks[official1]['total_partnership_games'] += games
        official_networks[official2]['total_partnership_games'] += games
    
    # Convert to summary format
    network_summary = []
    for official, data in official_networks.items():
        partners = data['partners']
        unique_partners = len(partners)
        total_partnership_games = data['total_partnership_games'] // 2  # Divide by 2 to avoid double counting
        
        # Find most frequent partner
        if partners:
            most_frequent_partner = max(partners, key=lambda x: x['games'])
            avg_games_per_partner = total_partnership_games / unique_partners if unique_partners > 0 else 0
        else:
            most_frequent_partner = {'partner': '', 'games': 0}
            avg_games_per_partner = 0
        
        network_summary.append({
            'official': official,
            'unique_partners': unique_partners,
            'total_partnership_games': total_partnership_games,
            'avg_games_per_partner': avg_games_per_partner,
            'most_frequent_partner': most_frequent_partner['partner'],
            'most_frequent_partner_games': most_frequent_partner['games']
        })
    
    network_df = pd.DataFrame(network_summary)
    network_df = network_df.sort_values('total_partnership_games', ascending=False)
    
    return network_df


def main():
    """Main function to run the two-official partnership analysis"""
    # Define the JSON files for different seasons
    json_files = [
        "officials_202425.json",    # 2024-25 season
        "officials_202324.json",    # 2023-24 season  
        "officials_202223.json"     # 2022-23 season
    ]
    
    # Load all seasons
    try:
        df = load_multiple_seasons(json_files)
    except ValueError as e:
        print(f"Error loading data: {e}")
        return
    
    # Show season breakdown
    print("\n=== SEASON BREAKDOWN ===")
    season_summary = df.groupby('season').size().reset_index(name='games')
    print(season_summary.to_string(index=False))
    
    # Analyze two-official partnerships across all seasons
    print("\n=== ANALYZING PARTNERSHIPS ACROSS ALL SEASONS ===")
    partnership_df = analyze_official_partnerships(df, min_games=10, by_season=False)
    
    if len(partnership_df) == 0:
        print("No partnerships found meeting minimum games criteria.")
        return
    
    # Save overall partnership analysis
    partnership_df.to_csv("two_official_partnership_analysis_all_seasons.csv", index=False)
    print(f"Saved partnership analysis to two_official_partnership_analysis_all_seasons.csv ({len(partnership_df)} partnerships)")
    
    # Analyze by individual seasons
    print("\n=== ANALYZING PARTNERSHIPS BY SEASON ===")
    partnership_by_season_df = analyze_official_partnerships(df, min_games=5, by_season=True)
    partnership_by_season_df.to_csv("two_official_partnership_analysis_by_season.csv", index=False)
    print(f"Saved season-by-season analysis ({len(partnership_by_season_df)} partnership-season combinations)")
    
    # Analyze trends over time
    print("\n=== ANALYZING PARTNERSHIP TRENDS OVER TIME ===")
    trends_df, trend_summary_df = analyze_partnership_trends_over_time(df, min_games_per_season=3)
    
    if len(trends_df) > 0:
        trends_df.to_csv("partnership_trends_over_time.csv", index=False)
        trend_summary_df.to_csv("partnership_trend_summary.csv", index=False)
        print(f"Found {len(trend_summary_df)} partnerships that worked multiple seasons")
        
        print("\nTop 5 partnerships with INCREASING foul trends:")
        increasing_trends = trend_summary_df.head(5)
        trend_cols = ['partnership_signature', 'seasons_active', 'total_games', 'first_season_avg', 'last_season_avg', 'trend_slope']
        if len(increasing_trends) > 0:
            print(increasing_trends[trend_cols].to_string(index=False))
        
        print("\nTop 5 partnerships with DECREASING foul trends:")
        decreasing_trends = trend_summary_df.tail(5)
        if len(decreasing_trends) > 0:
            print(decreasing_trends[trend_cols].to_string(index=False))
    
    # Show overall results
    print("\n=== TOP 15 HIGHEST FOUL PARTNERSHIPS (ALL SEASONS) ===")
    top_15_high = partnership_df.head(15)
    display_cols = ['partnership_signature', 'games_worked', 'avg_fouls_per_game', 'std_fouls']
    print(top_15_high[display_cols].to_string(index=False))
    
    print("\n=== TOP 15 LOWEST FOUL PARTNERSHIPS (ALL SEASONS) ===")
    bottom_15_low = partnership_df.tail(15)
    print(bottom_15_low[display_cols].to_string(index=False))
    
    # Find most frequent partnerships across all seasons
    print("\n=== MOST FREQUENT TWO-OFFICIAL PARTNERSHIPS (ALL SEASONS) ===")
    frequent_partnerships = find_most_frequent_partnerships(df, top_n=15)
    freq_display_cols = ['partnership_signature', 'games_together']
    print(frequent_partnerships[freq_display_cols].to_string(index=False))
    frequent_partnerships.to_csv("most_frequent_partnerships_all_seasons.csv", index=False)
    
    # Analyze partnership networks
    print("\n=== OFFICIAL PARTNERSHIP NETWORKS ===")
    network_df = analyze_official_partnership_networks(df, min_games=8)
    network_df.to_csv("official_partnership_networks.csv", index=False)
    print("Top 10 officials by partnership activity:")
    network_display_cols = ['official', 'unique_partners', 'total_partnership_games', 'most_frequent_partner', 'most_frequent_partner_games']
    print(network_df.head(10)[network_display_cols].to_string(index=False))
    
    # Compare individual vs partnership performance
    print("\n=== PARTNERSHIP vs INDIVIDUAL PERFORMANCE COMPARISON ===")
    comparison_df = compare_individual_vs_partnership_performance(df, partnership_df)
    if len(comparison_df) > 0:
        comparison_df.to_csv("partnership_vs_individual_performance_all_seasons.csv", index=False)
        print("Top 5 partnerships that call MORE fouls than individual averages:")
        top_over = comparison_df.head(5)
        comp_display_cols = ['partnership_signature', 'games_worked', 'partnership_avg_fouls', 'individual_avg_fouls', 'performance_difference']
        print(top_over[comp_display_cols].to_string(index=False))
        
        print("\nTop 5 partnerships that call FEWER fouls than individual averages:")
        top_under = comparison_df.tail(5)
        print(top_under[comp_display_cols].to_string(index=False))
    
    # Analyze partnership chemistry
    print("\n=== PARTNERSHIP CHEMISTRY ANALYSIS ===")
    chemistry_df = analyze_partnership_chemistry(df, min_games=12)
    if len(chemistry_df) > 0:
        chemistry_df.to_csv("partnership_chemistry_analysis_all_seasons.csv", index=False)
        print("Top 5 partnerships with BEST chemistry (most consistent):")
        best_chemistry = chemistry_df.head(5)
        chem_display_cols = ['partnership_signature', 'games_worked', 'avg_fouls', 'std_fouls', 'chemistry_score']
        print(best_chemistry[chem_display_cols].to_string(index=False))
        
        print("\nTop 5 partnerships with WORST chemistry (least consistent):")
        worst_chemistry = chemistry_df.tail(5)
        print(worst_chemistry[chem_display_cols].to_string(index=False))
    
    # Create visualization
    print("\n=== CREATING VISUALIZATION ===")
    plot_partnership_distributions(partnership_df, top_n=15, output_file="partnership_foul_distributions_all_seasons.png")
    
    print(f"\nAnalysis complete! Generated files:")
    print("- two_official_partnership_analysis_all_seasons.csv")
    print("- two_official_partnership_analysis_by_season.csv") 
    print("- partnership_trends_over_time.csv")
    print("- partnership_trend_summary.csv")
    print("- most_frequent_partnerships_all_seasons.csv")
    print("- official_partnership_networks.csv")
    print("- partnership_vs_individual_performance_all_seasons.csv")
    print("- partnership_chemistry_analysis_all_seasons.csv")
    print("- partnership_foul_distributions_all_seasons.png")


if __name__ == "__main__":
    main()