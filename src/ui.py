"""
ui.py – Streamlit front-end
──────────────────────────
Launch with:
$ export OPENAI_API_KEY="sk-..."
$ export SENDGRID_API_KEY="SG-..."
$ streamlit run ui.py
"""
import streamlit as st, random, pandas as pd
from backend import build_newsletter, send_newsletter

st.set_page_config(page_title="Personalised Financial Newsletter", layout="centered")
st.title("📬 Personalised Financial Newsletter")

email  = st.text_input("Email")
region = st.selectbox("Region", ["USA", "Europe", "Germany", "Asia", "Australia"])

if "tickers" not in st.session_state:
    st.session_state.tickers = ["", "", ""]

for i in range(3):
    st.session_state.tickers[i] = st.text_input(f"Stock Ticker {i+1}",
                                                value=st.session_state.tickers[i],
                                                key=f"T{i}")

if st.button("🎲 Random (S&P 500)"):
    sp = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]["Symbol"].tolist()
    st.session_state.tickers = random.sample(sp, 3)

if st.button("Submit"):
    tickers = [t.upper() for t in st.session_state.tickers if t]
    if not (email and tickers):
        st.error("Please enter an e-mail and at least one ticker."); st.stop()

    try:
        with st.spinner("Building newsletter…"):
            md, chart64, price_df = build_newsletter(tickers, region)

        st.subheader("Latest Close Prices")
        st.dataframe(price_df.tail(1).T)

        st.subheader("Preview")
        st.markdown(md)
        if chart64:
            st.image(f"data:image/png;base64,{chart64}", caption="30-day performance", use_column_width=True)

        if st.button("Send Newsletter"):
            with st.spinner("Sending e-mail…"):
                send_newsletter(email, md, chart64)
            st.success(f"Newsletter sent to {email}!")

    except Exception as e:
        st.error(f"Error creating newsletter: {e}")