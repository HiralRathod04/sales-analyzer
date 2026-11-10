from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import pandas as pd

# ---------- Settings ----------
REQUIRED = ["Invoice", "Customer", "Date", "Quantity", "Price"]
BASE_REQUIRED = ["Date"]
DATE_FORMATS = ["%m/%d/%Y %H:%M", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y"]
DEFAULT_MAPPING = {
    "InvoiceDate": "Date",
    "CustomerID": "Customer",
    "InvoiceNo": "Invoice",
    "Quantity": "Quantity",
    "UnitPrice": "Price",
}

# ---------- Guessing which column is which ----------
GUESS_WORDS = {
    "Date": ["order date", "invoicedate", "invoice date", "purchase date", "date"],
    "Revenue": ["sales", "revenue", "amount", "total"],
    "Quantity": ["quantity", "qty", "units"],
    "Price": ["unitprice", "unit price", "price"],
    "Invoice": ["order id", "invoiceno", "invoice", "transaction", "order"],
    "Customer": ["customer id", "customerid", "customer", "client"],
    "Country": ["country", "nation"],
    "Description": ["description", "product name", "product", "item"],
}

def guess_columns(columns):
    guesses = {}
    used = set()
    for standard, words in GUESS_WORDS.items():
        guesses[standard] = None
        for word in words:
            for col in columns:
                if col not in used and word in str(col).lower():
                    guesses[standard] = col
                    used.add(col)
                    break
            if guesses[standard] is not None:
                break
    return guesses

# ---------- Inspection ----------
def profile_data(data):
    return {
        "rows": len(data),
        "columns": data.shape[1],
        "missing_cells": int(data.isnull().sum().sum()),
        "duplicate_rows": int(data.duplicated().sum()),
        "missing_by_column": data.isnull().sum().to_dict(),
    }

# ---------- Cleaning steps ----------
def standardize_columns(data, mapping):
    data = data.copy()
    targets = set(mapping.values())
    # drop columns that already use a standard name but were not picked for it
    keep = [c for c in data.columns if c in mapping or c not in targets]
    data = data[keep].rename(columns=mapping)
    return data

def check_columns(data):
    missing = []
    for col in BASE_REQUIRED:
        if col not in data.columns:
            missing.append(col)
    has_revenue = "Revenue" in data.columns
    has_qty_price = "Quantity" in data.columns and "Price" in data.columns
    if not has_revenue and not has_qty_price:
        missing.append("Revenue (or both Quantity and Price)")
    if len(missing) > 0:
        raise ValueError("Missing columns: " + ", ".join(missing))
    return data

def remove_duplicates(data):
    data = data.copy()
    data = data.drop_duplicates()
    return data

def drop_missing_customers(data):
    data = data.copy()
    if "Customer" in data.columns:
        data = data.dropna(subset=["Customer"])
    return data

def remove_cancelled(data):
    data = data.copy()
    if "Invoice" in data.columns:
        data = data[~data["Invoice"].astype(str).str.match(r"^C\d")]
    return data

def remove_invalid(data):
    data = data.copy()
    if "Quantity" in data.columns and "Price" in data.columns:
        data = data[(data["Quantity"] > 0) & (data["Price"] > 0)]
    if "Revenue" in data.columns:
        data = data[data["Revenue"] > 0]
    return data

def remove_outliers(data):
    data = data.copy()
    col = "Quantity" if "Quantity" in data.columns else "Revenue"
    limit = data[col].quantile(0.9999)
    data = data[data[col] <= limit]
    return data

def convert_dates(data):
    data = data.copy()
    for fmt in DATE_FORMATS:
        try:
            data["Date"] = pd.to_datetime(data["Date"], format=fmt)
            return data
        except ValueError:
            continue
    raise ValueError("Could not understand the Date column format")

def add_revenue(data):
    data = data.copy()
    if "Revenue" not in data.columns:
        data["Revenue"] = data["Quantity"] * data["Price"]
    return data

# ---------- Full pipeline ----------
def clean_data(data, mapping=DEFAULT_MAPPING):
    data = standardize_columns(data, mapping)
    data = check_columns(data)
    data = remove_duplicates(data)
    data = drop_missing_customers(data)
    data = remove_cancelled(data)
    data = remove_invalid(data)
    data = remove_outliers(data)
    data = convert_dates(data)
    data = add_revenue(data)
    return data


# ---------- Forecasting ----------
def daily_sales(data):
    return data.set_index("Date")["Revenue"].resample("D").sum()

def make_features(daily):
    table = daily.to_frame(name="Revenue")
    table["day_of_week"] = table.index.dayofweek
    table["month"] = table.index.month
    table["lag_1"] = table["Revenue"].shift(1)
    table["lag_7"] = table["Revenue"].shift(7)
    return table.dropna()

def evaluate(y_true, y_pred):
    mae = mean_absolute_error(y_true, y_pred)
    rmse = mean_squared_error(y_true, y_pred) ** 0.5
    r2 = r2_score(y_true, y_pred)
    return {"MAE": round(mae), "RMSE": round(rmse), "R2": round(r2, 2)}

def run_forecast(clean):
    table = make_features(daily_sales(clean))
    features = ["day_of_week", "month", "lag_1", "lag_7"]
    split = int(len(table) * 0.8)
    X_train, X_test = table[features].iloc[:split], table[features].iloc[split:]
    y_train, y_test = table["Revenue"].iloc[:split], table["Revenue"].iloc[split:]

    lin = LinearRegression().fit(X_train, y_train)
    rf = RandomForestRegressor(n_estimators=200, random_state=42).fit(X_train, y_train)
    predictions = {"Linear Regression": lin.predict(X_test),
                   "Random Forest": rf.predict(X_test)}

    metrics = pd.DataFrame({"Baseline": evaluate(y_test, X_test["lag_1"]),
                            **{name: evaluate(y_test, p) for name, p in predictions.items()}})
    return {"metrics": metrics, "actual": y_test, "predictions": predictions}


# ---------- Customer segments (RFM) ----------
def segment_customer(row):
    if row["R_score"] >= 4 and row["F_score"] >= 4:
        return "Champions"
    elif row["R_score"] >= 3 and row["F_score"] >= 3:
        return "Loyal"
    elif row["R_score"] <= 2 and row["F_score"] >= 3:
        return "At Risk"
    elif row["R_score"] <= 2 and row["F_score"] <= 2:
        return "Lost"
    else:
        return "Potential"

def calculate_rfm(data):
    snapshot = data["Date"].max() + pd.Timedelta(days=1)
    last_purchase = data.groupby("Customer")["Date"].max()

    rfm = pd.DataFrame({
        "Recency": (snapshot - last_purchase).dt.days,
        "Frequency": data.groupby("Customer")["Invoice"].nunique(),
        "Monetary": data.groupby("Customer")["Revenue"].sum(),
    })

    rfm["R_score"] = pd.qcut(rfm["Recency"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
    rfm["F_score"] = pd.qcut(rfm["Frequency"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["M_score"] = pd.qcut(rfm["Monetary"].rank(method="first"), 5, labels=[1, 2, 3, 4, 5]).astype(int)
    rfm["Segment"] = rfm.apply(segment_customer, axis=1)
    return rfm
