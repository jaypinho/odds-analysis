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

def load_games():
    """Load all games from the database"""
    query = """
    SELECT 
        g.id,
        g.sport,
        g.league,
        g.home_team,
        g.away_team,
        g.game_date,
        g.game_start_time,
        g.actual_outcome,
        g.game_status
    FROM games g
    ORDER BY g.game_start_time DESC
    """
    
    try:
        results = db_manager.execute_query(query)
        if results:
            columns = ['id', 'sport', 'league', 'home_team', 'away_team', 'game_date', 'game_start_time', 'actual_outcome', 'game_status']
            return pd.DataFrame(results, columns=columns)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error loading games: {e}")
        return pd.DataFrame()

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
    
    # Load games
    games_df = load_games()
    
    if games_df.empty:
        st.warning("No games found in the database.")
        return
    
    # Game selection
    st.subheader("Select a Game")
    
    # Create a more readable game display
    games_df['display_name'] = (
        games_df['away_team'] + ' @ ' + games_df['home_team'] + 
        ' (' + games_df['game_date'].astype(str) + ')'
    )
    
    # Game selection dropdown
    selected_game_display = st.selectbox(
        "Choose a game:",
        options=games_df['display_name'].tolist(),
        index=0
    )
    
    # Get the selected game ID
    selected_game = games_df[games_df['display_name'] == selected_game_display].iloc[0]
    game_id = selected_game['id']
    
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
                    default=sorted(odds_df['outcome_type'].unique())
                )
            
            with col2:
                odds_type = st.selectbox(
                    "Odds type",
                    options=['decimal_odds', 'devigged_decimal_odds'],
                    format_func=lambda x: "Raw Decimal Odds" if x == 'decimal_odds' else "De-vigged Decimal Odds"
                )
            
            if chart_outcomes:
                # Filter data for chart
                chart_data = odds_df[odds_df['outcome_type'].isin(chart_outcomes)].copy()
                
                # Ensure timestamp is properly formatted
                chart_data['timestamp'] = pd.to_datetime(chart_data['timestamp'])
                
                # Create the scatter plot
                fig = px.scatter(
                    chart_data,
                    x='timestamp',
                    y=odds_type,
                    color='outcome_type',
                    symbol='platform_name',
                    hover_data=['platform_name', 'raw_probability', 'devigged_probability'],
                    title=f"{'Raw' if odds_type == 'decimal_odds' else 'De-vigged'} Decimal Odds Over Time",
                    labels={
                        'timestamp': 'Time',
                        odds_type: 'Decimal Odds',
                        'outcome_type': 'Outcome'
                    }
                )
                
                # Add game start time line if we have the data
                try:
                    game_start_time = pd.to_datetime(selected_game['game_start_time'])
                    # Convert to datetime object that Plotly can handle
                    game_start_dt = game_start_time.to_pydatetime()
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