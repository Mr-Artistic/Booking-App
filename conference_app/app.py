# region Chapter 1: Imports

import streamlit as st
import yaml
from yaml.loader import SafeLoader
from PIL import Image
import streamlit_authenticator as stauth
import time
from streamlit_lottie import st_lottie
import plotly.graph_objects as go
from datetime import datetime
import pandas as pd

# Custom Modules
from conference_app import config as cfg

from conference_app.functions import (
    init_db,
    get_bookings,
    booking_form,
    render_header_bar,
    build_vertical_day_time_timeline,  # using cached version from below
    build_timeline_figure_cached,
    st_red_alert,
    load_lottiefile,
    get_random_quote,
)

# endregion

# region Chapter 2: Page Layout

icon = Image.open("assets/logo.ico")

st.set_page_config(
    page_title="Booking App",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Report a bug": "mailto:sumiet_t@quantech.org.in",
        "About": "App Version 1.01  |  Developed by: Sumiet Talekar",
    },
)

# endregion


# region Chapter 3: User Authentication

UserAuth = False

if UserAuth:
    with open(".streamlit/cred.yaml") as file:
        auth_config = yaml.load(file, Loader=SafeLoader)

    authenticator = stauth.Authenticate(
        auth_config["credentials"],
        auth_config["cookie"]["name"],
        auth_config["cookie"]["key"],
        auth_config["cookie"]["expiry_days"],
    )

    authenticator.login(location="sidebar")

    # Read session values
    authentication_status = st.session_state.get("authentication_status")
    name = st.session_state.get("name")
    username = st.session_state.get("username")

    if not authentication_status:
        if authentication_status is False:
            st_red_alert("Username/password is incorrect")
        else:
            st_red_alert("Please login to access the Booking App (check sidebar).")
        st.stop()

    authenticator.logout(location="sidebar")


# endregion


# region Chapter 4: Header

render_header_bar(
    "Conference Room Booking App",
    "assets/logo.png",
    logo_height=50,
    bg_color="#CBD9F8",
)


# region Chapter 5: Load the MySQL Database
init_db()


@st.cache_data(ttl=1 * 24 * 60 * 60)  # 1 day
def load_bookings(page_id: str = "conference"):
    """Load bookings without timezone conversion for caching compatibility"""
    _ = page_id  # intentionally keep param to make cache key unique
    df = get_bookings()

    # Remove timezone info before caching to avoid pickle issues
    if "created_at" in df.columns and not df["created_at"].isna().all():
        try:
            # Convert to timezone-naive UTC datetime
            df["created_at"] = pd.to_datetime(
                df["created_at"], utc=True
            ).dt.tz_localize(None)
        except Exception as e:
            print(f"Error removing timezone from created_at: {e}")

    return df


def prepare_bookings_display(df):
    """Add IST timezone conversion for display after loading from cache"""
    if df.empty:
        return df

    df = df.copy()

    # Now add IST conversion for display
    if "created_at" in df.columns and not df["created_at"].isna().all():
        try:
            # Treat cached datetime as UTC and convert to IST
            df["created_at_ist"] = (
                pd.to_datetime(df["created_at"])
                .dt.tz_localize("UTC")
                .dt.tz_convert("Asia/Kolkata")
                .dt.tz_localize(None)
                .dt.strftime("%Y-%m-%d %H:%M:%S")
            )
        except Exception as e:
            print(f"Error converting to IST: {e}")
            df["created_at_ist"] = df["created_at"]

    return df


with st.spinner("Loading bookings…"):
    df = load_bookings("conference")
    df = prepare_bookings_display(df)

# endregion

# region Chapter 6: Bookings Timeline, Dataframe + Booking Form (1+1 Columns)
left_col, right_col = st.columns([2, 1], gap="small")

