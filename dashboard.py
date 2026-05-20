"""
CRYPTO ARBITRAGE DASHBOARD - ENHANCED PRODUCTION VERSION
Run with: streamlit run dashboard.py

Features:
- Smart price formatting (shows decimals for small coins)
- Market cap filtering (High/Mid/Low cap)
- Exchange coverage filtering
- Opportunity scoring (Spread × Exchanges / Cap Score)
- Liquidity metrics (volume, buy/sell ratio, net flows)
- Interactive charts and tables
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import glob
import os
from datetime import datetime

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="Crypto Arbitrage Dashboard",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# HELPER FUNCTIONS
# ============================================
def format_price(price):
    """Smart price formatting based on value."""
    if price >= 1000:
        return f"${price:,.2f}"
    elif price >= 1:
        return f"${price:,.4f}"
    elif price >= 0.01:
        return f"${price:,.6f}"
    elif price >= 0.0001:
        return f"${price:,.8f}"
    else:
        return f"${price:.10f}"

def format_volume(volume):
    """Format volume in human-readable format (K, M, B)"""
    if volume >= 1e9:
        return f"${volume/1e9:.2f}B"
    elif volume >= 1e6:
        return f"${volume/1e6:.2f}M"
    elif volume >= 1e3:
        return f"${volume/1e3:.2f}K"
    else:
        return f"${volume:.2f}"

def get_liquidity_rating(volume_usd, buy_sell_ratio=None, net_flow=None):
    """
    Determine liquidity rating based on volume and market activity.
    Returns rating, color, and description.
    """
    if volume_usd >= 100_000_000:  # $100M+
        rating = "🟢 EXCELLENT"
        color = "green"
        desc = "Very deep liquidity, minimal slippage"
    elif volume_usd >= 10_000_000:  # $10M - $100M
        rating = "🟡 GOOD"
        color = "yellowgreen"
        desc = "Good liquidity, low slippage"
    elif volume_usd >= 1_000_000:  # $1M - $10M
        rating = "🟠 MODERATE"
        color = "orange"
        desc = "Moderate liquidity, some slippage possible"
    elif volume_usd >= 100_000:  # $100K - $1M
        rating = "🔴 LOW"
        color = "red"
        desc = "Low liquidity, significant slippage possible"
    else:
        rating = "⚫ VERY LOW"
        color = "darkred"
        desc = "Very low liquidity, high slippage risk"
    
    # Adjust for buy/sell imbalance if data available
    if buy_sell_ratio is not None:
        if buy_sell_ratio > 1.5:
            rating += " (Strong buying pressure)"
            desc += " - More buyers than sellers"
        elif buy_sell_ratio < 0.67:
            rating += " (Strong selling pressure)"
            desc += " - More sellers than buyers"
    
    return rating, color, desc

def get_market_cap_tier(symbol):
    """Estimate market cap tier from symbol."""
    high_cap = ['BTC', 'ETH', 'XRP', 'BNB', 'SOL', 'ADA', 'DOGE', 'TRX', 'TON', 'SHIB']
    mid_cap = ['DOT', 'LINK', 'AVAX', 'MATIC', 'UNI', 'ATOM', 'ETC', 'FIL', 'APT', 'ARB',
               'NEAR', 'ALGO', 'VET', 'ICP', 'INJ', 'EGLD', 'RUNE', 'AAVE', 'MKR', 'CRO']
    
    base = symbol.replace('USDT', '').replace('USD', '').replace('USDC', '').replace('KRW', '')
    
    if base in high_cap:
        return "High Cap (>$10B)", 3
    elif base in mid_cap:
        return "Mid Cap ($1B-$10B)", 2
    else:
        return "Low Cap (<$1B)", 1

@st.cache_data(ttl=300)
def load_price_discrepancies():
    """Load the most recent price discrepancies file"""
    files = glob.glob('data/arbitrage/price_discrepancies_*.csv')
    if not files:
        return None
    latest = max(files, key=os.path.getctime)
    df = pd.read_csv(latest)
    return df

@st.cache_data(ttl=300)
def load_all_prices():
    """Load the most recent all prices file"""
    files = glob.glob('data/arbitrage/all_prices_*.csv')
    if not files:
        return None
    latest = max(files, key=os.path.getctime)
    df = pd.read_csv(latest)
    return df

def add_market_cap_tiers(df):
    """Add market cap tier columns to dataframe"""
    tiers = df['symbol'].apply(lambda x: pd.Series(get_market_cap_tier(x)))
    df['market_cap_tier'] = tiers[0]
    df['cap_score'] = tiers[1]
    return df

# ============================================
# LIQUIDITY DATA LOADING
# ============================================
@st.cache_data(ttl=300)
def load_liquidity_data():
    """
    Load liquidity data from all_prices file which contains volume metrics.
    Returns a dictionary with symbol -> exchange -> liquidity metrics
    """
    all_prices = load_all_prices()
    if all_prices is None:
        return {}
    
    liquidity_dict = {}
    
    for _, row in all_prices.iterrows():
        symbol = row['symbol']
        exchange = row['exchange_name']
        
        # Extract volume data (1h, 4h, 24h)
        volume_1h = row.get('volume_usd_1h', 0)
        volume_24h = row.get('volume_usd_24h', 0)
        buy_volume = row.get('buy_volume_usd_1h', 0)
        sell_volume = row.get('sell_volume_usd_1h', 0)
        net_flow = row.get('net_flows_usd_1h', 0)
        
        # Calculate buy/sell ratio
        if sell_volume > 0:
            buy_sell_ratio = buy_volume / sell_volume
        else:
            buy_sell_ratio = 1.0
        
        if symbol not in liquidity_dict:
            liquidity_dict[symbol] = {}
        
        liquidity_dict[symbol][exchange] = {
            'volume_1h': volume_1h,
            'volume_24h': volume_24h,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'buy_sell_ratio': buy_sell_ratio,
            'net_flow': net_flow,
            'liquidity_rating': get_liquidity_rating(volume_1h, buy_sell_ratio, net_flow)[0],
            'liquidity_desc': get_liquidity_rating(volume_1h, buy_sell_ratio, net_flow)[2]
        }
    
    return liquidity_dict

# ============================================
# LOAD DATA
# ============================================
df = load_price_discrepancies()

if df is None:
    st.error("❌ No data found!")
    st.info(
        "Please run Step 5 first to generate data files.\n\n"
        "The file should be at: data/arbitrage/price_discrepancies_*.csv"
    )
    st.stop()

# Add market cap tiers
df = add_market_cap_tiers(df)

# Load all prices and liquidity data
all_prices_df = load_all_prices()
liquidity_data = load_liquidity_data()

# ============================================
# SIDEBAR - FILTERS
# ============================================
st.sidebar.header("🔍 Filters")

# Market Cap Filter
st.sidebar.subheader("💰 Market Capitalization")
cap_filter = st.sidebar.multiselect(
    "Select Market Cap Tiers",
    options=["High Cap (>$10B)", "Mid Cap ($1B-$10B)", "Low Cap (<$1B)"],
    default=["High Cap (>$10B)", "Mid Cap ($1B-$10B)", "Low Cap (<$1B)"]
)

# Spread Filter
st.sidebar.subheader("📊 Price Spread")
min_spread = st.sidebar.slider(
    "Minimum Spread (%)",
    min_value=0.0,
    max_value=5.0,
    value=0.1,
    step=0.05
)

# Exchange Count Filter
st.sidebar.subheader("🏦 Exchange Coverage")
min_exchanges = st.sidebar.slider(
    "Minimum Number of Exchanges",
    min_value=2,
    max_value=20,
    value=3,
    step=1
)

# Minimum Volume Filter (for liquidity)
st.sidebar.subheader("💧 Minimum Liquidity")
min_volume = st.sidebar.select_slider(
    "Minimum 24h Volume",
    options=["Any", "$100K", "$1M", "$10M", "$100M"],
    value="Any",
    help="Filter out low liquidity pairs to avoid slippage"
)

volume_thresholds = {
    "Any": 0,
    "$100K": 100_000,
    "$1M": 1_000_000,
    "$10M": 10_000_000,
    "$100M": 100_000_000
}
min_volume_threshold = volume_thresholds[min_volume]

# Opportunity Scoring Toggle
st.sidebar.subheader("🎯 Opportunity Scoring")
use_scoring = st.sidebar.checkbox("Enable Smart Scoring", value=True)

if use_scoring:
    st.sidebar.info(
        "**Score Formula:**\n\n"
        "`Spread % × Exchange Count / Cap Score`\n\n"
        "Higher score = Better opportunity!"
    )

# Number of results
st.sidebar.subheader("📄 Display")
top_n = st.sidebar.slider("Number of Results to Show", min_value=10, max_value=100, value=50, step=10)

st.sidebar.markdown("---")

# Refresh button
if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.caption(
    "Data from CoinGlass API\n"
    "Liquidity based on 1h trading volume"
)

# ============================================
# APPLY FILTERS
# ============================================
df_filtered = df[
    (df['spread_pct'] >= min_spread) &
    (df['exchange_count'] >= min_exchanges) &
    (df['market_cap_tier'].isin(cap_filter))
].copy()

# Apply volume filter if needed
if min_volume_threshold > 0 and all_prices_df is not None:
    # Get symbols that meet volume threshold
    high_volume_symbols = set()
    for symbol in df_filtered['symbol'].unique():
        symbol_prices = all_prices_df[all_prices_df['symbol'] == symbol]
        if not symbol_prices.empty:
            max_volume = symbol_prices['volume_usd_24h'].max() if 'volume_usd_24h' in symbol_prices.columns else 0
            if max_volume >= min_volume_threshold:
                high_volume_symbols.add(symbol)
    
    original_count = len(df_filtered)
    df_filtered = df_filtered[df_filtered['symbol'].isin(high_volume_symbols)]
    st.sidebar.caption(f"Volume filter removed {original_count - len(df_filtered)} low-liquidity pairs")

# Calculate opportunity score
if use_scoring:
    df_filtered['opportunity_score'] = (
        df_filtered['spread_pct'] * df_filtered['exchange_count'] / df_filtered['cap_score']
    ).round(2)
    df_filtered = df_filtered.sort_values('opportunity_score', ascending=False)
else:
    df_filtered = df_filtered.sort_values('spread_pct', ascending=False)

df_filtered = df_filtered.head(top_n)

# ============================================
# MAIN HEADER
# ============================================
st.title("💰 Crypto Arbitrage Opportunity Finder")
st.markdown("### Find price discrepancies across 15+ cryptocurrency exchanges")
st.markdown("---")

# ============================================
# METRICS ROW
# ============================================
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("📊 Total Pairs", f"{len(df):,}")

with col2:
    st.metric("📈 Avg Spread", f"{df['spread_pct'].mean():.2f}%")

with col3:
    st.metric("🔥 Max Spread", f"{df['spread_pct'].max():.2f}%")

with col4:
    st.metric("✅ After Filters", len(df_filtered))

with col5:
    high_cap_count = len(df[df['market_cap_tier'] == "High Cap (>$10B)"])
    st.metric("🏦 High Cap Pairs", high_cap_count)

st.markdown("---")

# ============================================
# MAIN DATA TABLE
# ============================================
st.subheader("📋 Arbitrage Opportunities")

# Prepare display dataframe
if use_scoring and 'opportunity_score' in df_filtered.columns:
    display_cols = ['symbol', 'market_cap_tier', 'min_price', 'max_price', 
                    'spread_pct', 'exchange_count', 'opportunity_score']
    column_names = ['Pair', 'Market Cap', 'Min Price', 'Max Price', 'Spread %', 'Exchanges', 'Score']
else:
    display_cols = ['symbol', 'market_cap_tier', 'min_price', 'max_price', 
                    'spread_pct', 'exchange_count']
    column_names = ['Pair', 'Market Cap', 'Min Price', 'Max Price', 'Spread %', 'Exchanges']

display_df = df_filtered[display_cols].copy()

# Format the data
display_df['spread_pct'] = display_df['spread_pct'].apply(lambda x: f"{x:.2f}%")
display_df['min_price'] = display_df['min_price'].apply(format_price)
display_df['max_price'] = display_df['max_price'].apply(format_price)

if use_scoring and 'opportunity_score' in df_filtered.columns:
    display_df['opportunity_score'] = display_df['opportunity_score'].apply(lambda x: f"{x:.1f}")

display_df.columns = column_names

st.dataframe(display_df, use_container_width=True)

st.markdown("---")

# ============================================
# DETAILED VIEW - WITH LIQUIDITY METRICS
# ============================================
st.subheader("🔍 Detailed Exchange Comparison with Liquidity Analysis")

# Dropdown to select a pair
available_pairs = df['symbol'].tolist()[:100]
selected_pair = st.selectbox(
    "Select a trading pair to see prices and liquidity across all exchanges:",
    options=available_pairs,
    help="Shows which exchange has the cheapest/most expensive price AND liquidity metrics"
)

if selected_pair and all_prices_df is not None:
    # Filter for selected symbol
    pair_prices = all_prices_df[all_prices_df['symbol'] == selected_pair]
    
    if not pair_prices.empty:
        # ============================================
        # PRICE COMPARISON SECTION
        # ============================================
        st.write("### 💰 Price Comparison")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            best_idx = pair_prices['current_price'].idxmin()
            best_exchange = pair_prices.loc[best_idx, 'exchange_name']
            best_price = pair_prices.loc[best_idx, 'current_price']
            st.success(f"**🟢 CHEAPEST: {best_exchange}**\n\n{format_price(best_price)}")
        
        with col2:
            worst_idx = pair_prices['current_price'].idxmax()
            worst_exchange = pair_prices.loc[worst_idx, 'exchange_name']
            worst_price = pair_prices.loc[worst_idx, 'current_price']
            st.error(f"**🔴 MOST EXPENSIVE: {worst_exchange}**\n\n{format_price(worst_price)}")
        
        with col3:
            spread_for_pair = (worst_price - best_price) / best_price * 100
            st.info(f"**💡 Potential Profit**\n\n{spread_for_pair:.4f}%\n(before fees)")
        
        # ============================================
        # LIQUIDITY ANALYSIS TABLE
        # ============================================
        st.write("### 💧 Liquidity Analysis by Exchange")
        st.caption("Higher volume = easier to execute trades without price slippage")
        
        # Build liquidity table
        liquidity_rows = []
        
        for _, row in pair_prices.iterrows():
            exchange = row['exchange_name']
            price = row['current_price']
            
            # Get liquidity metrics
            vol_1h = row.get('volume_usd_1h', 0)
            vol_24h = row.get('volume_usd_24h', 0)
            buy_vol = row.get('buy_volume_usd_1h', 0)
            sell_vol = row.get('sell_volume_usd_1h', 0)
            net_flow = row.get('net_flows_usd_1h', 0)
            
            # Calculate buy/sell ratio
            if sell_vol > 0:
                buy_sell_ratio = buy_vol / sell_vol
            else:
                buy_sell_ratio = 1.0
            
            # Get liquidity rating
            rating, rating_color, rating_desc = get_liquidity_rating(vol_1h, buy_sell_ratio, net_flow)
            
            # Determine market sentiment
            if net_flow > 0:
                sentiment = "📈 Buying pressure (net inflow)"
                sentiment_color = "green"
            elif net_flow < 0:
                sentiment = "📉 Selling pressure (net outflow)"
                sentiment_color = "red"
            else:
                sentiment = "⚖️ Neutral"
                sentiment_color = "gray"
            
            liquidity_rows.append({
                'Exchange': exchange,
                'Price': format_price(price),
                '24h Volume': format_volume(vol_24h),
                '1h Volume': format_volume(vol_1h),
                'Buy/Sell Ratio': f"{buy_sell_ratio:.2f}",
                '1h Net Flow': format_volume(net_flow),
                'Liquidity': rating,
                'Sentiment': sentiment,
                'Volume (USD)': vol_1h  # For sorting
            })
        
        liquidity_df = pd.DataFrame(liquidity_rows)
        liquidity_df = liquidity_df.sort_values('Volume (USD)', ascending=False)
        liquidity_df = liquidity_df.drop('Volume (USD)', axis=1)
        
        st.dataframe(liquidity_df, use_container_width=True)
        
        # ============================================
        # LIQUIDITY VISUALIZATION
        # ============================================
        col1, col2 = st.columns(2)
        
        with col1:
            # Volume bar chart
            vol_chart_data = pair_prices[['exchange_name', 'volume_usd_24h']].copy()
            vol_chart_data = vol_chart_data.sort_values('volume_usd_24h', ascending=True)
            
            fig_vol = px.bar(
                vol_chart_data,
                x='volume_usd_24h',
                y='exchange_name',
                orientation='h',
                title="📊 24h Trading Volume by Exchange",
                labels={'volume_usd_24h': 'Volume (USD)', 'exchange_name': 'Exchange'},
                color='volume_usd_24h',
                color_continuous_scale='Blues'
            )
            fig_vol.update_layout(height=400)
            st.plotly_chart(fig_vol, use_container_width=True)
        
        with col2:
            # Buy/Sell ratio chart
            sentiment_data = pair_prices[['exchange_name', 'buy_volume_usd_1h', 'sell_volume_usd_1h']].copy()
            sentiment_data = sentiment_data.fillna(0)
            
            fig_sentiment = go.Figure()
            fig_sentiment.add_trace(go.Bar(
                name='Buy Volume',
                x=sentiment_data['exchange_name'],
                y=sentiment_data['buy_volume_usd_1h'],
                marker_color='green'
            ))
            fig_sentiment.add_trace(go.Bar(
                name='Sell Volume',
                x=sentiment_data['exchange_name'],
                y=sentiment_data['sell_volume_usd_1h'],
                marker_color='red'
            ))
            fig_sentiment.update_layout(
                title="📈 Buy vs Sell Volume (Last Hour)",
                xaxis_title="Exchange",
                yaxis_title="Volume (USD)",
                barmode='group',
                height=400
            )
            st.plotly_chart(fig_sentiment, use_container_width=True)
        
        # ============================================
        # EXCHANGE RECOMMENDATION
        # ============================================
        st.write("### 🎯 Exchange Recommendation")
        
        # Find best exchange for buying (cheapest + good liquidity)
        best_buy_candidates = pair_prices.copy()
        best_buy_candidates['liquidity_score'] = best_buy_candidates['volume_usd_1h']
        best_buy_candidates = best_buy_candidates.sort_values(['current_price', 'volume_usd_1h'], ascending=[True, False])
        
        # Find best exchange for selling (most expensive + good liquidity)
        best_sell_candidates = pair_prices.copy()
        best_sell_candidates['liquidity_score'] = best_sell_candidates['volume_usd_1h']
        best_sell_candidates = best_sell_candidates.sort_values(['current_price', 'volume_usd_1h'], ascending=[False, False])
        
        rec_col1, rec_col2 = st.columns(2)
        
        with rec_col1:
            best_buy = best_buy_candidates.iloc[0]
            st.success(f"""
            **🟢 BEST EXCHANGE TO BUY: {best_buy['exchange_name']}**
            
            - Price: {format_price(best_buy['current_price'])}
            - 24h Volume: {format_volume(best_buy.get('volume_usd_24h', 0))}
            - Liquidity Rating: {get_liquidity_rating(best_buy.get('volume_usd_1h', 0))[0]}
            """)
        
        with rec_col2:
            best_sell = best_sell_candidates.iloc[0]
            st.error(f"""
            **🔴 BEST EXCHANGE TO SELL: {best_sell['exchange_name']}**
            
            - Price: {format_price(best_sell['current_price'])}
            - 24h Volume: {format_volume(best_sell.get('volume_usd_24h', 0))}
            - Liquidity Rating: {get_liquidity_rating(best_sell.get('volume_usd_1h', 0))[0]}
            """)
        
        # Warning for low liquidity
        low_liquidity_exchanges = [row for row in liquidity_rows if 'LOW' in row['Liquidity'] or 'VERY LOW' in row['Liquidity']]
        if low_liquidity_exchanges:
            st.warning(f"⚠️ **Low Liquidity Warning:** {len(low_liquidity_exchanges)} exchange(s) have low trading volume. Trading there may cause significant price slippage.")
            for ex in low_liquidity_exchanges[:3]:
                st.caption(f"   - {ex['Exchange']}: {ex['Liquidity']}")

# ============================================
# FOOTER
# ============================================
st.markdown("---")
st.markdown(
    f"""
    <div style='text-align: center; color: gray; font-size: 12px;'>
    <b>💡 How to Interpret This Dashboard</b><br><br>
    <b>Spread %</b> = Price difference between cheapest and most expensive exchange<br>
    <b>Liquidity Rating</b>: 🟢 Excellent (>$100M/hr) → 🟡 Good ($10M-$100M) → 🟠 Moderate ($1M-$10M) → 🔴 Low (<$1M)<br>
    <b>Buy/Sell Ratio</b> > 1.5 = Strong buying pressure, < 0.67 = Strong selling pressure<br>
    <b>Net Flow</b> = Money flowing into/out of the exchange for this pair<br><br>
    📊 Data from CoinGlass API | 🚀 Dashboard built with Streamlit | ⏱️ Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    </div>
    """,
    unsafe_allow_html=True
)