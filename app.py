# Importing important libraries
import numpy as np
import pandas as pd
from pathlib import Path
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Maps each standardized internal column name to the list of possible
COLUMN_SYNONYMS = {
    "transaction_id": ["transaction_id", "transaction id", "id"],
    "transaction_date": ["transaction_date", "transaction date", "date"],
    "transaction_time": ["transaction_time", "transaction time", "time"],
    "store_location": ["store_location", "store location", "location"],
    "product_category": ["product_category", "product category", "category"],
    "product_type": ["product_type", "product type", "type"],
    "product_detail": ["product_detail", "product detail", "item", "product"],
    "unit_price": ["unit_price", "unit price", "price"],
    "transaction_qty": ["transaction_qty", "transaction qty", "quantity", "qty", "count"],
}

# Configure page
st.set_page_config(
    page_title="Product Optimization & Revenue Analytics",
    page_icon="☕",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Creating path for data
def resolve_data_path() -> Path:
    """Look in a fixed list of candidate locations for the sales CSV and
    return the first one that actually exists on disk. Raises if none found,
    so the caller can fall back to generated sample data instead."""
    candidates = [
        Path(__file__).resolve().parent / "data" / "Afficionado Coffee Roasters.xlsx - Transactions (2).csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError("No sales data file found. Please place the CSV in the project folder or data directory.")


# Setting up data caches
@st.cache_data(show_spinner=True)
def load_data() -> pd.DataFrame:
    """Load the real transactions CSV if available; otherwise generate a
    synthetic demo dataset so the dashboard is still usable out of the box.
    Cached by Streamlit so this only re-runs when inputs change."""
    try:
        data_path = resolve_data_path()
        df = pd.read_csv(data_path)
        df = _standardize_columns(df)
    except FileNotFoundError:
        df = _generate_sample_data() 

    return df

# Data loading & preparation
def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Rename whatever columns are present to the standardized internal names."""
    lower_map = {c.lower().strip().replace(" ", "_"): c for c in df.columns}
    rename_map = {}
    for std_name, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            if syn in lower_map:
                rename_map[lower_map[syn]] = std_name
                break
    df = df.rename(columns=rename_map)
    return df


def _generate_sample_data(n_rows: int = 6000, seed: int = 42) -> pd.DataFrame:
    """Create a realistic synthetic coffee-shop sales dataset for demo purposes."""
    rng = np.random.default_rng(seed)

    # Product catalog 
    catalog = {
        "Coffee": {
            "types": ["Drip Coffee", "Espresso", "Cold Brew"],
            "items": ["Brazilian Roast", "Colombian Roast", "House Blend",
                      "Dark Roast", "Ethiopian Single Origin"],
            "price_range": (2.5, 4.5),
        },
        "Tea": {
            "types": ["Brewed Tea", "Herbal Tea"],
            "items": ["Earl Grey", "Green Tea", "Chamomile", "Peppermint",
                      "Chai Latte"],
            "price_range": (2.5, 4.0),
        },
        "Bakery": {
            "types": ["Pastry", "Bread"],
            "items": ["Croissant", "Blueberry Muffin", "Scone", "Bagel",
                      "Banana Bread"],
            "price_range": (2.0, 4.5),
        },
        "Specialty": {
            "types": ["Latte", "Mocha", "Frappuccino"],
            "items": ["Vanilla Latte", "Caramel Macchiato", "Mocha Frappe",
                      "Hazelnut Latte", "Pumpkin Spice Latte"],
            "price_range": (4.0, 6.5),
        },
        "Merchandise": {
            "types": ["Drinkware", "Whole Bean"],
            "items": ["Ceramic Mug", "Travel Tumbler", "1lb Whole Bean Bag",
                      "Reusable Cup"],
            "price_range": (8.0, 18.0),
        },
    }

    store_locations = ["Downtown", "Uptown Square", "Riverside", "Airport Terminal"]
    # Six months of daily dates to spread transactions across for trend charts.
    dates = pd.date_range("2024-01-01", "2024-06-30", freq="D")

    categories = list(catalog.keys())
    # Weighted so "Coffee" is the most common category, mirroring a real coffee shop's mix.
    cat_weights = np.array([0.42, 0.16, 0.20, 0.15, 0.07])

    rows = []
    for i in range(n_rows):
        # Randomly pick a category, then a type/item/price within that category.
        cat = rng.choice(categories, p=cat_weights)
        info = catalog[cat]
        p_type = rng.choice(info["types"])
        item = rng.choice(info["items"])
        low, high = info["price_range"]
        price = round(rng.uniform(low, high), 2)
        # Quantity skewed toward 1 (most orders are single-item), rarely 3.
        qty = int(rng.choice([1, 1, 1, 2, 2, 3], p=[0.45, 0.2, 0.15, 0.1, 0.06, 0.04]))
        date = rng.choice(dates)
        # Store distribution weighted so Downtown gets the most foot traffic.
        store = rng.choice(store_locations, p=[0.35, 0.25, 0.25, 0.15])
        rows.append(
            {
                "transaction_id": i + 1,
                "transaction_date": pd.Timestamp(date),
                "store_location": store,
                "product_category": cat,
                "product_type": p_type,
                "product_detail": item,
                "unit_price": price,
                "transaction_qty": qty,
            }
        )
    return pd.DataFrame(rows)


# Sidebar
st.sidebar.title("☕ Dashboard Controls")

# Load data once (cached)
raw_df = load_data()

st.sidebar.divider()
st.sidebar.subheader("Filters")

store_options = sorted(raw_df["store_location"].dropna().unique().tolist())
selected_stores = st.sidebar.multiselect(
    "Store location", options=store_options, default=store_options
)

category_options = sorted(raw_df["product_category"].dropna().unique().tolist())
selected_categories = st.sidebar.multiselect(
    "Product category", options=category_options, default=category_options
)

type_pool = raw_df[raw_df["product_category"].isin(selected_categories)] if selected_categories else raw_df
type_options = sorted(type_pool["product_type"].dropna().unique().tolist())
selected_types = st.sidebar.multiselect(
    "Product type", options=type_options, default=type_options
)

has_dates = "transaction_date" in raw_df.columns and raw_df["transaction_date"].notna().any()
if has_dates:
    min_date = raw_df["transaction_date"].min().date()
    max_date = raw_df["transaction_date"].max().date()
    date_range = st.sidebar.date_input(
        "Date range", value=(min_date, max_date), min_value=min_date, max_value=max_date
    )
else:
    date_range = None

st.sidebar.divider()
st.sidebar.subheader("Display Options")

# Controls how many products show up in the "Top N" ranking chart/table.
top_n = st.sidebar.slider("Top-N products", min_value=5, max_value=50, value=10, step=1)

# Lets the user toggle whether "top" means highest revenue or highest volume sold.
rank_metric = st.sidebar.radio("Rank products by", ["Revenue", "Volume (units sold)"], horizontal=False)

# Apply filter
df = raw_df.copy()

if selected_stores:
    df = df[df["store_location"].isin(selected_stores)]
if selected_categories:
    df = df[df["product_category"].isin(selected_categories)]
if selected_types:
    df = df[df["product_type"].isin(selected_types)]
if has_dates and isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
    df = df[
        (df["transaction_date"] >= pd.Timestamp(start))
        & (df["transaction_date"] <= pd.Timestamp(end))
    ]

# Header + KPIs
st.title("☕ Product Optimization & Revenue Contribution Analytics")
st.caption(
    "Evaluate product popularity, revenue contribution, and category-level "
    "performance to support menu optimization decisions."
)

# If the filters leave no rows
if df.empty:
    st.warning("No data matches the current filter selection. Adjust the filters in the sidebar.")
    st.stop()

# Ensure `revenue` column exists
if "revenue" not in df.columns:
    if "unit_price" in df.columns and "transaction_qty" in df.columns:
        df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0)
        df["transaction_qty"] = pd.to_numeric(df["transaction_qty"], errors="coerce").fillna(0).astype(int)
        df["revenue"] = df["unit_price"] * df["transaction_qty"]
    elif "total" in df.columns:
        df["revenue"] = pd.to_numeric(df["total"], errors="coerce").fillna(0)
    else:
        st.warning(
            "Dataset does not include a `revenue` column and I couldn't compute it automatically."
            " Please provide `unit_price` and `transaction_qty` columns if available."
        )
        df["revenue"] = 0

# Top-level KPIs shown as metric cards at the top of the dashboard.
total_revenue = df["revenue"].sum()
total_units = df["transaction_qty"].sum()
n_products = df["product_detail"].nunique()
avg_order_value = total_revenue / max(df["transaction_qty"].sum(), 1)  

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Revenue", f"${total_revenue:,.0f}")
k2.metric("Units Sold", f"{total_units:,.0f}")
k3.metric("Active Products", f"{n_products:,}")
k4.metric("Avg. Revenue / Unit", f"${avg_order_value:,.2f}")

st.divider()

# Aggregations
product_agg = (
    df.groupby(["product_detail", "product_category", "product_type"], as_index=False)
    .agg(
        revenue=("revenue", "sum"),
        units_sold=("transaction_qty", "sum"),
        avg_price=("unit_price", "mean"),
        transactions=("revenue", "count"),
    )
)
product_agg["revenue_share_%"] = (product_agg["revenue"] / total_revenue * 100).round(2)

# Per-category rollup used for the pie chart
category_agg = (
    df.groupby("product_category", as_index=False)
    .agg(revenue=("revenue", "sum"), units_sold=("transaction_qty", "sum"))
    .sort_values("revenue", ascending=False)
)
category_agg["revenue_share_%"] = (category_agg["revenue"] / total_revenue * 100).round(2)

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(
    [
        "🏆 Product Ranking",
        "🥧 Category Distribution",
        "📈 Popularity vs Revenue",
        "🔍 Product Drill-Down",
    ])
    # Product ranking
with tab1:
    st.subheader(f"Top {top_n} Products by {rank_metric}")
    metric_col = "revenue" if rank_metric == "Revenue" else "units_sold"
    ranked = product_agg.sort_values(metric_col, ascending=False).head(top_n)

    # Horizontal bar chart of the top N products, colored by category.
    fig_rank = px.bar(
        ranked.sort_values(metric_col), 
        x=metric_col,
        y="product_detail",
        color="product_category",
        orientation="h",
        text=metric_col,
        labels={
            "product_detail": "Product",
            "revenue": "Revenue ($)",
            "units_sold": "Units Sold",
            "product_category": "Category",
        },
        title=f"Top {top_n} Products — Ranked by {rank_metric}",
    )
    fig_rank.update_traces(
        texttemplate="$%{text:,.0f}" if metric_col == "revenue" else "%{text:,.0f}",
        textposition="outside",
    )
    fig_rank.update_layout(height=max(400, 28 * top_n), yaxis_title=None)
    st.plotly_chart(fig_rank, use_container_width=True)

    # revenue ranking vs. volume ranking side by side,

    st.markdown("**Side-by-side comparison: Revenue vs. Volume rank**")
    col1, col2 = st.columns(2)
    with col1:
        top_rev = product_agg.sort_values("revenue", ascending=False).head(top_n)
        fig_rev = px.bar(
            top_rev.sort_values("revenue"),
            x="revenue", y="product_detail", orientation="h",
            title="By Revenue", labels={"product_detail": "", "revenue": "Revenue ($)"},
        )
        fig_rev.update_layout(height=max(350, 26 * top_n))
        st.plotly_chart(fig_rev, use_container_width=True)
    with col2:
        top_vol = product_agg.sort_values("units_sold", ascending=False).head(top_n)
        fig_vol = px.bar(
            top_vol.sort_values("units_sold"),
            x="units_sold", y="product_detail", orientation="h",
            title="By Volume", labels={"product_detail": "", "units_sold": "Units Sold"},
            color_discrete_sequence=["#ff7f0e"],
        )
        fig_vol.update_layout(height=max(350, 26 * top_n))
        st.plotly_chart(fig_vol, use_container_width=True)

# Category revenue distribution 
with tab2:
    st.subheader("Category Revenue Distribution")

    col1, col2 = st.columns([1, 1])
    with col1:
        # Donut chart showing each category's share of total revenue.
        fig_pie = px.pie(
            category_agg, names="product_category", values="revenue",
            title="Revenue Share by Category", hole=0.45,
        )
        fig_pie.update_traces(textinfo="percent+label")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        # Treemap drills
        fig_treemap = px.treemap(
            df,
            path=["product_category", "product_type"],
            values="revenue",
            title="Revenue Breakdown: Category → Product Type",
        )
        st.plotly_chart(fig_treemap, use_container_width=True)

    # Pareto (80/20) analysis
    st.markdown("**Pareto Analysis — Cumulative Revenue Contribution by Product**")
    pareto = product_agg.sort_values("revenue", ascending=False).reset_index(drop=True)
    pareto["cumulative_revenue"] = pareto["revenue"].cumsum()
    pareto["cumulative_%"] = (pareto["cumulative_revenue"] / total_revenue * 100).round(2)

    fig_pareto = go.Figure()
    fig_pareto.add_bar(x=pareto["product_detail"], y=pareto["revenue"], name="Revenue")
    
    fig_pareto.add_trace(
        go.Scatter(
            x=pareto["product_detail"], y=pareto["cumulative_%"],
            name="Cumulative %", yaxis="y2", mode="lines+markers",
            line=dict(color="firebrick"),
        )
    )
    
    fig_pareto.add_hline(y=80, line_dash="dot", line_color="gray", yref="y2")
    fig_pareto.update_layout(
        yaxis=dict(title="Revenue ($)"),
        yaxis2=dict(title="Cumulative %", overlaying="y", side="right", range=[0, 105]),
        xaxis=dict(showticklabels=False, title="Products (ranked by revenue)"),  # hide labels: too many products to fit
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig_pareto, use_container_width=True)

    # Call out in plain language how many products actually drive 80% of revenue.
    n_for_80 = (pareto["cumulative_%"] <= 80).sum() + 1
    pct_products_for_80 = round(n_for_80 / len(pareto) * 100, 1)
    st.info(
        f"**{n_for_80}** of **{len(pareto)}** products (**{pct_products_for_80}%**) "
        f"generate roughly 80% of total revenue."
    )

# Popularity vs revenue scatter plot
with tab3:
    st.subheader("Popularity vs. Revenue Contribution")
    st.caption("Bubble size = revenue · Color = category · Position = units sold vs. revenue")

    # Each bubble is one product: x = units sold, y = revenue, bubble size

    fig_scatter = px.scatter(
        product_agg,
        x="units_sold",
        y="revenue",
        size="revenue",
        color="product_category",
        hover_name="product_detail",
        hover_data={"avg_price": ":.2f", "transactions": True, "revenue_share_%": True},
        size_max=45,
        labels={"units_sold": "Units Sold (Popularity)", "revenue": "Revenue ($)"},
        title="Product Popularity vs. Revenue",
    )

    med_units = product_agg["units_sold"].median()
    med_rev = product_agg["revenue"].median()
    fig_scatter.add_vline(x=med_units, line_dash="dot", line_color="gray")
    fig_scatter.add_hline(y=med_rev, line_dash="dot", line_color="gray")
    fig_scatter.update_layout(height=550)
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown(
        """
**How to read the quadrants**
- **Top-right** — high popularity & high revenue: your core menu drivers, protect and promote.
- **Top-left** — low popularity but high revenue: premium/high-price niche items.
- **Bottom-right** — high popularity but low revenue: high-volume, low-margin items; consider a price review.
- **Bottom-left** — low popularity & low revenue: candidates for menu rationalization.
"""
    )

# Product drill-down performance table
with tab4:
    st.subheader("Product Drill-Down Performance Table")
    search = st.text_input("Search product name", "")
    table = product_agg.sort_values("revenue", ascending=False).copy()
    if search:
        table = table[table["product_detail"].str.contains(search, case=False, na=False)]

    table_display = table.rename(
        columns={
            "product_detail": "Product",
            "product_category": "Category",
            "product_type": "Type",
            "revenue": "Revenue ($)",
            "units_sold": "Units Sold",
            "avg_price": "Avg. Unit Price ($)",
            "transactions": "# Transactions",
            "revenue_share_%": "Revenue Share (%)",
        }
    )

    st.dataframe(
        table_display.style.format(
            {
                "Revenue ($)": "${:,.2f}",
                "Units Sold": "{:,.0f}",
                "Avg. Price ($)": "${:,.2f}",
                "# Transactions": "{:,.0f}",
                "Revenue Share (%)": "{:.2f}%",
            }
        ),
        use_container_width=True,
        height=500,
    )

    csv_bytes = table_display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download filtered table as CSV",
        data=csv_bytes,
        file_name="product_performance.csv",
        mime="text/csv",
    )

    # Single-product deep dive
    st.markdown("---")
    st.markdown("**Single Product Deep-Dive**")
    product_choice = st.selectbox(
        "Select a product", options=sorted(product_agg["product_detail"].unique())
    )
    prod_df = df[df["product_detail"] == product_choice]
    prod_row = product_agg[product_agg["product_detail"] == product_choice].iloc[0]

    # Quick metric cards for the selected product
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Revenue", f"${prod_row['revenue']:,.2f}")
    c2.metric("Units Sold", f"{prod_row['units_sold']:,.0f}")
    c3.metric("Revenue Share", f"{prod_row['revenue_share_%']:.2f}%")
    c4.metric("Avg. Price", f"${prod_row['avg_price']:,.2f}")

    # Daily revenue trend line for this product
    if has_dates and prod_df["transaction_date"].notna().any():
        daily = (
            prod_df.groupby(prod_df["transaction_date"].dt.date, as_index=False)
            .agg(revenue=("revenue", "sum"), units_sold=("transaction_qty", "sum"))
        )
        fig_trend = px.line(
            daily, x="transaction_date", y="revenue",
            title=f"Daily Revenue Trend — {product_choice}", markers=True,
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # Revenue-by-store breakdown for this product
    if prod_df["store_location"].nunique() > 1:
        by_store = (
            prod_df.groupby("store_location", as_index=False)
            .agg(revenue=("revenue", "sum"), units_sold=("transaction_qty", "sum"))
            .sort_values("revenue", ascending=False)
        )
        fig_store = px.bar(
            by_store, x="store_location", y="revenue",
            title=f"Revenue by Store — {product_choice}",
            labels={"store_location": "Store", "revenue": "Revenue ($)"},
        )
        st.plotly_chart(fig_store, use_container_width=True)


footer_html = """
<div style='
background: linear-gradient(135deg,#111827,#1f2937);
padding: 30px;
border-radius: 20px;
text-align: center;
border: 1px solid #374151;
margin-top: 30px;
'>

<h2 style='color:#f59e0b;'>
☕ Afficionado Coffee Roasters
</h2>

<p style='color:#d1d5db; font-size:16px;'>
Advanced Sales Trend & Time-Based Performance Analytics Dashboard
</p>

<div style='margin-top:20px;'>

<a href='https://www.afficionadocoffee.com/'
target='_blank'
style='
text-decoration:none;
background: linear-gradient(90deg,#f59e0b,#ef4444);
color:white;
padding:12px 20px;
border-radius:12px;
margin:10px;
display:inline-block;
font-weight:bold;
'>
🌐 Official Website
</a>

<a href='https://www.instagram.com/afficionado_coffee/'
target='_blank'
style='
text-decoration:none;
background: linear-gradient(90deg,#f59e0b,#ef4444);
color:white;
padding:12px 20px;
border-radius:12px;
margin:10px;
display:inline-block;
font-weight:bold;
'>
📸 Instagram
</a>

</div>

<p style='
color:#9ca3af;
margin-top:20px;
font-size:14px;
'>
Designed for Business Intelligence & Retail Analytics
</p>

</div>
"""

st.markdown(footer_html, unsafe_allow_html=True)

st.divider()
st.caption(
    "Built with Streamlit, Pandas & Plotly · Upload your own coffee-shop sales "
    "export (CSV/Excel) in the sidebar, or place a CSV in a local `data/` folder, "
    "to replace the demo dataset."
)
