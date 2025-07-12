import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.io as pio
import json, re, pytz, pycountry
from datetime import datetime, timezone

pio.json.config.default_engine = "json"

# ----------------------------------------------------------------------------------
#  Page / UI CONFIG
# ----------------------------------------------------------------------------------
st.set_page_config(
    page_title="Spotify Wrapped Dashboard",
    page_icon="🎧",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        background-color: #121212;
        color: #FFFFFF;
    }
    .stMetric {
        background-color: #282828;
        padding: 20px;
        border-radius: 10px;
    }
    .stMetric label {
        color: #B3B3B3;
    }
    .stMetric div {
        color: #FFFFFF;
    }
    .stSubheader {
        color: #1DB954;
    }
    .stDataFrame {
        background-color: #282828;
    }
    /* Sidebar styling */
    .css-1d391kg {
        background-color: #121212;
    }
    .sidebar .sidebar-content {
        background-color: #121212;
    }
    .stSidebar {
        background-color: #121212;
    }
    .sidebar-header {
        color: #1DB954;
        font-size: 24px;
        font-weight: bold;
        padding: 20px 0;
        text-align: center;
        border-bottom: 2px solid #282828;
        margin-bottom: 20px;
    }
    .sidebar-section {
        background-color: #282828;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    .sidebar-section-title {
        color: #1DB954;
        font-size: 16px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    /* Overall statistics card hover effect */
    .metric-card {
        background: rgba(40,40,40,0.6);
        backdrop-filter: blur(12px);
        border-radius: 20px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        color: #fff;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-5px) scale(1.03);
        box-shadow: 0 8px 32px rgba(30,185,84,0.15);
    }
    .metric-card h1 {
        color: #1DB954;
        font-size: 32px;
        font-weight: 700;
        margin-bottom: 0.5rem;
    }
    .metric-card p {
        font-size: 16px;
        color: #fff;
        margin: 0;
    }
    /* Artist card heading and metrics */
    .artist-card h3 {
        color: #1DB954 !important;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 20px;
    }
    .metric-box h2 {
        color: #1DB954 !important;
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 8px;
    }
    .metric-box span {
        color: #fff !important;
        font-size: 0.95rem;
        letter-spacing: 0.5px;
    }
    /* Spotify logo header */
    .spotify-header {
        display: flex;
        align-items: center;
        gap: 16px;
        margin-bottom: 1.5rem;
    }
    .spotify-logo {
        height: 40px;
        width: 40px;
    }
    .spotify-brand {
        color: #1DB954;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 1px;
    }
    .main-green-title {
        color: #1DB954 !important;
        font-size: 2.5rem !important;
        font-weight: 800 !important;
        margin-bottom: 1.5rem !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Spotify logo and brand header
st.markdown(
    '''<div class="spotify-header">
        <img class="spotify-logo" src="https://upload.wikimedia.org/wikipedia/commons/1/19/Spotify_logo_without_text.svg" alt="Spotify Logo">
        <span class="spotify-brand">Spotify Analytics</span>
    </div>''',
    unsafe_allow_html=True
)

# Main green heading
st.markdown('<div class="main-green-title">🎧 Your Ultimate Spotify Wrapped Dashboard</div>', unsafe_allow_html=True)
# ----------------------------------------------------------------------------------
# 1️⃣  FILE-UPLOAD + PRE-PROCESS PIPELINE
# ----------------------------------------------------------------------------------

def _country_alpha2_to_full(alpha):
    try:
        return pycountry.countries.get(alpha_2=alpha).name
    except Exception:
        return None

# Abbreviation fixes for VPN / mis-tags ➝ canonical country.
_VPN_CORRECTION = {
    "SG": "IN", "FR": "US", "NL": "US", "GB": "US", "JP": "US"
}

_TZ_MAP = {
    "IN": "Asia/Kolkata",
    "US": "America/New_York",
    "QA": "Asia/Qatar"
}

_PLATFORM_REGEX = {
    "Android": r"android",
    "iOS": r"ios|iphone|ipad|mac|darwin",
    "Windows": r"windows",
    "Google Cast": r"google cast|chromecast|cast_"
}

@st.cache_data(show_spinner=False)
def preprocess_streaming_history(json_blobs):
    """Take list-of-dict streaming objects ➝ cleaned DataFrame."""
    df = pd.DataFrame(json_blobs)

    # 1. Country corrections & full names
    df["conn_country"] = df["conn_country"].replace(_VPN_CORRECTION)
    df["conn_country_full"] = df["conn_country"].apply(_country_alpha2_to_full)

    # 2. Timestamps ▸ to UTC aware ▸ localised ▸ strip tz for analysis
    if "ts" in df.columns:
        df["ts"] = pd.to_datetime(df["ts"], utc=True)
    elif "endTime" in df.columns:
        df["ts"] = pd.to_datetime(df["endTime"], utc=True)
    else:
        st.error("Cannot find a timestamp column (ts / endTime) in uploaded data.")
        st.stop()

    # Split by country groups and localize separately (like in your notebook)
    dfs = []
    cutoff = pd.Timestamp('2024-08-04', tz='UTC')
    
    # India
    mask_in = df['conn_country'] == 'IN'
    if mask_in.any():
        df_in = df[mask_in].copy()
        df_in['ts_local'] = df_in['ts'].dt.tz_convert('Asia/Kolkata')
        dfs.append(df_in)
    
    # US
    mask_us = df['conn_country'] == 'US'
    if mask_us.any():
        df_us = df[mask_us].copy()
        df_us['ts_local'] = df_us['ts'].dt.tz_convert('America/New_York')
        dfs.append(df_us)
    
    # Qatar
    mask_qa = df['conn_country'] == 'QA'
    if mask_qa.any():
        df_qa = df[mask_qa].copy()
        df_qa['ts_local'] = df_qa['ts'].dt.tz_convert('Asia/Qatar')
        dfs.append(df_qa)
    
    # NaN fallback (US after Aug 4, 2024)
    mask_nan_us = df['conn_country'].isna() & (df['ts'] >= cutoff)
    if mask_nan_us.any():
        df_nan_us = df[mask_nan_us].copy()
        df_nan_us['ts_local'] = df_nan_us['ts'].dt.tz_convert('America/New_York')
        dfs.append(df_nan_us)
    
    # NaN fallback (India before Aug 4, 2024)
    mask_nan_in = df['conn_country'].isna() & (df['ts'] < cutoff)
    if mask_nan_in.any():
        df_nan_in = df[mask_nan_in].copy()
        df_nan_in['ts_local'] = df_nan_in['ts'].dt.tz_convert('Asia/Kolkata')
        dfs.append(df_nan_in)
    
    # Combine all and sort
    if dfs:
        df = pd.concat(dfs).sort_index()
    
    # Strip timezone for analysis
    df["ts_local_clean"] = df["ts_local"].dt.tz_localize(None)

    # 3. Basic listening metrics
    if "ms_played" in df.columns:
        ms_col = "ms_played"
    elif "msPlayed" in df.columns:
        ms_col = "msPlayed"
    else:
        st.error("Cannot find ms_played/msPlayed column in uploaded data.")
        st.stop()

    df["hours"] = df[ms_col] / (1000 * 60 * 60)
    df["minutes"] = df[ms_col] / (1000 * 60)

    # 4. Calendar helpers
    df["date"] = df["ts_local_clean"].dt.date
    df["Year"] = df["ts_local_clean"].dt.year

    # 5. Platform cleaning
    def _clean_platform(val):
        if pd.isna(val):
            return "Unknown"
        lower = str(val).lower()
        for pretty, rgx in _PLATFORM_REGEX.items():
            if re.search(rgx, lower):
                return pretty
        return "Other"

    platform_src_col = "platform"
    if platform_src_col not in df.columns:
        platform_src_col = "platform"
    df["platform_clean"] = df[platform_src_col].apply(_clean_platform)

    # 6. Track-id extraction
    if "spotify_track_uri" in df.columns:
        df["track_id"] = df["spotify_track_uri"].str.split(":" ).str[-1]
    elif "spotifyTrackUri" in df.columns:
        df["track_id"] = df["spotifyTrackUri"].str.split(":" ).str[-1]

    return df

# ----------------------------------------------------------------------------------
# 2️⃣  SIDEBAR ▸ FILE-UPLOAD
# ----------------------------------------------------------------------------------

with st.sidebar:
    st.markdown("<div class='sidebar-header'>🎧 Spotify Analytics</div>", unsafe_allow_html=True)
    up_files = st.file_uploader(
        "Upload your Spotify *StreamingHistory*.json file(s)",
        type=["json"], accept_multiple_files=True
    )

if not up_files:
    st.info("Please upload your JSON file(s) to begin.")
    st.stop()

# Consolidate all uploaded JSON blobs
json_records = []
for f in up_files:
    json_records.extend(json.load(f))

# Pre-process in-memory
with st.spinner("Pre-processing your data …"):
    df = preprocess_streaming_history(json_records)

# ----------------------------------------------------------------------------------
# 3️⃣  SIDEBAR FILTERS & DASHBOARD UI
# ----------------------------------------------------------------------------------

# Enhanced Sidebar (add filters after file upload)
with st.sidebar:
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">📅 Time Range</div>', unsafe_allow_html=True)
    all_years = sorted(df['Year'].dropna().unique())
    year_checks = {}
    for year in all_years:
        year_checks[year] = st.checkbox(str(year), value=True, key=f"year_{year}")
    selected_years = [year for year, checked in year_checks.items() if checked]
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Track Analysis with number input
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">🎵 Track Analysis</div>', unsafe_allow_html=True)
    top_n = st.number_input(
        "Number of Top Tracks",
        min_value=5,
        max_value=50,
        value=10,
        step=1,
        help="Enter how many top tracks to display"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Artist Analysis with autocomplete
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">🎤 Artist Analysis</div>', unsafe_allow_html=True)
    artist_list = sorted(df['master_metadata_album_artist_name'].dropna().unique())
    artist_filter = st.selectbox(
        "Select or Search Artist",
        options=["(All Artists)"] + artist_list,
        index=0,
        help="Start typing to search for an artist"
    )
    st.markdown('</div>', unsafe_allow_html=True)
    
    # About Section
    st.markdown('<div class="sidebar-section">', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-section-title">ℹ️ About</div>', unsafe_allow_html=True)
    st.markdown("""
        This dashboard provides detailed analytics of your Spotify listening history.
        Your data is processed in-memory and never saved to disk.
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# Filter by selected years
if selected_years:
    df = df[df['Year'].isin(selected_years)]

# Metrics
total_hours = df['hours'].sum()
total_tracks = len(df[df['hours'] > 0])

# Total number of unique listening days
unique_days = df['date'].nunique()

# Average listening hours per day
avg_hours_per_day = total_hours / unique_days if unique_days > 0 else 0

# Format average listen time
h = int(avg_hours_per_day)
m = int(round((avg_hours_per_day - h) * 60))
formatted_avg = f"{h} hrs {m} mins"

# Create three columns for metrics
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(f'''<div class="metric-card"><h1>{total_hours:.2f}</h1><p>Total Listening Hours</p></div>''', unsafe_allow_html=True)
with col2:
    st.markdown(f'''<div class="metric-card"><h1>{total_tracks:,}</h1><p>Total Tracks Played</p></div>''', unsafe_allow_html=True)
with col3:
    st.markdown(f'''<div class="metric-card"><h1>{formatted_avg}</h1><p>Avg Listen Time / Day</p></div>''', unsafe_allow_html=True)

# Add a divider
st.markdown("---")

# Top N Tracks
st.subheader(f"🎵 Top {top_n} Tracks")
if 'track_id' in df.columns:
    top_tracks = (df[df['hours'] > 0]
                  .groupby(['master_metadata_track_name', 'track_id'])['hours']
                  .sum()
                  .sort_values(ascending=False)
                  .head(top_n)
                  .reset_index())
    top_tracks.columns = ['Track', 'Track ID', 'Hours']
    top_tracks['Listening Time'] = top_tracks['Hours'].apply(
        lambda h: f"{int(h)} hrs {int(round((h - int(h)) * 60))} mins"
    )
    for _, row in top_tracks.iterrows():
        st.markdown(f"""
        <div style='display: flex; align-items: center; background: #181818; border-radius: 16px; margin-bottom: 1.5rem; box-shadow: 0 2px 8px #0003;'>
            <div style='flex: 1; padding: 1.2rem 1.5rem;'>
                <div style='font-size: 1.2rem; font-weight: 600; color: #fff;'>{row['Track']}</div>
                <div style='color: #1DB954; font-size: 1rem; margin-top: 0.2rem;'>Listening Time: {row['Listening Time']}</div>
            </div>
            <div style='min-width: 340px; max-width: 340px; padding: 0.5rem 1.5rem 0.5rem 0;'>
                <iframe src="https://open.spotify.com/embed/track/{row['Track ID']}" width="320" height="80" frameborder="0" allowtransparency="true" allow="encrypted-media" style="border-radius: 12px; background: #181818;"></iframe>
            </div>
        </div>
        """, unsafe_allow_html=True)
else:
    top_tracks = (df[df['hours'] > 0]
                  .groupby('master_metadata_track_name')['hours']
                  .sum()
                  .sort_values(ascending=False)
                  .head(top_n)
                  .reset_index())
    top_tracks.columns = ['Track', 'Hours']
    top_tracks['Listening Time'] = top_tracks['Hours'].apply(
        lambda h: f"{int(h)} hrs {int(round((h - int(h)) * 60))} mins"
    )
    for _, row in top_tracks.iterrows():
        st.markdown(f"""
        <div style='display: flex; align-items: center; background: #181818; border-radius: 16px; margin-bottom: 1.5rem; box-shadow: 0 2px 8px #0003;'>
            <div style='flex: 1; padding: 1.2rem 1.5rem;'>
                <div style='font-size: 1.2rem; font-weight: 600; color: #fff;'>{row['Track']}</div>
                <div style='color: #1DB954; font-size: 1rem; margin-top: 0.2rem;'>Listening Time: {row['Listening Time']}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Platform Comparison
st.subheader("🖥️ Platform Usage Comparison")
platform_usage = df.groupby('platform_clean')['hours'].sum().sort_values(ascending=False).reset_index()
platform_usage.columns = ['Platform', 'Hours']
platform_usage['Hours'] = platform_usage['Hours'].round(2)
fig_platform = px.bar(platform_usage, x='Platform', y='Hours', 
                      title="Hours Played by Platform",
                      color_discrete_sequence=['#1db954'],
                      template='plotly_dark')
fig_platform.update_layout(
    plot_bgcolor='#282828',
    paper_bgcolor='#282828',
    font=dict(color='white'),
    hovermode='x unified'
)
st.plotly_chart(fig_platform, use_container_width=True)

# Create two columns for pie charts
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔀 Shuffle Usage")
    shuffle_counts = df['shuffle'].value_counts().rename(index={True: "Shuffled", False: "Not Shuffled"}).reset_index()
    shuffle_counts.columns = ['Shuffle', 'Count']
    fig_shuffle = px.pie(shuffle_counts, names='Shuffle', values='Count', 
                        title="Shuffle vs Non-Shuffle",
                        color_discrete_sequence=['#1db954', '#212121'],
                        template='plotly_dark')
    fig_shuffle.update_layout(
        plot_bgcolor='#282828',
        paper_bgcolor='#282828',
        font=dict(color='white')
    )
    st.plotly_chart(fig_shuffle, use_container_width=True)

with col2:
    st.subheader("📶 Offline vs Online Playback")
    offline_counts = df['offline'].value_counts().rename(index={True: "Offline", False: "Online"}).reset_index()
    offline_counts.columns = ['Mode', 'Count']
    fig_offline = px.pie(offline_counts, names='Mode', values='Count', 
                        title="Offline vs Online",
                        color_discrete_sequence=['#1db954', '#121212'],
                        template='plotly_dark')
    fig_offline.update_layout(
        plot_bgcolor='#282828',
        paper_bgcolor='#282828',
        font=dict(color='white')
    )
    st.plotly_chart(fig_offline, use_container_width=True)

# Map of Countries Played
st.subheader("🌍 Country-wise Listening")
country_counts = df.groupby('conn_country_full')['hours'].sum().round(2).reset_index()
country_counts.columns = ['Country', 'Hours']
fig_map = px.choropleth(country_counts, 
                       locations="Country", 
                       locationmode="country names",
                       color="Hours", 
                       title="Hours of Music Played Around the World",
                       color_continuous_scale=['#121212', '#1db954'],
                       template='plotly_dark')
fig_map.update_layout(
    plot_bgcolor='#282828',
    paper_bgcolor='#282828',
    font=dict(color='white'),
    geo=dict(bgcolor='#282828')
)
st.plotly_chart(fig_map, use_container_width=True)

# Line chart of playtime
st.subheader("📈 Listening Time Over Time")
time_series = df.groupby('date')['hours'].sum().round(2).reset_index()
fig_time = px.line(time_series, x='date', y='hours', 
                  title="Daily Listening Time (Hours)",
                  color_discrete_sequence=['#1db954'],
                  template='plotly_dark')
fig_time.update_layout(
    plot_bgcolor='#282828',
    paper_bgcolor='#282828',
    font=dict(color='white'),
    hovermode='x unified',
    xaxis=dict(
        showgrid=True,
        gridcolor='#404040'
    ),
    yaxis=dict(
        showgrid=True,
        gridcolor='#404040'
    )
)
st.plotly_chart(fig_time, use_container_width=True)

# Privacy notice
st.markdown("---")
st.markdown("**🔒 Privacy Notice:** Your data is processed entirely in-memory and never saved to disk. When you close this page, your data is completely removed.")

# ----------------------------------------------------------------------------------
# 4️⃣  ADVANCED ANALYTICS (Streaks, Milestones, Time Analysis)
# ----------------------------------------------------------------------------------

# Listening Streaks
df_sorted = df.sort_values('date')
activity_days = pd.Series(df_sorted['date'].unique())
activity_days = pd.to_datetime(activity_days)
streaks = (activity_days.diff() != pd.Timedelta(days=1)).cumsum()
streak_lengths = activity_days.groupby(streaks).agg(['count', 'min', 'max'])
longest_streak = streak_lengths['count'].max()
longest_streak_row = streak_lengths[streak_lengths['count'] == longest_streak].iloc[0]
longest_streak_start = longest_streak_row['min'].date()
longest_streak_end = longest_streak_row['max'].date()

# Day with highest listening
max_day_row = df.groupby('date')['hours'].sum().sort_values(ascending=False).reset_index().iloc[0]
max_day = max_day_row['date']
max_day_hours = max_day_row['hours']

# Listening Milestones
first_row = df.sort_values('ts_local_clean').iloc[0]
first_song = first_row['master_metadata_track_name']
first_artist = first_row['master_metadata_album_artist_name']
first_date = first_row['date']

# Cumulative hours for milestones
cumulative = df.groupby('date')['hours'].sum().cumsum().reset_index()
milestones = [100, 500, 1000, 2000, 5000, 10000, 20000]
milestone_dates = {}
for m in milestones:
    milestone_row = cumulative[cumulative['hours'] >= m].head(1)
    if not milestone_row.empty:
        milestone_dates[m] = milestone_row.iloc[0]['date']

# Most listened track and date
track_hours = df.groupby('master_metadata_track_name')['hours'].sum().sort_values(ascending=False)
most_listened_track = track_hours.index[0]
most_listened_hours = track_hours.iloc[0]
most_listened_date = df[df['master_metadata_track_name'] == most_listened_track].groupby('date')['hours'].sum().idxmax()

# Listening by Time of Day
df['hour'] = pd.to_datetime(df['ts_local_clean']).dt.hour
def time_bucket(h):
    if 5 <= h <= 11:
        return 'Morning (5-11)'
    elif 12 <= h <= 17:
        return 'Afternoon (12-17)'
    elif 18 <= h <= 22:
        return 'Evening (18-22)'
    else:
        return 'Night (23-4)'
df['time_bucket'] = df['hour'].apply(time_bucket)
time_of_day = df.groupby('time_bucket')['hours'].sum().reindex([
    'Morning (5-11)', 'Afternoon (12-17)', 'Evening (18-22)', 'Night (23-4)']).reset_index()

# Skips and Replays Insight
total_skipped = df['skipped'].sum() if 'skipped' in df.columns else 0
top_skipped = (df[df['skipped'] == True]
               .groupby('master_metadata_track_name')
               .size()
               .sort_values(ascending=False)
               .head(5)
               .reset_index(name='Skips')) if 'skipped' in df.columns else pd.DataFrame()
top_played = (df[df['skipped'] == False]
              .groupby('master_metadata_track_name')['hours']
              .sum()
              .sort_values(ascending=False)
              .head(5)
              .reset_index()) if 'skipped' in df.columns else pd.DataFrame()

# Monthly and Weekday Trends
df['month'] = pd.to_datetime(df['ts_local_clean']).dt.strftime('%b')
df['month_num'] = pd.to_datetime(df['ts_local_clean']).dt.month
df['weekday'] = pd.to_datetime(df['ts_local_clean']).dt.day_name()
monthly_hours = df.groupby(['month_num', 'month'])['hours'].sum().reset_index().sort_values('month_num')

# Average daily listening hours by weekday
daily_totals = df.groupby('date')['hours'].sum().reset_index()
daily_totals['weekday'] = pd.to_datetime(daily_totals['date']).dt.day_name()
weekday_hours = daily_totals.groupby('weekday')['hours'].mean().reindex([
    'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']).reset_index()

# Heatmap data
month_order = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
               'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

df['month'] = pd.Categorical(df['month'], categories=month_order, ordered=True)
df['weekday'] = pd.Categorical(df['weekday'], categories=weekday_order, ordered=True)

heatmap_data = df.groupby(['month', 'weekday'])['hours'].sum().unstack(fill_value=0).loc[month_order]

# UI Section: Listening Streaks and Milestones
st.markdown("## 🏆 Listening Streaks & Milestones")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Longest Listening Streak", f"{longest_streak} days", f"{longest_streak_start} → {longest_streak_end}")
with col2:
    st.metric("Day with Most Listening", f"{max_day_hours:.2f} hrs", f"{max_day}")
with col3:
    st.metric("First Song Played", f"{first_song}", f"{first_artist} ({first_date})")

# Milestones Timeline
st.markdown("### 🎉 Listening Milestones")
for m, d in milestone_dates.items():
    st.info(f"Crossed {m} hours on {d}")
st.success(f"Most Listened Track: {most_listened_track} ({most_listened_hours:.2f} hrs), Top Day: {most_listened_date}")

# UI Section: Listening by Time of Day
st.markdown("## ⏰ Listening by Time of Day")
fig_timeofday = px.bar(time_of_day, x='time_bucket', y='hours',
                      color='time_bucket',
                      color_discrete_sequence=['#1db954', '#b3b3b3', '#535353', '#191414'],
                      title="Total Listening Hours by Time of Day")
fig_timeofday.update_layout(showlegend=False, plot_bgcolor='#282828', paper_bgcolor='#282828', font=dict(color='white'))
st.plotly_chart(fig_timeofday, use_container_width=True)

# UI Section: Skips and Replays
st.markdown("## ⏭️ Skips and Replays Insight")
col1, col2 = st.columns(2)
with col1:
    st.metric("Total Skipped Tracks", int(total_skipped))
    if not top_skipped.empty:
        st.dataframe(top_skipped, use_container_width=True)
with col2:
    st.metric("Top Played (Non-Skipped)", "")
    if not top_played.empty:
        st.dataframe(top_played, use_container_width=True)

# UI Section: Monthly and Weekday Trends
st.markdown("## 📅 Monthly and Weekday Listening Trends")
fig_month = px.bar(monthly_hours, x='month', y='hours',
                   title="Total Listening Hours per Month",
                   color_discrete_sequence=['#1db954'],
                   category_orders={'month': list(monthly_hours['month'])})
fig_month.update_layout(plot_bgcolor='#282828', paper_bgcolor='#282828', font=dict(color='white'))
st.plotly_chart(fig_month, use_container_width=True)

fig_weekday = px.bar(weekday_hours, x='weekday', y='hours',
                     title="Average Daily Listening Hours by Weekday",
                     color_discrete_sequence=['#1db954'],
                     category_orders={'weekday': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']})
fig_weekday.update_layout(plot_bgcolor='#282828', paper_bgcolor='#282828', font=dict(color='white'))
st.plotly_chart(fig_weekday, use_container_width=True)

fig_heatmap = px.imshow(heatmap_data,
                       labels=dict(x="Weekday", y="Month", color="Hours"),
                       x=heatmap_data.columns,
                       y=heatmap_data.index,
                       color_continuous_scale=['#121212', '#1db954'],
                       title="Listening Hours: Month vs. Weekday")
fig_heatmap.update_layout(plot_bgcolor='#282828', paper_bgcolor='#282828', font=dict(color='white'))
st.plotly_chart(fig_heatmap, use_container_width=True)

# ----------------------------------------------------------------------------------
# 5️⃣  ARTIST-SPECIFIC ANALYTICS
# ----------------------------------------------------------------------------------

# Artist-specific Analytics
st.subheader("🎤 Artist Analytics")
if artist_filter and artist_filter != "(All Artists)":
    import requests
    
    # Display artist image from Wikipedia
    def get_artist_image(artist_name):
        url = f"https://en.wikipedia.org/w/api.php?action=query&format=json&prop=pageimages&titles={artist_name}&pithumbsize=300"
        try:
            resp = requests.get(url, timeout=5)
            data = resp.json()
            pages = data['query']['pages']
            for page in pages.values():
                if 'thumbnail' in page:
                    return page['thumbnail']['source']
        except Exception:
            return None
        return None
    
    artist_img_url = get_artist_image(artist_filter)
    
    # Enhanced Artist Section - Premium UI
    st.markdown("""
    <style>
    .artist-card {
        display: flex;
        flex-wrap: wrap;
        background: linear-gradient(145deg, #1e1e1e, #151515);
        border-radius: 20px;
        padding: 24px;
        margin-top: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6);
        transition: all 0.3s ease-in-out;
    }
    .artist-image {
        width: 240px;
        height: auto;
        border-radius: 16px;
        object-fit: cover;
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        margin-right: 32px;
        margin-bottom: 20px;
    }
    .artist-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        justify-content: center;
        color: white;
    }
    .metric-row {
        display: flex;
        gap: 32px;
        flex-wrap: wrap;
    }
    .metric-box {
        background: #222;
        border-radius: 12px;
        padding: 20px 30px;
        text-align: center;
        box-shadow: 0 0 0 1px #2b2b2b;
        flex: 1;
        min-width: 160px;
        transition: transform 0.2s;
    }
    .metric-box:hover {
        transform: scale(1.03);
        box-shadow: 0 0 12px #1DB95444;
    }
    </style>
    """, unsafe_allow_html=True)

    # Artist Data
    artist_df = df[df['master_metadata_album_artist_name'] == artist_filter]
    artist_hours = artist_df['hours'].sum().round(2)
    artist_tracks = len(artist_df['master_metadata_track_name'].unique())
    artist_avg_hours = artist_hours / unique_days if unique_days > 0 else 0

    # HTML Block
    artist_card_html = f"""
    <div class="artist-card">
        <img class="artist-image" src="{artist_img_url}" alt="{artist_filter}">
        <div class="artist-info">
            <h3>{artist_filter}</h3>
            <div class="metric-row">
                <div class="metric-box">
                    <h2>{artist_hours:.2f}</h2>
                    <span>Total Hours Listened</span>
                </div>
                <div class="metric-box">
                    <h2>{artist_tracks}</h2>
                    <span>Unique Tracks</span>
                </div>
                <div class="metric-box">
                    <h2>{artist_avg_hours:.2f}</h2>
                    <span>Avg Daily Listening (hrs)</span>
                </div>
            </div>
        </div>
    </div>
    """
    st.markdown(artist_card_html, unsafe_allow_html=True)
    
    # Artist's top tracks
    st.subheader(f"🎤 Top {top_n} Tracks by {artist_filter}")
    if 'track_id' in artist_df.columns:
        top_artist_tracks = (artist_df.groupby(['master_metadata_track_name', 'track_id'])['hours']
                             .sum()
                             .sort_values(ascending=False)
                             .head(top_n)
                             .reset_index())
        top_artist_tracks.columns = ['Track', 'Track ID', 'Hours']
        top_artist_tracks['Listening Time'] = top_artist_tracks['Hours'].apply(
            lambda h: f"{int(h)} hrs {int(round((h - int(h)) * 60))} mins"
        )
        for _, row in top_artist_tracks.iterrows():
            st.markdown(f"""
            <div style='display: flex; align-items: center; background: #181818; border-radius: 16px; margin-bottom: 1.5rem; box-shadow: 0 2px 8px #0003;'>
                <div style='flex: 1; padding: 1.2rem 1.5rem;'>
                    <div style='font-size: 1.2rem; font-weight: 600; color: #fff;'>{row['Track']}</div>
                    <div style='color: #1DB954; font-size: 1rem; margin-top: 0.2rem;'>Listening Time: {row['Listening Time']}</div>
                </div>
                <div style='min-width: 340px; max-width: 340px; padding: 0.5rem 1.5rem 0.5rem 0;'>
                    <iframe src="https://open.spotify.com/embed/track/{row['Track ID']}" width="320" height="80" frameborder="0" allowtransparency="true" allow="encrypted-media" style="border-radius: 12px; background: #181818;"></iframe>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        top_artist_tracks = (artist_df.groupby('master_metadata_track_name')['hours']
                             .sum()
                             .sort_values(ascending=False)
                             .head(top_n)
                             .reset_index())
        top_artist_tracks.columns = ['Track', 'Hours']
        top_artist_tracks['Listening Time'] = top_artist_tracks['Hours'].apply(
            lambda h: f"{int(h)} hrs {int(round((h - int(h)) * 60))} mins"
        )
        for _, row in top_artist_tracks.iterrows():
            st.markdown(f"""
            <div style='display: flex; align-items: center; background: #181818; border-radius: 16px; margin-bottom: 1.5rem; box-shadow: 0 2px 8px #0003;'>
                <div style='flex: 1; padding: 1.2rem 1.5rem;'>
                    <div style='font-size: 1.2rem; font-weight: 600; color: #fff;'>{row['Track']}</div>
                    <div style='color: #1DB954; font-size: 1rem; margin-top: 0.2rem;'>Listening Time: {row['Listening Time']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Artist's listening time by time of day
    st.subheader(f"⏰ {artist_filter} Listening by Time of Day")
    artist_df['hour'] = pd.to_datetime(artist_df['ts_local_clean']).dt.hour
    artist_df['time_bucket'] = artist_df['hour'].apply(time_bucket)
    artist_time_of_day = (artist_df.groupby('time_bucket')['hours']
                        .sum()
                        .reindex(['Morning (5-11)', 'Afternoon (12-17)', 'Evening (18-22)', 'Night (23-4)'])
                        .reset_index())
    fig_artist_timeofday = px.bar(artist_time_of_day, 
                                x='time_bucket', 
                                y='hours',
                                color='time_bucket',
                                color_discrete_sequence=['#1db954', '#b3b3b3', '#535353', '#191414'],
                                title=f"Total Listening Hours of {artist_filter} by Time of Day")
    fig_artist_timeofday.update_layout(
        showlegend=False,
        plot_bgcolor='#282828',
        paper_bgcolor='#282828',
        font=dict(color='white')
    )
    st.plotly_chart(fig_artist_timeofday, use_container_width=True)

    # Artist's listening time over time
    st.subheader(f"📈 {artist_filter} Listening Time Over Time")
    artist_time_series = artist_df.groupby('date')['hours'].sum().round(2).reset_index()
    fig_artist_time = px.line(artist_time_series, x='date', y='hours',
                             title=f"Daily {artist_filter} Listening Time (Hours)",
                             color_discrete_sequence=['#1db954'],
                             template='plotly_dark')
    fig_artist_time.update_layout(
        plot_bgcolor='#282828',
        paper_bgcolor='#282828',
        font=dict(color='white'),
        hovermode='x unified',
        xaxis=dict(showgrid=True, gridcolor='#404040'),
        yaxis=dict(showgrid=True, gridcolor='#404040')
    )
    st.plotly_chart(fig_artist_time, use_container_width=True)

# Privacy notice
st.markdown("---")
st.markdown("**🔒 Privacy Notice:** Your data is processed entirely in-memory and never saved to disk. When you close this page, your data is completely removed.") 