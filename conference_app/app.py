# region Chapter 1: Imports

import streamlit as st
import yaml
from yaml.loader import SafeLoader
from PIL import Image
import streamlit_authenticator as stauth
import time

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


@st.cache_data(ttl=7 * 24 * 60 * 60)  # 1 week
def load_bookings():
    return get_bookings()


with st.spinner("Loading bookings…"):
    df = load_bookings()

# endregion

# region Chapter 6: App Layout (2 Columns)
left_col, right_col = st.columns([2, 1], gap="small")
with left_col:

    # Bordered container for the graph
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
            st.plotly_chart(fig, use_container_width=True)
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
                    f"No bookings in the 3-month window "
                    f"[{info.get('window_start')} → {info.get('window_end')}]. "
                    f"Data spans {info.get('min_date')} → {info.get('max_date')}."
                )
            else:
                st.info("No data to show.")

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
                    "created_at_ist",
                ]
            ]
            .sort_values(by=["booking_date", "start_time"])
            .reset_index(drop=True),
            height=cfg.TABLE_HEIGHT,
        )
    else:
        st.info("No bookings to show in the table yet.")

    container = st.container(border=False)
    with container:
        st.info(
            f"💡 **TIP:**"
            f"  \n"
            f"  \n• Provide a **valid email** to receive booking confirmation."
            f"  \n• Hover a **:rainbow[coloured]** bar in the graph to see the booking details."
            f"  \n• Use the table's **search tool** to search for a booking instance."
            f"  \n• Best viewed on a **computer**. :computer:"
            f"  \n• Found a **bug?** 🪲 Report to: sumiet_t@quantech.org.in"
        )

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
