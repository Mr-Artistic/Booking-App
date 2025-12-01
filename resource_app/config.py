import streamlit as st
from datetime import datetime, date, timedelta

DB_NAME = "bookings.db"


def get_timeline_start():
    """Returns timeline start dynamically (1 day ago at midnight)"""
    _now = datetime.now()
    return (_now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def get_timeline_end():
    """Returns timeline end dynamically (10 days from now at midnight)"""
    _now = datetime.now()
    return (_now + timedelta(days=10)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


# Stale helper window
TODAY = date.today()
_NOW = datetime.now()
TIMELINE_START = (_NOW - timedelta(days=1)).replace(
    hour=0, minute=0, second=0, microsecond=0
)
TIMELINE_END = (_NOW + timedelta(days=10)).replace(
    hour=0, minute=0, second=0, microsecond=0
)


# Visual Styles
GRAPH_HEIGHT = 400
TABLE_HEIGHT = 250
LINE_COLOR = "grey"
LINE_STYLE = "dot"

# Email Configuration
SMTP_HOST = st.secrets.get("smtp_host")
SMTP_PORT = int(st.secrets.get("smtp_port") or 587)
SMTP_USER = st.secrets.get("email_user")
SMTP_PASS = st.secrets.get("email_pass")
PRIMARY_CONTACT = st.secrets.get("primary_contact_for_resource")
SECONDARY_CONTACT = st.secrets.get("secondary_contact_for_resource")
CC_EMAILS = st.secrets[
    "cc_emails_for_resource"
]  # must contain at least two email addresses"


# Resources

resource_list = st.secrets.get("resource_list")
resource_price_list = st.secrets.get("resource_price_list")
resource_color_map = st.secrets.get("resource_color_map")

# Payment

payment_link = st.secrets.get("payment_link")
