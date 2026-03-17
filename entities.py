"""
entities.py - エンティティ辞書

構造:
  ENTITIES = {
    "カテゴリ名": {
      "グループID": ["表記1", "表記2", ...],
      ...
    }
  }

Filtered Stream ルール生成時は、グループ内の表記を OR でまとめて1ルールとする。
どの表記が言及されたかはPhase7(OpenClaw)がツイート本文から抽出する。
"""

ENTITIES = {

    # ------------------------------------------------------------------
    # 主要通貨（時価総額上位50ベース）
    # ------------------------------------------------------------------
    "CRYPTO": {
        "BTC":   ["Bitcoin", "BTC", "ビットコイン"],
        "ETH":   ["Ethereum", "ETH", "イーサリアム"],
        "SOL":   ["Solana", "SOL"],
        "XRP":   ["XRP", "Ripple"],
        "BNB":   ["BNB", "Binance Coin"],
        "ADA":   ["Cardano", "ADA"],
        "DOGE":  ["Dogecoin", "DOGE"],
        "AVAX":  ["Avalanche", "AVAX"],
        "DOT":   ["Polkadot", "DOT"],
        "MATIC": ["Polygon", "MATIC", "POL"],
        "LINK":  ["Chainlink", "LINK"],
        "UNI":   ["Uniswap", "UNI"],
        "ATOM":  ["Cosmos", "ATOM"],
        "LTC":   ["Litecoin", "LTC"],
        "NEAR":  ["NEAR Protocol", "NEAR"],
        "ICP":   ["Internet Computer", "ICP"],
        "APT":   ["Aptos", "APT"],
        "SUI":   ["Sui", "SUI"],
        "ARB":   ["Arbitrum", "ARB"],
        "OP":    ["Optimism", "OP"],
        "TON":   ["Toncoin", "TON"],
        "SHIB":  ["Shiba Inu", "SHIB"],
        "TRX":   ["TRON", "TRX"],
        "FIL":   ["Filecoin", "FIL"],
        "STX":   ["Stacks", "STX"],
    },

    # ------------------------------------------------------------------
    # ステーブルコイン
    # ------------------------------------------------------------------
    "STABLECOIN": {
        "USDT":  ["Tether", "USDT"],
        "USDC":  ["USDC", "USD Coin"],
        "DAI":   ["DAI", "MakerDAO"],
        "OTHER": ["BUSD", "TUSD", "PYUSD", "FDUSD"],
    },

    # ------------------------------------------------------------------
    # 取引所
    # ------------------------------------------------------------------
    "EXCHANGE": {
        "TIER1":  ["Binance", "Coinbase", "Kraken", "OKX", "Bybit"],
        "TIER2":  ["KuCoin", "Gate.io", "Bitfinex", "Gemini", "HTX", "Huobi"],
        "JAPAN":  [
            "bitFlyer", "Coincheck", "bitbank", "GMOコイン", "GMO Coin",
            "SBI VC Trade", "SBI VCトレード",
            "Zaif",
        ],
    },

    # ------------------------------------------------------------------
    # DeFi プロトコル
    # ------------------------------------------------------------------
    "DEFI": {
        "DEX":     ["Uniswap", "Curve", "dYdX", "GMX"],
        "LENDING": ["Aave", "Compound"],
        "OTHER":   ["Lido", "EigenLayer", "Pendle"],
    },

    # ------------------------------------------------------------------
    # Layer2 / インフラ
    # ------------------------------------------------------------------
    "LAYER2": {
        "L2":    ["Arbitrum", "Optimism", "Base", "zkSync", "StarkNet", "Linea"],
        "INFRA": ["Celestia", "EigenLayer"],
    },

    # ------------------------------------------------------------------
    # 規制当局
    # ------------------------------------------------------------------
    "REGULATOR": {
        "US":   ["SEC", "CFTC", "FinCEN", "OCC"],
        "INTL": ["FCA", "MAS", "FSA", "BaFin"],
    },
}