with left_col:

    # Left Column: Bookings Timeline
    with st.container(border=True):
        st.write("📊 Current Bookings Timeline (Date & Time)")

        df_json = df.to_json(date_format="iso", orient="split")
        nrows = len(df)
        max_created = None
        if "created_at" in df.columns and not df["created_at"].isna().all():
            # using string because datetimes are not stable cache keys otherwise
            max_created = str(df["created_at"].max())

        fig, info = build_timeline_figure_cached(nrows, max_created, df_json)

        if fig is not None:
            # creates a fresh display copy so cached figure object is left intact
            fig_display = go.Figure(fig)

            # Adds a live "Today" marker
            now_dt = datetime.now()
            today = now_dt.date()
            fig_display.add_vline(
                x=today,
                line_width=1,
                line_dash=cfg.LINE_STYLE,
                line_color=cfg.LINE_COLOR,
            )
            fig_display.add_annotation(
                x=today,
                y=1,
                xref="x",
                yref="paper",
                text="Today",
                showarrow=False,
                font=dict(color=cfg.LINE_COLOR),
                yanchor="bottom",
            )

            st.plotly_chart(fig_display, use_container_width=True)
        else:
            reason = (info or {}).get("reason")
            if reason == "empty_df":
                st.info("No bookings in the database yet.")
            elif reason == "all_rows_unparsable":
                st.error(
                    f"All rows failed to parse times/dates (bad rows: {info.get('bad_count')})."
                )
            elif reason == "out_of_window":
                st.warning(
                    f"No bookings in the current (30-days) window."
                    # f"[{info.get('window_start')} → {info.get('window_end')}]. "
                )
                st.warning(
                    f"Data range: [{info.get('min_date')}] to [{info.get('max_date')}]."
                )
            else:
                st.info("No data to show.")

    # Left Column: Table Dataframe
    st.subheader("📌 All Existing Bookings")

    if not df.empty:
        st.dataframe(
            df[
                [
                    "booking_date",
                    "start_time",
                    "end_time",
                    "conference_type",
                    "person_name",
                    "company_name",
                    "affiliation",
                    "email",
                    "booking_description",
                    "created_at_ist",
                ]
            ]
            .sort_values(by=["booking_date", "start_time"])
            .reset_index(drop=True),
            height=cfg.TABLE_HEIGHT,
        )
    else:
        st.info("No bookings to show in the table yet.")

    # Tips + Lottie (1+1 Internal Sections)
    left_sec, right_sec = st.columns([2, 1], gap="small", vertical_alignment="top")

    with left_sec:

        # Tips
        st.info(
            f"💡 **TIP:**"
            f"  \n"
            f"  \n• Provide **valid email** to get booking confirmation."
            f"  \n• Hover a **:rainbow[coloured]** bar in the graph to see the booking details."
            f"  \n• Use the table's **search tool** to search for a booking instance."
            f"  \n• Best viewed on a **wide screen**. :computer:"
            f"  \n• Found a **bug?** 🪲 Report to: sumiet_t@quantech.org.in"
        )

    with right_sec:

        # Lottie Animation
        with st.container(border=False):
            lottie_animation = load_lottiefile("assets/conference_lottie.json")
            if lottie_animation:
                st_lottie(lottie_animation, speed=1, height=220, key="conference")

# Right Column: Booking Form
with right_col:

    booking_form()
    if "_flash" in st.session_state:
        st.success(st.session_state.pop("_flash"))


# endregion

# region Chapter 7: Clear Cache

if st.button("🔄 Clear Cache"):
    st.cache_data.clear()
    st.cache_resource.clear()
    st.success("All caches cleared. Refreshing the page...")
    time.sleep(3)
    st.rerun()

# endregion


# region Chapter 8: Daily Quote

st.divider()
quote_data = get_random_quote()
if quote_data:
    st.markdown(
        f"### 💭 **Quote of the Day!**  \n"
        f"*\"{quote_data['content']}\"*  — **{quote_data['author']}**"
    )

# endregion
