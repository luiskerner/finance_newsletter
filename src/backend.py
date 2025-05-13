"""
backend.py  –  fetch prices, generate summaries, send e-mail
────────────────────────────────────────────────────────────
pip install --upgrade yfinance feedparser matplotlib sendgrid openai
"""
from __future__ import annotations
import os, io, datetime, base64, pandas as pd, matplotlib.pyplot as plt
import feedparser, yfinance as yf
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from openai import OpenAI         # → pip install --upgrade openai

# ─────────────────── OpenAI helper ──────────────────────────────────────────────
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")
client      = OpenAI(api_key=OPENAI_KEY)

def gpt(prompt: str, model: str = "gpt-3.5-turbo", temp: float = 0.3) -> str:
    """Return the single completion string or raise."""
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temp,
    )
    return resp.choices[0].message.content.strip()

# ─────────────────── Macro overview ────────────────────────────────────────────
def macro_overview() -> str:
    today = datetime.date.today().strftime("%B %d, %Y")
    prompt = (f"As of {today}, in ≤200 words summarise last week’s key global "
              f"macroeconomic and geopolitical trends an investor should know.")
    return gpt(prompt, model="gpt-4o-mini")

# ─────────────────── News functions ────────────────────────────────────────────
def fetch_yahoo_news(tickers: list[str], n: int = 20):
    query = ",".join(tickers)
    feed  = feedparser.parse(
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={query}&region=US&lang=en-US"
    )
    return [(e.title, e.link) for e in feed.entries[:n]]

def filter_news(articles, tickers):
    matches = []
    upper = [t.upper() for t in tickers]
    for title, link in articles:
        for t in upper:
            if t in title.upper():
                matches.append((t, title, link)); break
    return matches

def short_summary(title: str, link: str) -> str:
    prompt = ( "Summarise the following headline & link in 2-3 sentences for an investor.\n"
               f"TITLE: {title}\nLINK: {link}")
    return gpt(prompt)

# ─────────────────── Price + chart ─────────────────────────────────────────────
def price_data(tickers: list[str]) -> tuple[pd.DataFrame, str]:
    df = yf.download(tickers, period="30d", interval="1d",
                     group_by="ticker", auto_adjust=True, threads=False)
    if df.empty:
        raise ValueError("yfinance returned no data.")

    closes = {}
    for t in tickers:
        try:
            closes[t] = (df[t] if isinstance(df, pd.DataFrame) else df)["Close"]
        except KeyError:
            pass
    if not closes:
        raise ValueError("No Close column in download.")

    close_df = pd.DataFrame(closes).dropna()
    cum_ret  = close_df / close_df.iloc[0] - 1

    # Build a compact PNG
    plt.figure(figsize=(6, 3))
    for t in cum_ret.columns:
        plt.plot(cum_ret.index, cum_ret[t] * 100, label=t)
    plt.ylabel("% return"); plt.xticks([])
    plt.legend(); plt.tight_layout()
    buf = io.BytesIO(); plt.savefig(buf, format="png"); plt.close()
    png64 = base64.b64encode(buf.getvalue()).decode(); buf.close()

    return close_df.round(2), png64

# ─────────────────── Master generator ──────────────────────────────────────────
def build_newsletter(tickers: list[str], region: str):
    macro = macro_overview()
    news  = fetch_yahoo_news(tickers)
    matched = filter_news(news, tickers)

    article_block = ""
    for t, title, link in matched[:6]:
        try:
            s = short_summary(title, link)
        except Exception:
            s = title
        article_block += f"- **{t}** {s}\n  <{link}>\n"

    prices, chart64 = price_data(tickers)
    table_md = prices.tail(1).T.to_markdown()

    md = (f"## Macroeconomic Overview\n{macro}\n\n"
          f"## Latest 30-day Close (last row) – {region}\n{table_md}\n\n"
          f"## News Highlights\n{article_block or 'No relevant news today.'}")

    return md, chart64, prices

# ─────────────────── SendGrid e-mail ───────────────────────────────────────────
def send_newsletter(to_email: str, md_body: str, img64: str):
    sg_key = os.getenv("SENDGRID_API_KEY", "")
    if not sg_key:
        raise RuntimeError("SENDGRID_API_KEY not set")
    img_tag = f'<img src="data:image/png;base64,{img64}" width="600">' if img64 else ""
    html    = f"<html><body>{md_body.replace(chr(10), '<br>')}{img_tag}</body></html>"

    msg = Mail(
        from_email="luis.kerner@icloud.com",
        to_emails=to_email,
        subject="Your Personalised Financial Newsletter",
        html_content=html,
    )
    response = SendGridAPIClient(sg_key).send(msg)
    print(response.status_code)
    print(response.body)
    print(response.headers)
    
