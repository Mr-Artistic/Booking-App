# region Chapter 1: Imports

import streamlit as st
import yaml
from yaml.loader import SafeLoader
from PIL import Image
import streamlit_authenticator as stauth
import time
import pandas as pd
from streamlit_lottie import st_lottie
import plotly.graph_objects as go
from datetime import datetime


# Custom Modules
from resource_app import config as cfg

from resource_app.functions import (
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
        "About": "App Version 1.0  |  Developed by: Sumiet Talekar",
    },
)

# endregion


# region Chapter 3: User Authentication

UserAuth = True

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
    "Resource Booking App",
    "assets/logo.png",
    logo_height=50,
    bg_color="#CBD9F8",
)


# region Chapter 5: Load the MySQL Database
init_db()


@st.cache_data(ttl=7 * 24 * 60 * 60)  # 1 week
def load_bookings(page_id: str = "resource"):
    _ = page_id  # intentionally keep param to make cache key unique
    return get_bookings()


with st.spinner("Loading bookings…"):
    df = load_bookings("resource")

# endregion

# region Chapter 6: Timeline with filter, Dataframe + Booking Form (1+1 Columns)

left_col, right_col = st.columns([2, 1], gap="small")
with left_col:

    # Left Column: Bookings Timeline
    with st.container(border=True):
        st.write("📊 Current Bookings Timeline (Date & Time)")

        # --- Multiselect Filter for User ---
        # Fallback to config.resource_list if df empty or column missing
        # Always use canonical resource list from config.resource_list so user-created combinations don't appear here.
        if df is None or df.empty or "resource_type" not in df.columns:
            available_types = (
                list(cfg.resource_list) if getattr(cfg, "resource_list", None) else []
            )
        else:
            available_types = list(cfg.resource_list)

        # default = first item if available
        selected_types = st.multiselect(
            "Select resource(s) to plot data:",
            options=available_types,
            default=[available_types[0]] if available_types else [],
        )

        # Apply filter for plotting & table.
        # Include ANY of the selected single resource even if DB stores rows as comma-joined strings.
        if selected_types and "resource_type" in (df.columns if df is not None else []):
            # Normalize selected types to lower-case trimmed tokens for comparison
            sel_set = {str(x).strip().lower() for x in selected_types if str(x).strip()}

            def row_matches_any(selected_set, row_val):
                if row_val is None:
                    return False
                # split DB string on commas, strip and lowercase
                tokens = [
                    t.strip().lower() for t in str(row_val).split(",") if t.strip()
                ]
                if not tokens:
                    return False
                return not selected_set.isdisjoint(tokens)

            # Use .apply to keep rows matching any selected resource
            mask = df["resource_type"].apply(lambda v: row_matches_any(sel_set, v))
            df = df[mask].copy()
        else:
            # Nothing selected OR column missing -> an empty frame to downstream logic
            df = (
                df.iloc[0:0].copy()
                if (df is not None and not df.empty)
                else (pd.DataFrame() if df is None else df.copy())
            )
        # --- End Filter ---

        # Serialize filtered df and build cached figure
        df_json = df.to_json(date_format="iso", orient="split")
        nrows = len(df)
        max_created = None
        if "created_at" in df.columns and not df["created_at"].isna().all():
            max_created = str(df["created_at"].max())

        # fig, info = build_vertical_day_time_timeline(df) --> using cached version below
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
                    f"No bookings in the current (10-days) window."
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
                    "resource_type",
                    "person_name",
                    "company_name",
                    "affiliation",
                    "email",
                    "created_at_ist",
                    "payment_status",
                    "payment_id",
                    "payment_date",
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
            f"  \n• Provide **valid email** to get booking confirmation & payment link."
            f"  \n• Please share **payment reference** to enable us process booking."
            f"  \n• Bookings are to be done at least **18 hours** in advance."
            f"  \n• Resources are to be booked only between **09:00 and 18:00**."
            f"  \n• Hover a **:rainbow[coloured]** bar in the graph to see the booking details."
            f"  \n• Use the table's **search tool** to search for a booking instance."
            f"  \n• Best viewed on a **wide screen**. :computer:"
            f"  \n• Found a **bug?** 🪲 Report to: sumiet_t@quantech.org.in"
            f"  \n• Have a **feedback?** ✍️ Write to: niranjan_d@quantech.org.in"
        )

    with right_sec:

        # Lottie Animation
        with st.container(border=False):
            lottie_animation = load_lottiefile("assets/resource_lottie.json")
            if lottie_animation:
                st_lottie(lottie_animation, speed=1, height=300, key="resource")

# Right Column: Booking Form
with right_col:

    booking_form()
    if "_flash" in st.session_state:
        flash_message = st.session_state.pop("_flash")

        st.markdown(
            f'<div class="stAlert stSuccess" style="background-color: #f0fff0; color: #008000; padding: 10px; border-radius: 5px; border-left: 5px solid #008000;">{flash_message}</div>',
            unsafe_allow_html=True,
        )

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
