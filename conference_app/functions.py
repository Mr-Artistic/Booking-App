# region Chapter 1: Imports
import streamlit as st
import pandas as pd
import base64
import plotly.graph_objects as go
import tempfile, os
import re
import smtplib
import datetime as _dt
import json
import requests

from io import StringIO
from datetime import datetime, timedelta, date, time as dtime
from pathlib import Path
from email.mime.text import MIMEText
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Custom Modules
from conference_app import config as cfg

# endregion


# region Chapter 2: Initialise MySQL connection
@st.cache_resource
def get_engine():
    user = st.secrets.get("mysql_user")
    password = st.secrets.get("mysql_password")
    host = st.secrets.get("mysql_host")
    port = st.secrets.get("mysql_port", "3306")
    dbname = st.secrets.get("mysql_db")
    if not (user and password and host and dbname):
        raise RuntimeError(
            "Missing MySQL secrets: mysql_user/mysql_password/mysql_host/mysql_db"
        )

    ca_b64 = st.secrets.get("mysql_ca_b64")
    if ca_b64:
        tmp = tempfile.gettempdir()
        ca_path = os.path.join(tmp, "aiven_mysql_ca.pem")
        with open(ca_path, "wb") as f:
            f.write(base64.b64decode(ca_b64))
        ssl_args = {"ssl": {"ca": ca_path}}
    else:
        ssl_args = {}

    db_url = f"mysql+pymysql://{user}:{password}@{host}:{port}/{dbname}?charset=utf8mb4"
    return create_engine(db_url, connect_args=ssl_args, pool_pre_ping=True)


# endregion


# region  Chapter 3: Initialise MySQL database
def init_db():
    engine = get_engine()
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS conference_bookings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        booking_date DATE,
        start_time TIME,
        end_time TIME,
        conference_type VARCHAR(100),
        person_name VARCHAR(100),
        company_name VARCHAR(100),
        affiliation VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    idx_sql = "CREATE INDEX idx_booking_date_conference_type ON conference_bookings (booking_date, conference_type);"
    try:
        with engine.begin() as conn:
            conn.execute(text(create_table_sql))
            # create index if missing
            schema = st.secrets.get("mysql_db") or engine.url.database
            idx_check = text(
                "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=:schema AND table_name='conference_bookings' AND index_name='idx_booking_date_conference_type'"
            )
            cnt = int(conn.execute(idx_check, {"schema": schema}).scalar() or 0)
            if cnt == 0:
                conn.execute(text(idx_sql))
    except SQLAlchemyError as e:
        print("init_db error:", e)
        raise


# endregion


# region Chapter 4: Add Booking function
def add_booking(
    booking_date: date,
    start_time: dtime,
    end_time: dtime,
    conference_type: str,
    person_name: str,
    company_name: str,
    affiliation: str,
    email: str,
    booking_description: str = "",
):
    """
    Inserts python date/time objects directly - SQLAlchemy will bind them to DATE/TIME.
    """
    engine = get_engine()
    insert_sql = text(
        """
        INSERT INTO conference_bookings
        (booking_date, start_time, end_time, conference_type, person_name, company_name, affiliation, email, booking_description)
        VALUES (:booking_date, :start_time, :end_time, :conference_type, :person_name, :company_name, :affiliation, :email, :booking_description)
    """
    )
    params = {
        "booking_date": booking_date,
        "start_time": start_time,
        "end_time": end_time,
        "conference_type": conference_type,
        "person_name": person_name,
        "company_name": company_name,
        "affiliation": affiliation,
        "email": email,
        "booking_description": booking_description,
    }
    try:
        with engine.begin() as conn:
            conn.execute(insert_sql, params)
    except SQLAlchemyError as e:
        print("add_booking error:", e)
        raise


# endregion


