import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Add the src directory to the path so we can import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config.database import db_manager

st.set_page_config(
    page_title="Odds Analysis Dashboard",
    page_icon="📊",
    layout="wide"
)

@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_games():
    """Load all games from the database"""
    query = """
    SELECT 
        g.id,
        g.sport,
        g.league,
        g.home_team,
        g.away_team,
        g.game_date_local,
        g.game_start_time,
        g.actual_outcome,
        g.game_status,
        m.identifier as polymarket_slug
    FROM games g
    LEFT JOIN markets m ON g.id = m.game_id 
    LEFT JOIN platforms p ON m.platform_id = p.id 
    WHERE p.name = 'polymarket' OR p.name IS NULL
    ORDER BY g.game_start_time DESC
    """
    
    try:
        results = db_manager.execute_query(query)
        if results:
            columns = ['id', 'sport', 'league', 'home_team', 'away_team', 'game_date_local', 'game_start_time', 'actual_outcome', 'game_status', 'polymarket_slug']
            return pd.DataFrame(results, columns=columns)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading games: {e}")
        return pd.DataFrame()

def calculate_brier_scores():
    """Calculate Brier scores for each platform using completed games."""
    query = """
    SELECT 
        p.name as platform_name,
        p.platform_type,
        p.region,
        COUNT(DISTINCT g.id) as num_games,
        COUNT(os.id) as num_predictions,
        AVG(POWER(os.devigged_probability - 
            CASE 
                WHEN g.actual_outcome = o.outcome_type THEN 1.0 
                ELSE 0.0 
            END, 2)) as brier_score,
        AVG(os.devigged_probability) as avg_predicted_probability
    FROM odds_snapshots os
    JOIN outcomes o ON os.outcome_id = o.id
    JOIN markets m ON o.market_id = m.id
    JOIN platforms p ON m.platform_id = p.id
    JOIN games g ON m.game_id = g.id
    WHERE g.actual_outcome IS NOT NULL 
    AND g.game_status = 'completed'
    AND os.devigged_probability IS NOT NULL
    AND os.is_closing_line = TRUE  -- Only use closing lines
    GROUP BY p.name, p.platform_type, p.region
    HAVING COUNT(os.id) >= 5  -- Reduced minimum since we're only using closing lines now
    ORDER BY brier_score ASC
    """
    
    try:
        results = db_manager.execute_query(query)
        if results:
            columns = ['platform_name', 'platform_type', 'region', 'num_games', 'num_predictions', 
                      'brier_score', 'avg_predicted_probability']
            df = pd.DataFrame(results, columns=columns)
            
            # Convert decimal columns to float
            numeric_columns = ['brier_score', 'avg_predicted_probability']
            for col in numeric_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error calculating Brier scores: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60)  # Cache for 60 seconds
def load_odds_for_game(game_id):
    """Load all odds data for a specific game"""
    query = """
    SELECT 
        os.timestamp,
        p.name as platform_name,
        p.platform_type,
        p.region,
        m.market_name,
        o.outcome_type,
        o.outcome_name,
        os.decimal_odds,
        os.raw_probability,
        os.devigged_probability,
        os.devigged_decimal_odds,
        os.is_closing_line
    FROM odds_snapshots os
    JOIN outcomes o ON os.outcome_id = o.id
    JOIN markets m ON o.market_id = m.id
    JOIN platforms p ON m.platform_id = p.id
    JOIN games g ON m.game_id = g.id
    WHERE g.id = %s
    ORDER BY os.timestamp, p.name, o.outcome_type
    """
    
    try:
        # Convert numpy int64 to regular Python int
        game_id_param = int(game_id)
        results = db_manager.execute_query(query, (game_id_param,))
        if results:
            columns = ['timestamp', 'platform_name', 'platform_type', 'region', 'market_name', 
                      'outcome_type', 'outcome_name', 'decimal_odds', 'raw_probability', 
                      'devigged_probability', 'devigged_decimal_odds', 'is_closing_line']
            df = pd.DataFrame(results, columns=columns)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Convert decimal columns to float for compatibility with Plotly
            decimal_columns = ['decimal_odds', 'raw_probability', 'devigged_probability', 'devigged_decimal_odds']
            for col in decimal_columns:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading odds data: {e}")
        return pd.DataFrame()

