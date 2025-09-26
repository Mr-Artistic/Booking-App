import streamlit as st
from datetime import datetime, date, timedelta

DB_NAME = "bookings.db"

# Timeline window (last month, this month, next month)
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


# Resource config

resource_list = [
    "3D Printer(FDM)",
    "3D Printer(SLA)",
    "Digital Microscope",
    "Electronics Test Bench",
    "High-end Workstation",
    "iMAC",
    "PCB Prototyping Machine",
    "Solder Station",
]

resource_price_list = {
    "3D Printer(FDM)": 0,
    "3D Printer(SLA)": 0,
    "Digital Microscope": 200,
    "Electronics Test Bench": 1000,
    "High-end Workstation": 750,
    "iMAC": 250,
    "PCB Prototyping Machine": 1000,
    "Solder Station": 100,
}


color_map = {
    "3D Printer(FDM)": "#1EE56A",
    "3D Printer(SLA)": "#E51E64",
    "Digital Microscope": "#E5B71E",
    "Electronics Test Bench": "#1E88E5",
    "High-end Workstation": "#E5DE1E",
    "iMAC": "#875F0E",
    "PCB Prototyping Machine": "#6A1EE5",
    "Solder Station": "#E21EE5",
}
