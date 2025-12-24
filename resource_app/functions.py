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
from resource_app import config as cfg
from resource_app.config import (
    resource_list,
    resource_color_map,
    resource_price_list,
    payment_link,
)

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
    CREATE TABLE IF NOT EXISTS resource_bookings (
        id INT AUTO_INCREMENT PRIMARY KEY,
        booking_date DATE,
        start_time TIME,
        end_time TIME,
        resource_type VARCHAR(1000),
        person_name VARCHAR(100),
        company_name VARCHAR(100),
        affiliation VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_status VARCHAR(100),
        payment_id VARCHAR(100),
        payment_date DATE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    idx_sql = "CREATE INDEX idx_booking_date ON resource_bookings (booking_date);"
    try:
        with engine.begin() as conn:
            conn.execute(text(create_table_sql))
            # create index if missing
            schema = st.secrets.get("mysql_db") or engine.url.database
            idx_check = text(
                "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema=:schema AND table_name='resource_bookings' AND index_name='idx_booking_date'"
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
    resource_type: str,
    person_name: str,
    company_name: str,
    affiliation: str,
    email: str,
):
    """
    Inserts python date/time objects directly - SQLAlchemy will bind them to DATE/TIME.
    """
    engine = get_engine()
    insert_sql = text(
        """
        INSERT INTO resource_bookings
        (booking_date, start_time, end_time, resource_type, person_name, company_name, affiliation, email)
        VALUES (:booking_date, :start_time, :end_time, :resource_type, :person_name, :company_name, :affiliation, :email)
    """
    )
    params = {
        "booking_date": booking_date,
        "start_time": start_time,
        "end_time": end_time,
        "resource_type": resource_type,
        "person_name": person_name,
        "company_name": company_name,
        "affiliation": affiliation,
        "email": email,
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
    """
    engine = get_engine()
    sql = """
        SELECT id, booking_date, start_time, end_time, resource_type,
               person_name, company_name, affiliation, email, created_at, payment_status, payment_id, payment_date
        FROM resource_bookings
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
                "resource_type",
                "person_name",
                "company_name",
                "affiliation",
                "email",
                "created_at",
                "payment_status",
                "payment_id",
                "payment_date",
            ]
        )

    expected_cols = [
        "id",
        "booking_date",
        "start_time",
        "end_time",
        "resource_type",
        "person_name",
        "company_name",
        "affiliation",
        "email",
        "created_at",
        "payment_status",
        "payment_id",
        "payment_date",
    ]
    for c in expected_cols:
        if c not in df.columns:
            df[c] = None

    if "created_at" in df.columns:
        try:
            # Ensure created_at is timezone-aware UTC
            df["created_at"] = pd.to_datetime(df["created_at"], utc=True)

            # Add a new column with IST time
            df["created_at_ist"] = (
                df["created_at"]
                .dt.tz_convert("Asia/Kolkata")
                .dt.tz_localize(None)  # drop tz info, keep clean local datetime
            )
        except Exception as e:
            print("created_at IST conversion error:", e)

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
def check_conflict(booking_date, start_time, end_time, requested_resources):
    """
    Checks overlaps for the same date *only* for rows that share at least one resource.
    - requested_resources may be a list of strings or a single comma-joined string.
    Returns (bool_conflict, details_or_None)
    """
    # Normalize requested_resources into a set of trimmed lowercase tokens
    if requested_resources is None:
        req_set = set()
    elif isinstance(requested_resources, (list, tuple, set)):
        req_set = {
            str(x).strip().lower() for x in requested_resources if str(x).strip()
        }
    else:
        # single string (possibly comma-separated)
        req_set = {
            t.strip().lower() for t in str(requested_resources).split(",") if t.strip()
        }

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
        SELECT booking_date, start_time, end_time, resource_type, person_name, company_name
        FROM resource_bookings
        WHERE booking_date = :bdate
    """
    )

    try:
        with engine.connect() as conn:
            rows = conn.execute(sql, {"bdate": booking_date}).mappings().all()
    except Exception as e:
        print("check_conflict DB error:", e)
        return False, None

    for r in rows:
        # Parse stored resource_type CSV into a set of tokens (lowercased)
        raw = r.get("resource_type") or ""
        existing_set = {t.strip().lower() for t in str(raw).split(",") if t.strip()}

        # If no intersection, skip this row (different resources)
        if req_set and existing_set and req_set.isdisjoint(existing_set):
            continue
        # If both sets empty, treat as potential conflict (conservative)
        # If req_set empty (shouldn't happen since form validates), treat as potential conflict
        # Proceed to time overlap check

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
            # build details showing which resource(s) intersected
            intersect = (
                ", ".join(sorted(req_set.intersection(existing_set)))
                if req_set and existing_set
                else (", ".join(sorted(existing_set)) if existing_set else "")
            )
            details = (
                f"Existing booking for [{intersect or r.get('resource_type','')}] "
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
    st.subheader(":red[**👉 Book a Resource**]")
    with st.form("booking_form"):
        with st.popover("Check Pricing ₹ (per hour)"):
            st.write(resource_price_list)
        booking_date = st.date_input("Booking Date (YYYY-MM-DD)*")
        start_time = st.time_input("Start Time (24hrs Format)*")
        end_time = st.time_input("End Time (24hrs Format)*")
        resource_types = st.multiselect("Resource Type*", resource_list)
        person_name = st.text_input("Person Name*")
        company_name = st.text_input("Company*")
        affiliation = st.selectbox("Affiliation*", ["I-HUB", "IISER", "Other"])
        email = st.text_input("Email*")

        submitted = st.form_submit_button("Submit Booking")

        if submitted:
            missing = []
            if not booking_date:
                missing.append("Booking Date")
            if not start_time:
                missing.append("Start Time")
            if not end_time:
                missing.append("End Time")
            if not resource_types:
                missing.append("Resource Type")
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
                if requested_start < now + timedelta(hours=18):
                    st_red_alert("Please book at least 18 hours in advance.")
                    return
                # Validation for working hours
                office_start = dtime(9, 0)
                office_end = dtime(18, 0)
                if start_time < office_start or end_time > office_end:
                    st_red_alert("Bookings are allowed only between 09:00 - 18:00.")
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

                with st.spinner("Checking conflict…"):
                    conflict, details = check_conflict(
                        booking_date, start_time, end_time, resource_types
                    )

                if conflict:
                    st_red_alert(f"❌ Time conflict! {details}")
                else:
                    resource_type_str = ", ".join(resource_types)

                    add_booking(
                        booking_date,
                        start_time,
                        end_time,
                        resource_type_str,
                        person_name,
                        company_name,
                        affiliation,
                        email,
                    )

                    subject = f"Booking confirmation for resource(s) on {booking_date}"
                    body = (
                        f"Hello {person_name},\n\n"
                        f"Your booking for resources has been confirmed (subject to the receipt of payment).\n\n"
                        f"Date: {booking_date} (YYYY/MM/DD)\n"
                        f"From: {start_time}\n"
                        f"To: {end_time}\n"
                        f"Company: {company_name}\n"
                        f"Affiliation: {affiliation}\n\n"
                        f"Resources Booked: {resource_type_str}.\n\n"
                        ""
                        "Thank you!"
                        f"\n\nPrimary Contact: {cfg.PRIMARY_CONTACT}\n"
                        f"Secondary Contact: {cfg.SECONDARY_CONTACT}\n\n"
                        f"------------------------------------------------------------\n"
                        f"NOTE: To enable us process this booking, please pay via: {payment_link} (comment your name during payment) and share the payment reference.\n"
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
                    st.session_state["_flash"] = (
                        f"✅ Booking successfull, check email!<br><br>To proceed further, please pay via: {payment_link}"
                    )
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
            margin: -80px 0 10px 0;
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
    Timeline builder:
    - Explodes rows so each canonical resource becomes its own row (prevents overlap).
    - Computes a per-day slot index and shifts x (date) by a tiny fraction of a day so bars sit side-by-side.
    - Dynamically computes bar width but keeps it thinner by default.
    """
    if df is None or df.empty:
        return None, {"reason": "empty_df"}

    required = {
        "booking_date",
        "start_time",
        "end_time",
        "resource_type",
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

    # --- Compute how many bars will be placed per day ---
    # For each row, count how many canonical resources it maps to (so multi-resource rows count multiple bars).
    canonical = [r.strip() for r in getattr(cfg, "resource_list", [])]
    canonical_lower = [r.lower() for r in canonical]

    def extract_canonical_tokens(row_val):
        if not row_val:
            return []
        toks = [t.strip() for t in str(row_val).split(",") if t.strip()]
        # keep only tokens that match canonical list (exact match case-insensitive)
        return [t for t in toks if t.lower() in canonical_lower]

    # reset_index so we can keep original row identity for tooltip info
    dfw = dfw.reset_index(drop=True)
    dfw["_orig_idx"] = dfw.index

    # build exploded dataframe
    exploded_rows = []
    for _, row in dfw.iterrows():
        tokens = extract_canonical_tokens(row["resource_type"])
        if not tokens:
            # keep rows with no canonical match as-is (optional: skip them)
            continue
        for tok in tokens:
            exploded_rows.append(
                {
                    "_orig_idx": row["_orig_idx"],
                    "DateOnly": row["DateOnly"],
                    "StartH": row["StartH"],
                    "DurH": row["DurH"],
                    "person_name": row.get("person_name"),
                    "company_name": row.get("company_name"),
                    "start_time": row.get("start_time"),
                    "end_time": row.get("end_time"),
                    "ResourceCanonical": tok,  # keeps original capitalization from token
                }
            )

    if not exploded_rows:
        return None, {"reason": "no_canonical_rows"}

    df_exp = pd.DataFrame(exploded_rows)

    # Standardize ResourceCanonical to canonical capitalization by mapping lowercase -> canonical
    canon_map = {r.lower(): r for r in canonical}
    df_exp["ResourceCanonical"] = (
        df_exp["ResourceCanonical"]
        .str.strip()
        .str.lower()
        .map(lambda v: canon_map.get(v, v))
    )

    # Compute slots per day: each row on same DateOnly gets a unique slot index (0..n-1)
    df_exp["slot_idx"] = df_exp.groupby("DateOnly").cumcount()
    slot_counts = (
        df_exp.groupby("DateOnly")["slot_idx"].max().add(1).to_dict()
    )  # number of bars per day

    # --- compute width per bar dynamically so they fit side-by-side ---
    ms_per_day = 24 * 60 * 60 * 1000
    # reserve 80% of day width to hold bars, leave 20% for breathing room
    usable_fraction = 0.60

    max_bars_per_day = max([int(v) for v in slot_counts.values()] + [1])
    bar_width_ms = int(ms_per_day * (usable_fraction / max_bars_per_day))
    # sensible caps (smaller max width)
    min_width_ms = int(ms_per_day * 0.0025)
    max_width_ms = int(ms_per_day * 0.35)
    bar_width_ms = max(min_width_ms, min(bar_width_ms, max_width_ms))

    # spacing multiplier between adjacent slots (slightly larger than width to avoid touching)
    spacing_factor = 1.08
    width_days = bar_width_ms / ms_per_day

    # compute offset in fractional days for each row: center the group on the date
    def compute_offset_days(row):
        count = slot_counts.get(row["DateOnly"], 1)
        idx = row["slot_idx"]
        center = (count - 1) / 2.0
        # per-slot shift in days
        per_slot = width_days * spacing_factor
        return (idx - center) * per_slot

    df_exp["offset_days"] = df_exp.apply(compute_offset_days, axis=1)
    # final x positions: DateOnly + offset_days
    df_exp["x_pos"] = pd.to_datetime(df_exp["DateOnly"]) + pd.to_timedelta(
        df_exp["offset_days"], unit="D"
    )

    fig = go.Figure()

    # Build one trace per resource (clean legend)
    for resource in canonical:
        color = getattr(cfg, "resource_color_map", {}).get(resource, default_color)

        subset = df_exp[df_exp["ResourceCanonical"] == resource]
        if subset.empty:
            continue

        xs = list(subset["x_pos"])
        ys = list(subset["DurH"])
        bases = list(subset["StartH"])
        customdata = [
            [
                row.get("person_name"),
                row.get("company_name"),
                row.get("start_time"),
                row.get("end_time"),
            ]
            for _, row in subset.iterrows()
        ]

        fig.add_bar(
            x=xs,
            y=ys,
            base=bases,
            marker_color=color,
            width=[bar_width_ms] * len(xs),
            name=resource,
            offsetgroup=resource,
            customdata=customdata,
            hovertemplate=(
                "<b>%{customdata[0]}</b> (%{customdata[1]})<br>Date: %{x|%Y-%m-%d}<br>From: %{customdata[2]}<br>To: %{customdata[3]}<extra></extra>"
            ),
            showlegend=True,
            marker_line_width=0,
        )

    # Y axis simple ticks (every 2 hours)
    tick_vals = list(range(0, 25, 2))
    tick_text = [f"{h:02d}:00" for h in tick_vals]

    # Force daily ticks: dtick in milliseconds = 24 * 60 * 60 * 1000
    one_day_ms = ms_per_day

    # set tick0 to the epoch of start_window so ticks start exactly there
    # convert to milliseconds epoch for tick0 accepted formats: use ISO string as safe option
    tick0_iso = pd.to_datetime(start_window).strftime("%Y-%m-%dT%H:%M:%S")

    # Layout: horizontal legend at bottom, leave ample bottom margin so legend does not overlap
    # If you need more space for a long legend, increase 'b' or reduce legend.font.size.

    fig.update_layout(
        height=getattr(cfg, "GRAPH_HEIGHT", 620),
        bargap=0.02,
        bargroupgap=0.01,
        barmode="group",
        xaxis=dict(
            type="date",
            range=[start_window, end_window],
            fixedrange=True,
            title="Date",
            tickangle=-90,
            tickfont=dict(size=10),
            dtick=one_day_ms,  # one tick per day
            tick0=tick0_iso,  # aligns ticks to the start_window
            tickformat="%d %b",  # day + month format
            automargin=True,
            domain=[0.0, 1.0],
        ),
        yaxis=dict(
            range=[0, 24],
            tickvals=tick_vals,
            ticktext=tick_text,
            fixedrange=True,
            title="Time",
            automargin=True,
        ),
        margin=dict(
            l=40, r=20, t=40, b=130
        ),  # <-- reserve big bottom margin for horizontal legend
        legend=dict(
            title="Resource Type",
            orientation="h",
            yanchor="top",
            y=-0.40,  # place legend below the plot area (negative y)
            xanchor="center",
            x=0.5,
            traceorder="normal",
        ),
    ),

    return fig, {
        "reason": "ok",
        "rows_plotted": int(len(dfw)),
        "invalid_durations": invalid_count,
    }


# endregion

# region Chapter 12: Cached wrapper to build the timeline figure


@st.cache_data(ttl=7 * 24 * 60 * 60)  # 1 week
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


@st.cache_data(ttl=7 * 24 * 60 * 60)  # 1 week
def load_lottiefile(filepath: str, page_id: str = "resource"):
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