# region Chapter 5: Get Bookings function
def get_bookings() -> pd.DataFrame:
    """
    Returns a dataframe of bookings. Assumes rows were inserted from the controlled streamlit form (date/time objects).
    Note: created_at timezone conversion is handled in the app layer for caching compatibility.
    """
    engine = get_engine()
    sql = """
        SELECT id, booking_date, start_time, end_time, conference_type,
               person_name, company_name, affiliation, email, booking_description, created_at
        FROM conference_bookings
        ORDER BY booking_date ASC, start_time ASC, id ASC
    """
    try:
        df = pd.read_sql_query(sql, con=engine)
    except Exception as e:
        print("get_bookings() sql error:", e)
        return pd.DataFrame(
            columns=[
                "id",
                "booking_date",
                "start_time",
                "end_time",
                "conference_type",
                "person_name",
                "company_name",
                "affiliation",
                "email",
                "booking_description",
                "created_at",
            ]
        )

    expected_cols = [
        "id",
        "booking_date",
        "start_time",
        "end_time",
        "conference_type",
        "person_name",
        "company_name",
        "affiliation",
        "email",
        "booking_description",
        "created_at",
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = None

    # Converts start_time/end_time to strings 'HH:MM:SS' for consistent downstream use (plotting & tooltip)
    def to_hhmmss(v):
        # use module alias _dt (imported at top) to access timedelta safely
        if pd.isna(v):
            return None

        # pandas Timedelta or datetime.timedelta (use _dt.timedelta)
        if isinstance(v, (pd.Timedelta, _dt.timedelta)):
            total_seconds = int(pd.Timedelta(v).total_seconds())
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        # datetime.time or datetime.datetime
        if hasattr(v, "strftime") and not isinstance(v, str):
            return v.strftime("%H:%M:%S")

        s = str(v).strip()
        s = s.replace(".", ":")
        # If format like '0 days HH:MM:SS', takes last token
        if "days" in s:
            parts = s.split()
            s = parts[-1]

        parts = s.split(":")
        if len(parts) == 2:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"

        # Fallback: tries parsing with pandas datetime
        try:
            t = pd.to_datetime(s, errors="coerce")
            if not pd.isna(t):
                return t.strftime("%H:%M:%S")
        except Exception:
            pass

        return s

    df["start_time"] = df["start_time"].apply(to_hhmmss)
    df["end_time"] = df["end_time"].apply(to_hhmmss)
    return df


# endregion


# region Chapter 6: Check Conflict function
def check_conflict(booking_date, start_time, end_time, conference_type):
    """
    Combines date + time to datetimes and check overlaps for same date & conference_type.
    Returns (bool_conflict, details_or_None)
    """
    engine = get_engine()
    try:
        new_start = datetime.combine(booking_date, start_time)
        new_end = datetime.combine(booking_date, end_time)
    except Exception:
        return False, None
    if new_end <= new_start:
        return True, "End time must be after start time."

    sql = text(
        """
        SELECT booking_date, start_time, end_time, conference_type, person_name, company_name
        FROM conference_bookings
        WHERE booking_date = :bdate AND conference_type = :ctype
    """
    )
    try:
        with engine.connect() as conn:
            rows = (
                conn.execute(sql, {"bdate": booking_date, "ctype": conference_type})
                .mappings()
                .all()
            )
    except Exception as e:
        print("check_conflict DB error:", e)
        return False, None

    for r in rows:
        db_start = r.get("start_time")
        db_end = r.get("end_time")

        try:
            # Handle pandas Timedelta / datetime.timedelta
            if isinstance(db_start, (pd.Timedelta, _dt.timedelta)):
                total = int(pd.Timedelta(db_start).total_seconds())
                h = total // 3600
                m = (total % 3600) // 60
                s = total % 60
                db_start_t = _dt.time(h % 24, m, s)
            elif hasattr(db_start, "strftime") and not isinstance(db_start, str):
                # already a time or datetime
                db_start_t = (
                    db_start
                    if isinstance(db_start, _dt.time)
                    else getattr(db_start, "time", lambda: db_start)()
                )
            else:
                s = str(db_start)
                if "days" in s:
                    s = s.split()[-1]
                db_start_t = _dt.strptime(s, "%H:%M:%S").time()

            # same for end
            if isinstance(db_end, (pd.Timedelta, _dt.timedelta)):
                total = int(pd.Timedelta(db_end).total_seconds())
                h = total // 3600
                m = (total % 3600) // 60
                s = total % 60
                db_end_t = _dt.time(h % 24, m, s)
            elif hasattr(db_end, "strftime") and not isinstance(db_end, str):
                db_end_t = (
                    db_end
                    if isinstance(db_end, _dt.time)
                    else getattr(db_end, "time", lambda: db_end)()
                )
            else:
                s = str(db_end)
                if "days" in s:
                    s = s.split()[-1]
                db_end_t = _dt.strptime(s, "%H:%M:%S").time()

            exist_start = datetime.combine(r.get("booking_date"), db_start_t)
            exist_end = datetime.combine(r.get("booking_date"), db_end_t)
        except Exception:
            # couldn't parse this DB row — skip it
            continue

        if new_start < exist_end and new_end > exist_start:
            details = (
                f"Existing booking in [{r.get('conference_type','')}] "
                f"by [{r.get('person_name','')} ({r.get('company_name','')})] "
                f"from {db_start} to {db_end}."
            )
            return True, details
    return False, None


# endregion


# region Chapter 7: Fractional Hours functions
def to_fractional_hours(val):
    """Convert time value (string or datetime.time) into fractional hours (float)."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None

    # pandas Timedelta or datetime.timedelta
    if isinstance(val, (pd.Timedelta, _dt.timedelta)):
        total_seconds = int(pd.Timedelta(val).total_seconds())
        return total_seconds / 3600.0

    # datetime.time or datetime.datetime (has hour attribute)
    if hasattr(val, "hour") and not isinstance(val, str):
        try:
            h = int(val.hour)
            m = int(getattr(val, "minute", 0))
            s = int(getattr(val, "second", 0))
            return h + m / 60.0 + s / 3600.0
        except Exception:
            pass

    try:
        s = str(val)
        # handle '0 days HH:MM:SS'
        if "days" in s:
            s = s.split()[-1]
        t = pd.to_datetime(s, format="%H:%M:%S", errors="coerce")
        if pd.isna(t):
            t = pd.to_datetime(s, format="%H:%M", errors="coerce")
        if pd.isna(t):
            t = pd.to_datetime(s, errors="coerce")
            if pd.isna(t):
                return None
        return float(t.hour + t.minute / 60.0 + t.second / 3600.0)
    except Exception:
        return None


# endregion


# region Chapter 8: Red Alert function
def st_red_alert(msg: str):
    """A format for the red alert message."""
    st.markdown(
        f"""
        <div style="
            padding: 10px 16px;
            margin: 10px 0;
            border-radius: 6px;
            background-color: #ffddd9;   /* red-500 */
            color: black;
            font-weight: 400;
        ">
            {msg}
        </div>
        """,
        unsafe_allow_html=True,
    )


# endregion


# region Chapter 9: Booking Form function
def booking_form():
    st.subheader(":red[**👉 Book Conference Room**]")
    with st.form("booking_form"):
        booking_date = st.date_input("Booking Date (YYYY-MM-DD)*")
        start_time = st.time_input("Start Time (24hrs Format)*")
        end_time = st.time_input("End Time (24hrs Format)*")
        conference_type = st.selectbox(
            "Conference Type*", ["I-HUB 1st floor", "I-HUB 5th floor", "Mendeleev"]
        )
        person_name = st.text_input("Person Name*")
        company_name = st.text_input("Company*")
        affiliation = st.selectbox("Affiliation*", ["I-HUB", "AIC"])
        email = st.text_input("Email*")
        booking_description = st.text_input(
            "Booking Description (optional)",
            max_chars=30,
            help="Optional field to describe your booking (max 30 characters)",
        )

        submitted = st.form_submit_button("Submit Booking")

        if submitted:
            missing = []
            if not booking_date:
                missing.append("Booking Date")
            if not start_time:
                missing.append("Start Time")
            if not end_time:
                missing.append("End Time")
            if not conference_type:
                missing.append("Conference Type")
            if not person_name.strip():
                missing.append("Person Name")
            if not company_name.strip():
                missing.append("Company")
            if not affiliation.strip():
                missing.append("Affiliation")
            if not email.strip():
                missing.append("Email")

            if missing:
                st_red_alert(f"Please fill all required fields: {', '.join(missing)}.")
            else:
                # Validation for future booking
                now = datetime.now()
                requested_start = datetime.combine(booking_date, start_time)
                if requested_start < now:
                    st_red_alert("Booking date/time cannot be a history.")
                    return

                if end_time <= start_time:
                    st_red_alert("End Time must be after Start Time.")
                    return

                if len(email) > 100:
                    st_red_alert("Email is too long (max 100 characters).")
                    return

                if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
                    st_red_alert("Please enter a valid email address.")
                    return

                if len(person_name) > 100:
                    st_red_alert("Person Name is too long (max 100 characters).")
                    return

                if len(company_name) > 100:
                    st_red_alert("Company Name is too long (max 100 characters).")
                    return

                # Clean booking_description: strip multiple whitespaces
                cleaned_description = " ".join(booking_description.split()).strip()

                conflict, details = check_conflict(
                    booking_date, start_time, end_time, conference_type
                )
                if conflict:
                    st_red_alert(f"❌ Time conflict! {details}")
                else:
                    add_booking(
                        booking_date,
                        start_time,
                        end_time,
                        conference_type,
                        person_name,
                        company_name,
                        affiliation,
                        email,
                        cleaned_description,
                    )

                    subject = f"Booking confirmation for {conference_type} Conference Room on {booking_date}"
                    body = (
                        f"Hello {person_name},\n\n"
                        f"Your booking for {conference_type} conference room has been confirmed.\n\n"
                        f"Date: {booking_date} (YYYY/MM/DD)\n"
                        f"From: {start_time}\n"
                        f"To: {end_time}\n"
                        f"Company: {company_name}\n"
                        f"Affiliation: {affiliation}\n"
                        f"Description: {cleaned_description if cleaned_description else 'N/A'}\n\n"
                        ""
                        "Thank you!"
                        f"\n\nPrimary Contact: {cfg.PRIMARY_CONTACT}\n"
                        f"Secondary Contact: {cfg.SECONDARY_CONTACT}\n"
                    )

                    with st.spinner("Sending confirmation email..."):
                        # uses send_email unction defined at last
                        email_ok = send_email(email, subject, body)

                    if not email_ok:
                        st.warning(
                            "Booking saved, but confirmation email could not be sent."
                        )
                    else:
                        st.success("Confirmation email sent.")
                    st.session_state["_flash"] = "✅ Booking successfull, check email!"
                    st.cache_data.clear()
                    st.rerun()


# endregion


# region Chapter 10: Header Bar function
def render_header_bar(
    title: str, logo_path: str, logo_height: int = 50, bg_color: str = "#1E3A8A"
):
    p = Path(logo_path)
    logo_html = ""
    if p.exists():
        b64 = base64.b64encode(p.read_bytes()).decode()
        logo_html = f"<img src='data:image/png;base64,{b64}' height='{logo_height}'>"

    st.markdown(
        f"""
        <div style="
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: {bg_color};
            padding: 6px 8px;
            border-radius: 8px;
            margin: -40px 0 10px 0;
            margin-bottom: 10px;
        ">
            <h1 style="margin: 0; color: black; font-size: 28px;">{title}</h1>
            {logo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# endregion


# region Chapter 11: Plotting function
def build_vertical_day_time_timeline(df: pd.DataFrame, default_color="#E53935"):
    """
    Timeline builder. Expects get_bookings() style dataframe where start_time/end_time are strings 'HH:MM:SS'.

    Features:
    - 4-week window from cfg.TIMELINE_START to cfg.TIMELINE_END (datetime at midnight)
    - one tick per day (dtick = 24h) aligned to start_window (tick0)
    - grouped bars (# offsetgroup + barmode='group') to avoid overlap
    """
    if df is None or df.empty:
        return None, {"reason": "empty_df"}

    required = {
        "booking_date",
        "start_time",
        "end_time",
        "conference_type",
        "person_name",
        "company_name",
        "affiliation",
        "email",
    }
    if not required.issubset(set(df.columns)):
        return None, {"reason": "missing_columns"}

    df = df.copy()

    # Convert booking_date to normalized datetime (midnight) and compute start/end in fractional hours
    df["DateOnly"] = pd.to_datetime(df["booking_date"], errors="coerce").dt.normalize()
    df["StartH"] = df["start_time"].apply(to_fractional_hours)
    df["EndH"] = df["end_time"].apply(to_fractional_hours)

    mask = df["DateOnly"].notna() & df["StartH"].notna() & df["EndH"].notna()
    df = df[mask]
    if df.empty:
        return None, {"reason": "all_rows_unparsable"}

    df["DurH_raw"] = df["EndH"] - df["StartH"]
    invalid_count = int((df["DurH_raw"] <= 0).sum())
    df["DurH"] = df["DurH_raw"].where(df["DurH_raw"] > 0, 0.25)

    # Use config window (expected to be datetime objects at midnight)
    start_window = pd.to_datetime(cfg.get_timeline_start())
    end_window = pd.to_datetime(cfg.get_timeline_end())

    # Ensure start_window < end_window
    if pd.isna(start_window) or pd.isna(end_window) or start_window >= end_window:
        return None, {
            "reason": "invalid_window",
            "start": str(start_window),
            "end": str(end_window),
        }

    # Filter to window (include start, exclude end)
    dfw = df[(df["DateOnly"] >= start_window) & (df["DateOnly"] < end_window)]
    if dfw.empty:
        return None, {
            "reason": "out_of_window",
            "window_start": start_window.strftime("%Y-%m-%d"),
            "window_end": end_window.strftime("%Y-%m-%d"),
            "min_date": df["DateOnly"].min(),
            "max_date": df["DateOnly"].max(),
        }

    fig = go.Figure()

    # Bar width: small fraction of a day (ms)
    ms_per_day = 24 * 60 * 60 * 1000
    bar_width_ms = int(ms_per_day * 0.18)

    color_map = {
        "I-HUB 1st floor": "#1E88E5",
        "I-HUB 5th floor": "#43A047",
        "Mendeleev": "#FB8C00",
    }
    seen_ctypes = set()

    for _, row in dfw.iterrows():
        ctype = str(row.get("conference_type") or "")
        color = color_map.get(ctype, default_color)

        show_legend = False
        name = ""

        if ctype not in seen_ctypes:
            show_legend = True
            name = ctype
            seen_ctypes.add(ctype)

        # Ensure hover shows only time strings (HH:MM:SS) — avoids Plotly coercing to full datetimes (which add today's date)
        def _fmt_time_for_hover(v):
            if pd.isna(v) or v is None:
                return ""
            s = str(v).strip()
            # handle "0 days HH:MM:SS" style
            if "days" in s:
                s = s.split()[-1].strip()
            # if already in H:M or H:M:S form produce H:M:S
            try:
                t = pd.to_datetime(s, format="%H:%M:%S", errors="coerce")
                if pd.isna(t):
                    t = pd.to_datetime(s, format="%H:%M", errors="coerce")
                if pd.isna(t):
                    t = pd.to_datetime(s, errors="coerce")
                if not pd.isna(t):
                    return t.strftime("%H:%M:%S")
            except Exception:
                pass
            return s

        start_disp = _fmt_time_for_hover(row.get("start_time"))
        end_disp = _fmt_time_for_hover(row.get("end_time"))

        # Get booking description
        desc = row.get("booking_description", "")
        if pd.isna(desc) or not desc:
            desc = "N/A"

        fig.add_bar(
            x=[row["DateOnly"]],
            y=[row["DurH"]],
            base=[row["StartH"]],
            marker_color=color,
            width=[bar_width_ms],
            name=name,
            offsetgroup=ctype,
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[1]})<br>Date: %{x|%Y-%m-%d}<br>"
                "From: %{customdata[2]}<br>To: %{customdata[3]}<br>"
                "Description: %{customdata[4]}<extra></extra>"
            ),
            customdata=[
                [
                    row.get("person_name"),
                    row.get("company_name"),
                    start_disp,
                    end_disp,
                    desc,
                ]
            ],
            showlegend=show_legend,
        )

    # Y axis simple ticks (every 2 hours)
    tick_vals = list(range(0, 25, 2))
    tick_text = [f"{h:02d}:00" for h in tick_vals]

    # Force daily ticks: dtick in milliseconds = 24 * 60 * 60 * 1000
    one_day_ms = 24 * 60 * 60 * 1000

    # Convert start and end window to string format for x-axis range
    start_window_str = start_window.strftime("%Y-%m-%d")
    end_window_str = end_window.strftime("%Y-%m-%d")

    # set tick0 to string date format
    tick0_str = start_window.strftime("%Y-%m-%d")

    fig.update_layout(
        height=getattr(cfg, "GRAPH_HEIGHT", 600),
        bargap=0.15,
        barmode="group",
        xaxis=dict(
            type="date",
            range=[start_window_str, end_window_str],  # Use string dates
            fixedrange=True,
            title="Date",
            tickangle=-90,
            tickfont=dict(size=10),
            dtick=one_day_ms,  # one tick per day
            tick0=tick0_str,  # Use string format
            tickformat="%d %b",  # day + month format
            automargin=True,
        ),
        yaxis=dict(
            range=[0, 24],
            tickvals=tick_vals,
            ticktext=tick_text,
            fixedrange=True,
            title="Time",
            automargin=True,
        ),
        margin=dict(l=40, r=20, t=40, b=40),
        legend=dict(
            title="Conference Type",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )

    return fig, {
        "reason": "ok",
        "rows_plotted": int(len(dfw)),
        "invalid_durations": invalid_count,
    }


# endregion

# region Chapter 12: Cached wrapper to build the timeline figure


@st.cache_data(ttl=1 * 24 * 60 * 60)  # 1 day
def build_timeline_figure_cached(n_rows: int, max_created_at: str, df_json: str):
    """
    - n_rows and max_created_at are cheap cache keys (fingerprint).
    - df_json: small JSON serialization of the dataframe (orient='split' recommended).
    """
    try:
        # Recreate DataFrame (orient='split')
        df = pd.read_json(StringIO(df_json), orient="split")
    except Exception as e:
        # If reconstruction fails, pass None so plotting function can handle it
        print("build_timeline_figure_cached: failed to read df_json:", e)
        return None, {"reason": "invalid_df_json"}

    # Calls the main plotting function
    return build_vertical_day_time_timeline(df)


# endregion


# region Chapter 13: Send Email function
def send_email(to_email, subject, body):
    """Sends an email using SMTP settings from config."""

    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = cfg.SMTP_USER
    msg["To"] = to_email

    cc_list = cfg.CC_EMAILS
    msg["Cc"] = ", ".join(cc_list)

    recipients = [to_email] + cc_list

    try:
        if cfg.SMTP_PORT == 465:
            # Uses SSL for port 465
            with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
                server.login(cfg.SMTP_USER, cfg.SMTP_PASS)
                server.sendmail(cfg.SMTP_USER, recipients, msg.as_string())
        else:
            # Default: connects plain + upgrade to TLS
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT) as server:
                server.starttls()
                server.login(cfg.SMTP_USER, cfg.SMTP_PASS)
                server.sendmail(cfg.SMTP_USER, recipients, msg.as_string())
        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False


