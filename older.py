import os
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
# Load env vars
load_dotenv()
# ─── 1. App configuration ────────────────────────────────────────────────
st.set_page_config(page_title="API Logs Dashboard", layout="wide")
st.title("📊 API Logs Dashboard")

# ─── 2. Connect to MongoDB ───────────────────────────────────────────────
MONGODB_URI = os.getenv(
    "MONGO_URI")
#st.text(MONGODB_URI)
client = MongoClient(MONGODB_URI)
db = client["markly"]
collection = db["APILogs"]

# ─── 3. Load & cache data ────────────────────────────────────────────────
#@st.cache_data(show_spinner=True)
def load_data():
    docs = list(collection.find({}))
    df = pd.DataFrame(docs)
    
    df = df.fillna(-1)

    # ensure timestamp is datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    # derive date for convenience
    df["date"] = df["timestamp"].dt.date
    clms = [
        "timestamp", "path", "method", "type",
        "process_time", "status_code", "public_ip", "date", "fu"
    ]
    # select only the columns we need
    return df

def is_valid_row(r):
    path = str(r['path'])
    valid = 1
    if "//" in path:
        valid = 0
    return valid


def filter_my_df(df,lv,clm):
    init_r = df.shape[0]
    df = df[df[clm].isin(lv)]
    final_r = df.shape[0]
    delta_r = init_r-final_r
    st.text(f"Column {clm}\nafter filtering \nthe rows dropped from {init_r} to {final_r}\ni.e. delta is {delta_r}")
    return df

df_ori = load_data()

df_ori['path'] = df_ori.apply(lambda x : x['function'] if x['path']==-1 else x['path'],axis=1)
st.dataframe(df_ori.tail())
df_ori['is_valid_row'] = df_ori.apply(is_valid_row,axis=1)
df_ori_shape = df_ori.shape[0]
df =  df_ori[df_ori['is_valid_row']==1]
df_shape = df.shape[0]
st.text(f"{df_ori_shape-df_shape} rows dropped, now left with {df_shape} rows")
# ─── 4. Sidebar filters ──────────────────────────────────────────────────
st.sidebar.header("Filter API logs")
paths      = df["path"].unique()
methods    = df["method"].unique()
statuses   = df["status_code"].unique()
ips        = df["public_ip"].unique()
functions = df["function"].unique()

ips_mapping = {'vercel':'44.227.217.144','amritansh_local_computer':'192.168.1.7'}

ips = list(ips_mapping.keys())
sel_ips     = st.multiselect("Client IP", options=ips,      default=[])




def current_allowed_values():

    # Constructing the API endpoints DataFrame
    data = {
        "method": [
            # Auth
            "POST", "POST", "POST", "POST", "POST", "POST", "POST",
            # Bookmarks
            "POST", "POST", "GET", "DELETE", "PUT", "POST", "GET", "POST", "POST", "DELETE", "GET",
            # Collections
            "POST", "GET", "PUT", "DELETE",
            # Comments
            "POST", "GET", "PUT",
            # Votes
            "GET", "POST",
            # Ratings
            "POST",
            # Subscriptions
            "POST", "DELETE", "GET",
            # Users
            "GET", "PUT", "POST",
            # Deployment
            "GET",
            # WebSocket
            "WebSocket"
        ],
        "path": [
            # Auth
            "/api/auth/send-otp", "/api/auth/verify-otp", "/api/auth/signup", "/api/auth/google-signin", "/api/auth/login",
            "/api/auth/token_validation", "/api/auth/logout",
            # Bookmarks
            "/api/browser_bookmarks", "/api/bookmarks", "/api/bookmarks", "/api/bookmarks", "/api/bookmarks",
            "/api/bookmarks/validate_url", "/api/bookmarks/search", "/api/bookmarks/views",
            "/api/bookmarks/favourites", "/api/bookmarks/favourites", "/api/bookmarks/favourites",
            # Collections
            "/api/collections", "/api/collections", "/api/collections", "/api/collections",
            # Comments
            "/api/bookmarks/comments", "/api/bookmarks/comments", "/api/bookmarks/comments",
            # Votes
            "/api/users/votedBookmarks", "/api/bookmarks/votes",
            # Ratings
            "/api/bookmarks/ratings",
            # Subscriptions
            "/api/users/subscribe", "/api/users/subscribe", "/api/users/subscribe",
            # Users
            "/api/users", "/api/users", "/api/save_image",
            # Deployment
            "/api/deployment_details",
            # WebSocket
            "/api/ws"
        ]
    }

    df = pd.DataFrame(data)
    return df




allowed_vals = current_allowed_values()



# Using dictionary comprehension
sel_ips_addresses = [ips_mapping[k] for k in sel_ips]
#print(f"Filtered dictionary (comprehension): {filtered_dict_comp}")
df = filter_my_df(df,sel_ips_addresses,"public_ip")

sel_status  = st.multiselect("Status",    options=statuses, default=statuses)
df = filter_my_df(df,statuses,"status_code")


methods = set(allowed_vals['method'])
sel_methods = st.multiselect("Method",    options=methods, default=methods)
df = filter_my_df(df,sel_methods,"method")

paths = set(allowed_vals[allowed_vals['method'].isin(sel_methods)]['path']).union(set(functions))
sel_paths   = st.multiselect("Path",      options=paths,    default=[])
df = filter_my_df(df,paths,"path")

#sel_functions   = st.multiselect("Functions",      options=functions,    default=[])
#df = filter_my_df(df,functions,"function")

# grouping frequency
freq_map = {
    "1 Hour": "1H",
    "6 Hours": "6H",
    "12 Hours": "12H",
    "1 Day": "1D",
    "1 Week": "7D"
}
freq_label = st.sidebar.selectbox(
    "Group by",
    options=list(freq_map.keys()),
    index=list(freq_map.values()).index("1D")
)
freq = freq_map[freq_label]


dff = df

if dff.empty:
    st.warning("No data matches your filters. Try broadening them.")
    st.stop()

# group into time buckets and compute stats
agg = (
    dff
    .groupby(pd.Grouper(key="timestamp", freq=freq))["process_time"]
    .agg(count="size", mean="mean", min="min", max="max", std="std")
    .reset_index()
)

# ─── 6. Plotly time-series ──────────────────────────────────────────────
fig = go.Figure()
for metric in ["count", "mean", "min", "max", "std"]:
    fig.add_trace(go.Scatter(
        x=agg["timestamp"],
        y=agg[metric],
        mode="lines+markers",
        name=metric
    ))

fig.update_layout(
    title=f"API calls aggregated by {freq_label}",
    xaxis_title="Time",
    yaxis_title="Process Time / Count",
    hovermode="x unified",
    margin=dict(l=40, r=40, t=60, b=40)
)

st.plotly_chart(fig, use_container_width=True)

# ─── 7. Show raw data option ─────────────────────────────────────────────
with st.expander("Show raw filtered data"):
    st.dataframe(dff.sort_values("timestamp", ascending=False), height=300)
