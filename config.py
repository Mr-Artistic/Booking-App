import streamlit as st
from datetime import date
from dateutil.relativedelta import relativedelta

DB_NAME = "bookings.db"

# Timeline window (last month, this month, next month)
TODAY = date.today()
TIMELINE_START = TODAY.replace(day=1) - relativedelta(months=1)
TIMELINE_END = TODAY.replace(day=1) + relativedelta(months=2)

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
CC_EMAIL = st.secrets.get("cc_email")
