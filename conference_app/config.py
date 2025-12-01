import streamlit as st
from datetime import datetime, date, timedelta

DB_NAME = "bookings.db"

# Timeline window
TODAY = date.today()


def get_timeline_start():
    """Returns timeline start dynamically (7 days ago at midnight)"""
    _now = datetime.now()
    return (_now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)


def get_timeline_end():
    """Returns timeline end dynamically (21 days from now at midnight)"""
    _now = datetime.now()
    return (_now + timedelta(days=21)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


# Stale helper window
_NOW = datetime.now()
TIMELINE_START = (_NOW - timedelta(days=7)).replace(
    hour=0, minute=0, second=0, microsecond=0
)
TIMELINE_END = (_NOW + timedelta(days=21)).replace(
    hour=0, minute=0, second=0, microsecond=0
)

# Visual Styles
GRAPH_HEIGHT = 300
TABLE_HEIGHT = 250
LINE_COLOR = "grey"
LINE_STYLE = "dot"

# Email Configuration
SMTP_HOST = st.secrets.get("smtp_host")
SMTP_PORT = int(st.secrets.get("smtp_port") or 587)
SMTP_USER = st.secrets.get("email_user")
SMTP_PASS = st.secrets.get("email_pass")
PRIMARY_CONTACT = st.secrets.get("primary_contact_for_conference")
SECONDARY_CONTACT = st.secrets.get("secondary_contact_for_conference")
CC_EMAILS = st.secrets[
    "cc_emails_for_conference"
]  # must contain at least two email addresses"
