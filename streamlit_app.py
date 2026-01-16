# streamlit_app.py
from pathlib import Path
import runpy

HERE = Path(__file__).parent
APP = HERE / "app.py"

if APP.exists():
    runpy.run_path(str(APP), run_name="__main__")
else:
    import streamlit as st
    st.error("Не намирам app.py в repo-то. Качи app.py в root папката.")
