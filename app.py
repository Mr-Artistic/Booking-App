# region Chapter 1: Imports

import streamlit as st
import config as cfg
from functions import (
    init_db,
    get_bookings,
    booking_form,
    render_header_bar,
    build_vertical_day_time_timeline,
)

# endregion

# region Chapter 2: Page Layout
st.set_page_config(page_title="Booking App", layout="wide")
if "_flash" in st.session_state:
    st.success(st.session_state.pop("_flash"))

render_header_bar(
    "Conference Room Booking Dashboard",
    "assets/logo.png",
    logo_height=50,
    bg_color="#CBD9F8",
)

# endregion

# region Chapter 3: Load the MySQL Database
init_db()


@st.cache_data(ttl=30)
def load_bookings():
    return get_bookings()


with st.spinner("Loading bookings…"):
    df = load_bookings()

# endregion

# region Chapter 4: App Layout (2 Columns)
left_col, right_col = st.columns([2, 1], gap="small")
with left_col:

    # Bordered container for the graph
    with st.container(border=True):
        st.write("📊 Current Bookings Timeline (Day vs Time)")
        fig, info = build_vertical_day_time_timeline(df)

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

    st.write(
        f"💡 **Tip:**"
        f"  \n"
        f"  \n• Best viewed on a **computer**. :computer:"
        f"  \n• Hover the **:rainbow[coloured]** bars to see a booking instance."
        f"  \n• Use the table's column **headers** to sort/filter bookings."
        f"  \n• Found a **bug?** 🪲 Report to: sumiet_t@quantech.org.in"
    )

# Right Column: Booking Form
with right_col:
    booking_form()

# endregion
