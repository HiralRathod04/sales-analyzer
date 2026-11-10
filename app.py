import streamlit as st
import pandas as pd
from pathlib import Path
from analyzer import (profile_data, clean_data, calculate_rfm, run_forecast,
                      guess_columns)
from hero import show_hero

st.set_page_config(page_title="Sales Analyzer", page_icon="📊", layout="wide")


def load_css(filename):
    path = Path(__file__).parent / filename
    if path.exists():
        st.markdown("<style>" + path.read_text(encoding="utf-8") + "</style>",
                    unsafe_allow_html=True)
    else:
        st.warning("styles.css not found, using the default look.")


load_css("styles.css")
show_hero()

# ---------- Upload ----------
uploaded = st.file_uploader("Upload a sales CSV", type="csv")

if uploaded is not None:
    try:
        df = pd.read_csv(uploaded)
    except UnicodeDecodeError:
        uploaded.seek(0)
        df = pd.read_csv(uploaded, encoding="ISO-8859-1")

    st.success("Loaded " + str(len(df)) + " rows")
    st.dataframe(df.head(20))
    st.write(profile_data(df))

    # a new file means old results should disappear
    if st.session_state.get("file_name") != uploaded.name:
        st.session_state.pop("clean", None)
        st.session_state["file_name"] = uploaded.name

    # ---------- Column mapping ----------
    st.subheader("Tell me which column is which")
    st.caption("Pick (none) for anything your file does not have. "
               "Only a date and a sales amount (or quantity and price) are needed.")

    NONE = "(none)"
    options = [NONE] + list(df.columns)
    guesses = guess_columns(list(df.columns))

    fields = [
        ("Date", "Date of the order"),
        ("Revenue", "Sales amount (money per row)"),
        ("Quantity", "Quantity (units sold)"),
        ("Price", "Unit price"),
        ("Invoice", "Order or invoice ID"),
        ("Customer", "Customer ID"),
        ("Country", "Country"),
        ("Description", "Product name"),
    ]

    mapping = {}
    picked = []
    for standard, label in fields:
        guess = guesses.get(standard)
        position = options.index(guess) if guess in options else 0
        choice = st.selectbox(label, options, index=position,
                              key=standard + "_" + uploaded.name)
        if choice != NONE:
            mapping[choice] = standard
            picked.append(choice)

    if st.button("Analyze"):
        if len(set(picked)) < len(picked):
            st.error("Each dropdown needs a different column.")
        else:
            try:
                st.session_state["clean"] = clean_data(df, mapping)
            except ValueError as problem:
                st.error(str(problem))

# ---------- Results ----------
if "clean" in st.session_state:
    clean = st.session_state["clean"]
    st.header("Results")

    # ----- Filters (left sidebar) -----
    st.sidebar.header("Filters")
    first_day = clean["Date"].min().date()
    last_day = clean["Date"].max().date()
    dates = st.sidebar.date_input("Date range", value=(first_day, last_day),
                                  min_value=first_day, max_value=last_day)

    view = clean
    if len(dates) == 2:
        start, end = dates
        view = view[(view["Date"].dt.date >= start) & (view["Date"].dt.date <= end)]

    if "Country" in view.columns:
        countries = sorted(view["Country"].dropna().unique())
        chosen = st.sidebar.multiselect("Country", countries, default=countries)
        view = view[view["Country"].isin(chosen)]

    if len(view) == 0:
        st.warning("No data matches these filters.")
        st.stop()

    # ----- KPI cards (only the ones the data supports) -----
    total_revenue = view["Revenue"].sum()
    kpis = [("Total revenue", f"{total_revenue:,.0f}")]
    if "Customer" in view.columns:
        kpis.append(("Customers", f"{view['Customer'].nunique():,}"))
    if "Invoice" in view.columns:
        orders = view["Invoice"].nunique()
        kpis.append(("Orders", f"{orders:,}"))
        kpis.append(("Avg order value", f"{total_revenue / orders:,.0f}"))

    boxes = st.columns(len(kpis))
    for box, (label, value) in zip(boxes, kpis):
        box.metric(label, value)

    # ----- Charts -----
    st.subheader("Revenue by month")
    monthly = view.set_index("Date")["Revenue"].resample("MS").sum()
    st.line_chart(monthly)
    st.caption("The last month may be incomplete if the data ends part-way through it.")

    if "Description" in view.columns:
        st.subheader("Top 10 products by revenue")
        top_products = view.groupby("Description")["Revenue"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_products)

    if "Country" in view.columns:
        st.subheader("Top 10 countries by revenue")
        top_countries = view.groupby("Country")["Revenue"].sum().sort_values(ascending=False).head(10)
        st.bar_chart(top_countries)

    st.subheader("Revenue by day of the week")
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    by_day = view.groupby(view["Date"].dt.day_name())["Revenue"].sum().reindex(days).fillna(0)
    st.bar_chart(by_day)

    # ----- Customer segments -----
    st.subheader("Customer segments (RFM)")
    if "Customer" not in view.columns or "Invoice" not in view.columns:
        st.info("Customer segments need a Customer and an Invoice column.")
    elif view["Customer"].nunique() < 5:
        st.info("Need at least 5 customers to build segments.")
    else:
        rfm = calculate_rfm(view)
        st.bar_chart(rfm["Segment"].value_counts())
        st.write("Average behaviour of each segment")
        st.dataframe(rfm.groupby("Segment")[["Recency", "Frequency", "Monetary"]].mean().round(1))
        st.write("Top 20 customers by spend")
        st.dataframe(rfm.sort_values("Monetary", ascending=False).head(20))

    # ----- Forecast -----
    st.subheader("Sales forecast")
    span = (view["Date"].max() - view["Date"].min()).days

    if span < 60:
        st.info("Need at least 60 days of data to build a forecast.")
    else:
        try:
            result = run_forecast(view)
        except Exception:
            st.error("Could not build a forecast for this data.")
        else:
            metrics = result["metrics"]
            st.write("Model comparison (smaller MAE and RMSE are better, R2 closer to 1 is better)")
            st.dataframe(metrics)

            best = metrics.loc["MAE", ["Linear Regression", "Random Forest"]].idxmin()
            average_day = view.set_index("Date")["Revenue"].resample("D").sum().mean()
            error_pct = metrics.loc["MAE", best] / average_day * 100
            st.write(f"Best model by average error: **{best}**, typically off by about "
                     f"{error_pct:.0f}% of an average day's revenue.")

            chart = pd.DataFrame({"Actual": result["actual"]})
            for name, values in result["predictions"].items():
                chart[name] = values
            st.line_chart(chart)
            st.caption("Models learn weekly and monthly patterns from past sales. "
                       "They cannot predict very large one-off orders.")