def main():
    st.title("📊 Sports Odds Analysis Dashboard")
    st.markdown("---")
    
    # Main navigation
    page = st.selectbox(
        "Select a page:",
        ["Game Analysis", "Brier Scores"]
    )
    
    if page == "Game Analysis":
        show_game_analysis()
    elif page == "Brier Scores":
        show_brier_scores()

def show_brier_scores():
    """Display Brier scores page."""
    st.header("🎯 Brier Scores by Platform")
    st.markdown("""
    Brier scores measure the accuracy of probabilistic predictions. 
    Lower scores are better (perfect score = 0, worst score = 1).
    """)
    
    # Calculate Brier scores
    brier_df = calculate_brier_scores()
    
    if brier_df.empty:
        st.warning("No completed games found for Brier score calculation.")
        return
    
    # Display summary metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Platforms", len(brier_df))
    with col2:
        best_platform = brier_df.loc[brier_df['brier_score'].idxmin()]
        st.metric("Best Brier Score", f"{best_platform['brier_score']:.4f}", 
                 help=f"Platform: {best_platform['platform_name']}")
    with col3:
        total_predictions = brier_df['num_predictions'].sum()
        st.metric("Total Predictions", f"{total_predictions:,}")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        platform_types = ['All'] + sorted(brier_df['platform_type'].unique().tolist())
        selected_type = st.selectbox("Platform Type", platform_types)
    
    with col2:
        min_predictions = st.slider("Minimum Predictions", 
                                   min_value=10, 
                                   max_value=int(brier_df['num_predictions'].max()), 
                                   value=50)
    
    # Filter data
    filtered_df = brier_df.copy()
    if selected_type != 'All':
        filtered_df = filtered_df[filtered_df['platform_type'] == selected_type]
    
    filtered_df = filtered_df[filtered_df['num_predictions'] >= min_predictions]
    
    if filtered_df.empty:
        st.warning("No platforms match the selected filters.")
        return
    
    # Create the main table
    st.subheader("Platform Performance Summary")
    
    display_df = filtered_df.copy()
    display_df['region'] = display_df['region'].fillna('Global')
    
    # Format columns for display
    display_df['brier_score'] = display_df['brier_score'].round(4)
    display_df['avg_predicted_probability'] = display_df['avg_predicted_probability'].round(3)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "platform_name": "Platform",
            "platform_type": "Type",
            "region": "Region",
            "num_games": st.column_config.NumberColumn("Games", format="%d"),
            "num_predictions": st.column_config.NumberColumn("Predictions", format="%d"),
            "brier_score": st.column_config.NumberColumn("Brier Score", format="%.4f"),
            "avg_predicted_probability": st.column_config.NumberColumn("Avg Probability", format="%.3f")
        }
    )
    
    # Performance chart
    st.subheader("Brier Score Comparison")
    
    if len(filtered_df) > 1:
        # Create bar chart
        chart_df = filtered_df.copy()
        chart_df['platform_label'] = chart_df['platform_name'] + \
            chart_df['region'].apply(lambda x: f" ({x})" if pd.notna(x) and x != 'Global' else "")
        
        fig = px.bar(
            chart_df,
            x='platform_label',
            y='brier_score',
            color='platform_type',
            title="Brier Scores by Platform (Lower is Better)",
            labels={
                'platform_label': 'Platform',
                'brier_score': 'Brier Score',
                'platform_type': 'Platform Type'
            },
            hover_data=['num_games', 'num_predictions', 'avg_predicted_probability']
        )
        
        fig.update_layout(
            height=500,
            xaxis_title="Platform",
            yaxis_title="Brier Score",
            xaxis_tickangle=-45
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Additional insights
    st.subheader("Key Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Best Performers:**")
        top_3 = filtered_df.nsmallest(3, 'brier_score')
        for i, row in top_3.iterrows():
            region_text = f" ({row['region']})" if pd.notna(row['region']) and row['region'] != 'Global' else ""
            st.write(f"{row.name + 1}. {row['platform_name']}{region_text}: {row['brier_score']:.4f}")
    
    with col2:
        st.markdown("**Most Active:**")
        most_active = filtered_df.nlargest(3, 'num_predictions')
        for i, row in most_active.iterrows():
            region_text = f" ({row['region']})" if pd.notna(row['region']) and row['region'] != 'Global' else ""
            st.write(f"{row.name + 1}. {row['platform_name']}{region_text}: {row['num_predictions']:,} predictions")

def show_game_analysis():
    """Display the original game analysis page."""
    # Load games
    games_df = load_games()
    
    if games_df.empty:
        st.warning("No games found in the database.")
        return
    
    # Game selection
    st.subheader("Select a Game")
    
    # Convert game_date to datetime for date filtering
    games_df['game_date_local'] = pd.to_datetime(games_df['game_date_local'])
    
    # Date picker for filtering games
    col1, col2 = st.columns([1, 2])
    
    with col1:
        # Get available date range
        min_date = games_df['game_date_local'].min().date()
        max_date = games_df['game_date_local'].max().date()
        
        # Default to today's date if there are games today, otherwise most recent date
        from datetime import date
        today = date.today()
        available_dates = set(games_df['game_date_local'].dt.date)
        
        if today in available_dates:
            default_date = today
        else:
            default_date = max_date
        
        selected_date = st.date_input(
            "Select a date:",
            value=default_date,
            min_value=min_date,
            max_value=max_date,
            key="date_selector"
        )
    
    # Filter games by selected date
    games_on_date = games_df[games_df['game_date_local'].dt.date == selected_date].copy()
    
    if games_on_date.empty:
        st.warning(f"No games found for {selected_date}")
        return
    
    # Sort games by start time in ascending order
    games_on_date = games_on_date.sort_values('game_start_time')
    
    # Create display names for games on selected date
    games_on_date['display_name'] = (
        games_on_date['away_team'] + ' @ ' + games_on_date['home_team'] + 
        ' (' + games_on_date['game_start_time'].dt.strftime('%H:%M') + ')'
    )
    
    with col2:
        # Game selection dropdown for the selected date
        selected_game_display = st.selectbox(
            f"Choose a game from {selected_date}:",
            options=games_on_date['display_name'].tolist(),
            index=0,
            key=f"game_selector_{selected_date}"
        )
    
    # Get the selected game ID
    selected_game = games_on_date[games_on_date['display_name'] == selected_game_display].iloc[0]
    game_id = selected_game['id']
    
    # Add Polymarket link if slug is available
    if pd.notna(selected_game['polymarket_slug']) and selected_game['polymarket_slug']:
        st.markdown(f"🔗 [View on Polymarket](https://polymarket.com/event/{selected_game['polymarket_slug']})")
    
    # Store the current game ID in session state to track changes
    if 'current_game_id' not in st.session_state:
        st.session_state.current_game_id = game_id
    elif st.session_state.current_game_id != game_id:
        st.session_state.current_game_id = game_id
        # Clear any cached multiselect state when game changes
        if hasattr(st.session_state, 'outcomes_selector_keys'):
            for key in st.session_state.outcomes_selector_keys:
                if key in st.session_state:
                    del st.session_state[key]
    
    # Display game info
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sport", selected_game['sport'].upper())
    with col2:
        st.metric("Status", selected_game['game_status'].title())
    with col3:
        if pd.notna(selected_game['actual_outcome']):
            st.metric("Outcome", selected_game['actual_outcome'].replace('_', ' ').title())
        else:
            st.metric("Outcome", "TBD")
    
    st.markdown("---")
    
    # Load odds data for selected game
    odds_df = load_odds_for_game(game_id)
    
    if odds_df.empty:
        st.warning("No odds data found for this game.")
        return
    
    # Tabs for different views
    tab1, tab2 = st.tabs(["📋 Odds Table", "📈 Time Series Chart"])
    
    with tab1:
        st.subheader("All Odds Data")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            platforms = ['All'] + sorted(odds_df['platform_name'].unique().tolist())
            selected_platform = st.selectbox("Platform", platforms)
        
        with col2:
            outcomes = ['All'] + sorted(odds_df['outcome_type'].unique().tolist())
            selected_outcome = st.selectbox("Outcome", outcomes)
        
        with col3:
            show_closing_only = st.checkbox("Show closing lines only")
        
        # Filter the data
        filtered_df = odds_df.copy()
        
        if selected_platform != 'All':
            filtered_df = filtered_df[filtered_df['platform_name'] == selected_platform]
        
        if selected_outcome != 'All':
            filtered_df = filtered_df[filtered_df['outcome_type'] == selected_outcome]
        
        if show_closing_only:
            filtered_df = filtered_df[filtered_df['is_closing_line'] == True]
        
        # Display the table
        if not filtered_df.empty:
            # Format the display DataFrame
            display_df = filtered_df[['timestamp', 'platform_name', 'outcome_type', 'decimal_odds', 
                                    'devigged_decimal_odds', 'raw_probability', 'devigged_probability', 
                                    'is_closing_line']].copy()
            
            display_df['raw_probability'] = display_df['raw_probability'].round(4)
            display_df['devigged_probability'] = display_df['devigged_probability'].round(4)
            display_df['decimal_odds'] = display_df['decimal_odds'].round(3)
            display_df['devigged_decimal_odds'] = display_df['devigged_decimal_odds'].round(3)
            
            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "timestamp": st.column_config.DatetimeColumn("Timestamp"),
                    "platform_name": "Platform",
                    "outcome_type": "Outcome",
                    "decimal_odds": st.column_config.NumberColumn("Decimal Odds", format="%.3f"),
                    "devigged_decimal_odds": st.column_config.NumberColumn("De-vigged Odds", format="%.3f"),
                    "raw_probability": st.column_config.NumberColumn("Raw Probability", format="%.4f"),
                    "devigged_probability": st.column_config.NumberColumn("De-vigged Probability", format="%.4f"),
                    "is_closing_line": st.column_config.CheckboxColumn("Closing Line")
                }
            )
            
            st.info(f"Showing {len(display_df)} odds entries")
        else:
            st.warning("No data matches the selected filters.")
    
    with tab2:
        st.subheader("Odds Over Time")
        
        if not odds_df.empty:
            # Chart controls
            col1, col2 = st.columns(2)
            
            with col1:
                chart_outcomes = st.multiselect(
                    "Select outcomes to display",
                    options=sorted(odds_df['outcome_type'].unique()),
                    default=sorted(odds_df['outcome_type'].unique()),
                    key=f"outcomes_selector_{st.session_state.current_game_id}"
                )
            
            with col2:
                odds_type = st.selectbox(
                    "Odds type",
                    options=['decimal_odds', 'devigged_decimal_odds'],
                    format_func=lambda x: "Raw Decimal Odds" if x == 'decimal_odds' else "De-vigged Decimal Odds",
                    index=1  # Default to 'De-vigged Decimal Odds'
                )
            
            if chart_outcomes:
                # Filter data for chart
                chart_data = odds_df[odds_df['outcome_type'].isin(chart_outcomes)].copy()
                
                # Ensure timestamp is properly formatted
                chart_data['timestamp'] = pd.to_datetime(chart_data['timestamp'])
                
                # Create the line chart
                fig = px.line(
                    chart_data,
                    x='timestamp',
                    y=odds_type,
                    color='outcome_type',
                    line_dash='platform_name',
                    hover_data=['platform_name', 'raw_probability', 'devigged_probability'],
                    title=f"{'Raw' if odds_type == 'decimal_odds' else 'De-vigged'} Decimal Odds Over Time",
                    labels={
                        'timestamp': 'Time',
                        odds_type: 'Decimal Odds',
                        'outcome_type': 'Outcome'
                    }
                )
                
                # Add markers to the lines
                fig.update_traces(mode='lines+markers')
                
                # Add game start time line if we have the data
                try:
                    game_start_time = pd.to_datetime(selected_game['game_start_time'])
                    # Convert to datetime object that Plotly can handle using .item() instead of deprecated .to_pydatetime()
                    if hasattr(game_start_time, 'item'):
                        game_start_dt = game_start_time.item()
                    else:
                        game_start_dt = game_start_time
                    fig.add_vline(
                        x=game_start_dt,
                        line_dash="dash",
                        line_color="red",
                        annotation_text="Game Start"
                    )
                except Exception as e:
                    # If that fails, try without the marker
                    pass
                
                fig.update_layout(
                    height=600,
                    xaxis_title="Time",
                    yaxis_title="Decimal Odds",
                    legend_title_text="Outcome / Platform"
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Summary statistics
                st.subheader("Summary Statistics")
                
                summary_stats = chart_data.groupby(['outcome_type', 'platform_name']).agg({
                    odds_type: ['min', 'max', 'mean', 'std', 'count']
                }).round(3)
                
                summary_stats.columns = ['Min', 'Max', 'Mean', 'Std Dev', 'Count']
                st.dataframe(summary_stats, use_container_width=True)
            else:
                st.warning("Please select at least one outcome to display.")
        else:
            st.warning("No odds data available for charting.")

if __name__ == "__main__":
    main()