# endregion

# region Chapter 14: Lottie Animation function


@st.cache_data(ttl=1 * 24 * 60 * 60)  # 1 day
def load_lottiefile(filepath: str, page_id: str = "conference"):
    _ = page_id  # intentionally keep param to make cache key unique
    try:
        with open(filepath, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception as e:
        st.error(f"Error loading local Lottie file: {e}")
        return None


# endregion


# region Chapter 15: Random Quotes function


@st.cache_data(ttl=24 * 60 * 60)  # Cache for 1 day
def get_random_quote():
    """Fetch a random quote from Quotable API"""
    try:
        response = requests.get(
            "https://api.quotable.io/random?tags=technology",
            timeout=5,
            verify=True,  # Try with SSL verification first
        )
        if response.status_code == 200:
            data = response.json()
            return {
                "content": data.get("content", ""),
                "author": data.get("author", "Unknown"),
            }
        return None

    except requests.exceptions.SSLError:
        # Fallback: retry without SSL verification if certificate fails
        try:
            response = requests.get(
                "https://api.quotable.io/random?tags=technology",
                timeout=5,
                verify=False,  # Disable SSL verification as fallback
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "content": data.get("content", ""),
                    "author": data.get("author", "Unknown"),
                }
        except Exception:
            pass
        return None
    except Exception as e:
        # Silently fail - don't show warning to users
        print(f"Quote API error: {e}")
        return None


# endregion
