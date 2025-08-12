# 必要ライブラリをインストール（Google Colabの場合）
# pip install yfinance matplotlib pandas

import time
import math
from typing import Dict, List
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

# ---- 対象銘柄 ----
japan_symbols = {
    "Tokyo Electron": "8035.T",
    "Disco": "6146.T",
    "SCREEN Holdings": "7735.T",
}
us_symbols = {
    "NVIDIA": "NVDA",
    "AMD": "AMD",
    "Apple": "AAPL",
}
uk_symbols = {
    "ARM Holdings": "ARM",  # ADR (NASDAQ: ARM)
}
name_to_ticker: Dict[str, str] = {**japan_symbols, **us_symbols, **uk_symbols}

# ---- yfinanceの並列を切ってDBロック回避、Adj Closeを確実に取得 ----
def dl_adj_close(tickers: List[str], period="5y") -> pd.DataFrame:
    """
    tickersをまとめて取得。auto_adjust=False固定で 'Adj Close' を返す。
    並列を切って database is locked を回避。失敗は除外。
    """
    # まとめて取得
    raw = yf.download(
        tickers,
        period=period,
        auto_adjust=False,     # 'Adj Close' を出す
        group_by="ticker",     # 銘柄ごとの縦持ち
        threads=False,         # DBロック回避
        progress=False
    )

    frames = []
    succeeded = []
    for t in tickers:
        try:
            # 単一銘柄の 'Adj Close' を取り出してシリーズに
            s = raw[(t, "Adj Close")].rename(t)
            if s.dropna().empty:
                continue
            frames.append(s)
            succeeded.append(t)
        except Exception:
            # 個別再試行（1回だけ）
            try:
                time.sleep(0.5)
                r = yf.download(
                    t, period=period, auto_adjust=False,
                    group_by="ticker", threads=False, progress=False
                )
                s2 = r["Adj Close"].rename(t)
                if not s2.dropna().empty:
                    frames.append(s2)
                    succeeded.append(t)
            except Exception:
                pass

    if not frames:
        raise RuntimeError("価格データの取得にすべて失敗しました。")

    df = pd.concat(frames, axis=1)
    return df, succeeded

# ---- ダウンロード ----
tickers = list(name_to_ticker.values())
adj_close, ok_tickers = dl_adj_close(tickers, period="5y")

# 名前（企業名）に付け替え（成功したティッカーのみ）
inv_map = {v: k for k, v in name_to_ticker.items()}
adj_close = adj_close.rename(columns=inv_map)

# ---- 正規化（スタート=100） ----
start = adj_close.iloc[0]
normalized = adj_close.divide(start).multiply(100)

# ---- 5年リターン（%） ----
last = adj_close.iloc[-1]
returns = (last / start - 1.0) * 100.0
returns = returns.dropna().sort_values(ascending=False)

# ---- グラフ ----
plt.figure(figsize=(12, 6))
for col in normalized.columns:
    plt.plot(normalized.index, normalized[col], label=col)

plt.title("5-Year Performance (Adj Close, Normalized=100)")
plt.xlabel("Date")
plt.ylabel("Normalized Price")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.show()

# ---- ランキング表示 ----
print("\n=== 5-Year Return Ranking (Adj Close) ===")
out = pd.DataFrame({"5Y Return (%)": returns.round(2)})
print(out.to_string())

# ---- 取得失敗銘柄の表示 ----
failed = [t for t in tickers if t not in ok_tickers]
if failed:
    print("\n[Info] 取得できなかったティッカー:", failed)