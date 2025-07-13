import os
from pymongo import MongoClient
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
try:
    from dotenv import load_dotenv

    # Load env vars
    load_dotenv()
except Exception as e:
    print("e is ",e)


# returns 'light' or 'dark'
theme = st.get_option("theme.base")
if theme == "dark":
    plotly_template = "plotly_dark"
    ann_bg = "rgba(0,0,0,0.75)"
    ann_border = "white"
    ann_font_color = "white"
else:
    plotly_template = "plotly_white"
    ann_bg = "rgba(255,255,255,0.8)"
    ann_border = "gray"
    ann_font_color = "black"



# ─── 1. App configuration ────────────────────────────────────────────────
st.set_page_config(page_title="API Logs Dashboard", layout="wide")
st.title("📊 API Logs Dashboard")

# ─── 2. Connect to MongoDB ───────────────────────────────────────────────
MONGODB_URI = os.getenv("MONGO_URI")
client = MongoClient(MONGODB_URI)
db = client["markly"]
collection = db["APILogs"]



log_msg = ""
# ─── 3. Load & cache data ────────────────────────────────────────────────
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

def filter_my_df(df,lv,clm):
    init_r = df.shape[0]
    df = df[df[clm].isin(lv)]
    final_r = df.shape[0]
    delta_r = init_r-final_r
    global log_msg
    log_msg += f"Column {clm}\nafter filtering \nthe rows dropped from {init_r} to {final_r}\ni.e. delta is {delta_r}\n"
    #st.text()
    return df

df_ori = load_data()
with st.expander("original data"):
    st.dataframe(df_ori)
# ─── 4. Sidebar filters ──────────────────────────────────────────────────
st.sidebar.header("Filter API logs")

df_ori['path'] = df_ori.apply(lambda x : x['function'] if x['path']==-1 else x['path'],axis=1)
df_ori['is_valid_row'] = df_ori.apply(is_valid_row,axis=1)
df_ori_shape = df_ori.shape[0]
df =  df_ori[df_ori['is_valid_row']==1]
df_shape = df.shape[0]

log_msg += f"After filtering invalid rows\n{df_ori_shape-df_shape} rows dropped, now left with {df_shape} rows\n\n"
#st.text()


# Time-window dropdown
time_windows = {
    "Last 24 Hours": pd.Timedelta(days=1),
    "Last 3 Days":   pd.Timedelta(days=3),
    "Last 7 Days":   pd.Timedelta(days=7),
    "Last 28 Days":  pd.Timedelta(days=28),
    "Last 1 Year":   pd.Timedelta(days=365),
}
sel_tw = st.sidebar.selectbox(
    "Time Window",
    options=list(time_windows.keys()),
    index=2
)
cutoff = pd.Timestamp.now() - time_windows[sel_tw]
df = df[df["timestamp"] >= cutoff]


statuses   = df["status_code"].unique()
functions = df["function"].unique()

# Example IP-mapping & filter
ips_mapping = {'vercel':'44.227.217.144','amritansh_local_computer':'192.168.1.7'}
sel_ips = st.multiselect("Client IP", options=list(ips_mapping.keys()), default=['vercel'])
sel_ips_addresses = [ips_mapping[k] for k in sel_ips]
df = filter_my_df(df,sel_ips_addresses,"public_ip")
    
sel_status  = st.sidebar.multiselect("Status",    options=statuses, default=statuses)
df = filter_my_df(df,statuses,"status_code")

methods = set(allowed_vals['method'])
sel_methods = st.sidebar.multiselect("Method",    options=methods, default=methods)
df = filter_my_df(df,sel_methods,"method")

paths = set(allowed_vals[allowed_vals['method'].isin(sel_methods)]['path']).union(set(functions))
sel_paths   = st.sidebar.multiselect("Path",      options=paths,    default=[])
df = filter_my_df(df,sel_paths,"path")

if df.empty:
    st.warning("No data matches your filters. Try broadening them.")
    st.stop()

# ─── 5. Grouping frequency ───────────────────────────────────────────────
freq_map = {
    "6 Hours": "6H",
    "1 Day": "1D",
    "3 Day": "3D",
    "1 Week": "7D"
}

sel_bucket_size   = st.sidebar.selectbox("Bucket Size", options=freq_map.keys(),index=2)

freq = freq_map[sel_bucket_size]

agg = (
    df
    .groupby(pd.Grouper(key="timestamp", freq=freq))
    .agg(
        count=("process_time", "size"),
        mean=("process_time", "mean"),
        min=("process_time", "min"),
        max=("process_time", "max"),
        std=("process_time", "std")
    )
    .reset_index()
)

# ─── 6. Plotly time-series with annotations ─────────────────────────────
fig = go.Figure()

# Only the count trace
fig.add_trace(go.Scatter(
    x=agg["timestamp"],
    y=agg["count"],
    mode="lines+markers",
    name="Count"
))

# Add a light grid
fig.update_xaxes(showgrid=True)
fig.update_yaxes(showgrid=True)

# Annotate each point with the 2×2 grid of stats
for _, row in agg.iterrows():
    # two rows, two columns: min|max on first, mean|std on second
    text = (
        f"<b>min:</b> {row['min']:.2f}<br><b>max:</b> {row['max']:.2f}<br>"
        f"<b>mean:</b> {row['mean']:.2f}<br>"
    )
    fig.add_annotation(
        x=row["timestamp"],
        y=row["count"],
        text=text,
        showarrow=False,
        align="left",
        xanchor="center",
        yanchor="bottom",
        bgcolor="rgba(255,255,255,0.8)",
        bordercolor="gray",
        borderwidth=1,
        font=dict(size=10, family="monospace")
    )
# switch to the correct template
fig.update_layout(
    template=plotly_template,
    title=f"API Call Count (over {sel_tw}), grouped by {sel_bucket_size}",
    xaxis_title="Time",
    yaxis_title="Count of process_time",
    hovermode="x unified",
    margin=dict(l=40, r=40, t=60, b=40),
)
# bulk-update all annotations so they use your dark/light styling
fig.update_annotations(
    bgcolor=ann_bg,
    bordercolor=ann_border,
    font_color=ann_font_color,
    font_size=10,
    font_family="monospace"
)
st.plotly_chart(fig, use_container_width=True)

# ─── 7. Show raw data option ─────────────────────────────────────────────
with st.expander("Show raw filtered data and logs"):
    st.dataframe(df.sort_values("timestamp", ascending=False), height=300)
    st.text(log_msg)

