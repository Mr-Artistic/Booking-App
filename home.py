import streamlit as st

conference_page = st.Page(
    "conference_app/app.py", title="Book Conference", icon="🏢", url_path="conference"
)
resource_page = st.Page(
    "resource_app/app.py", title="Book Resource", icon="🛠️", url_path="resource"
)

pg = st.navigation([conference_page, resource_page], position="top")
pg.run()
