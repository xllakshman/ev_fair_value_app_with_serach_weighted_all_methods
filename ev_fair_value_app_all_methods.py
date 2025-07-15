
import streamlit as st
import pandas as pd
import yfinance as yf
import altair as alt
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
from ta.trend import MACD

st.set_page_config(page_title="Stock Fair Value Analyzer", layout="wide")
st.title("📈 India and USA Stock Fair Value Estimator")

GITHUB_CSV_URL = "https://raw.githubusercontent.com/xllakshman/ev_fair_value_app_with_serach/main/stock_list.csv"

def dcf_valuation(eps, growth_rate=0.08, discount_rate=0.10):
    try:
        if eps <= 0:
            return None
        cf = eps * (1 + growth_rate)
        return round(cf / (discount_rate - growth_rate), 2)
    except:
        return None

def graham_valuation(eps, bvps):
    try:
        if eps <= 0 or bvps <= 0:
            return None
        return round((22.5 * eps * bvps) ** 0.5, 2)
    except:
        return None

def pe_valuation(eps, pe_ratio=15):
    try:
        if eps <= 0:
            return None
        return round(eps * pe_ratio, 2)
    except:
        return None

def get_fair_value(ticker, growth_rate=0.10):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        ev = info.get("enterpriseValue")
        ebitda = info.get("ebitda")
        shares = info.get("sharesOutstanding")
        current_price = info.get("currentPrice")
        if not (ev and ebitda and shares):
            return None, None
        ev_ebitda_ratio = ev / ebitda
        projected_ebitda = ebitda * (1 + growth_rate)
        projected_ev = projected_ebitda * ev_ebitda_ratio
        fair_price = projected_ev / shares
        return fair_price, current_price
    except:
        return None, None

def ev_valuation(ticker):
    try:
        ticker = ticker.upper()
        fair_price, current_price = get_fair_value(ticker)
        if fair_price is None or current_price is None:
            return None
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="3y")
        company_name = info.get("shortName", "N/A")
        market_cap = info.get("marketCap", 0)
        industry = info.get("industry", "N/A")
        cap_type = (
            "Mega" if market_cap >= 200_000_000_000 else
            "Large" if market_cap >= 10_000_000_000 else
            "Mid" if market_cap >= 2_000_000_000 else "Small"
        )
        market = "India" if ticker.endswith(".NS") else "USA"
        underval_pct = ((fair_price - current_price) / current_price) * 100
        if fair_price < 0 or underval_pct < 5:
            band = "Over Valued"
        elif underval_pct > 30:
            band = "Deep Discount"
        elif underval_pct > 20:
            band = "High Value"
        elif underval_pct > 18:
            band = "Undervalued"
        else:
            band = "Fair/Premium"
        high_3y = hist["High"].max() if not hist.empty else None
        low_3y = hist["Low"].min() if not hist.empty else None
        entry_price = round(low_3y * 1.05, 2) if low_3y else "N/A"
        exit_price = round(high_3y * 0.95, 2) if high_3y else "N/A"
        return {
            "Symbol": ticker,
            "Name": company_name,
            "Fair Value (EV)": round(fair_price, 2),
            "Current Price": round(current_price, 2),
            "Undervalued (%)": round(underval_pct, 2),
            "Valuation Band": band,
            "Market": market,
            "Cap Size": cap_type,
            "Industry": industry,
            "3Y High": round(high_3y, 2) if high_3y else "N/A",
            "3Y Low": round(low_3y, 2) if low_3y else "N/A",
            "Entry Price": entry_price,
            "Exit Price": exit_price,
            "Signal": "Buy" if fair_price > current_price else "Hold/Sell"
        }
    except:
        return None

# On-demand search
st.markdown("## 🔍 On-Demand Stock Valuation")
search_ticker = st.text_input("Enter a stock ticker (e.g., AAPL, INFY.NS)")

if search_ticker:
    result = ev_valuation(search_ticker)
    stock = yf.Ticker(search_ticker)
    info = stock.info

    eps = info.get("trailingEps", 0)
    bvps = info.get("bookValue", 0)
    pe_ratio = info.get("trailingPE", 15)

    ev_val = result.get("Fair Value (EV)", None)
    dcf_val = dcf_valuation(eps)
    graham_val = graham_valuation(eps, bvps)
    pe_val = pe_valuation(eps, pe_ratio)

    tab1, tab2, tab3 = st.tabs(["📋 Filtered View", "📂 Full Raw Data", "📈 Valuation & Technicals"])

    with tab1:
        df = pd.DataFrame([result])
        df["Fair Value (DCF)"] = dcf_val
        df["Fair Value (Graham)"] = graham_val
        df["Fair Value (PE)"] = pe_val
        st.dataframe(df)

    with tab2:
        full_df = pd.DataFrame([{
            "Ticker": search_ticker,
            "EPS": eps,
            "Book Value": bvps,
            "PE Ratio": pe_ratio,
            "Fair Value (EV)": ev_val,
            "Fair Value (DCF)": dcf_val,
            "Fair Value (Graham)": graham_val,
            "Fair Value (PE)": pe_val
        }])
        st.dataframe(full_df)

    with tab3:
        weight_ev = st.slider("EV/EBITDA Weight", 0, 100, 30)
        weight_dcf = st.slider("DCF Weight", 0, 100, 30)
        weight_graham = st.slider("Graham Weight", 0, 100, 20)
        weight_pe = st.slider("PE Weight", 0, 100, 20)

        total_weight = weight_ev + weight_dcf + weight_graham + weight_pe
        if total_weight == 100 and all(v is not None for v in [ev_val, dcf_val, graham_val, pe_val]):
            combined_val = round(
                (ev_val * weight_ev +
                 dcf_val * weight_dcf +
                 graham_val * weight_graham +
                 pe_val * weight_pe) / 100, 2
            )
            st.markdown("### 💰 Valuation Comparison")
            st.table({
                "Method": ["EV", "DCF", "Graham", "PE", "Combined"],
                "Fair Value": [ev_val, dcf_val, graham_val, pe_val, combined_val]
            })

        hist = stock.history(period="5y")
        if hist.empty:
            hist = stock.history(period="3y")
        hist.reset_index(inplace=True)

        hist["SMA_50"] = SMAIndicator(close=hist["Close"], window=50).sma_indicator()
        hist["SMA_200"] = SMAIndicator(close=hist["Close"], window=200).sma_indicator()
        hist["RSI"] = RSIIndicator(close=hist["Close"], window=14).rsi()
        macd = MACD(close=hist["Close"])
        hist["MACD"] = macd.macd()
        hist["Signal"] = macd.macd_signal()

        base = alt.Chart(hist).encode(x="Date:T")
        st.altair_chart(base.mark_line(color="blue").encode(y="Close") +
                        base.mark_line(strokeDash=[4, 4], color="orange").encode(y="SMA_50") +
                        base.mark_line(strokeDash=[2, 2], color="green").encode(y="SMA_200"),
                        use_container_width=True)

        st.altair_chart(base.mark_line(color="purple").encode(y="MACD") +
                        base.mark_line(color="red").encode(y="Signal"),
                        use_container_width=True)

        st.altair_chart(alt.Chart(hist).mark_line(color="darkgreen").encode(x="Date:T", y="RSI"),
                        use_container_width=True)
