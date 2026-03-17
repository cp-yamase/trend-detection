"""
event_keywords.py - イベントキーワード辞書

構造:
  EVENT_KEYWORDS = {
    "カテゴリ名": {
      "tag": str,          # ルールタグ・DB記録用
      "keywords": [str],   # Filtered Stream の OR 条件に使うキーワード群
      "description": str,  # 人間向け説明
    }
  }
"""

EVENT_KEYWORDS = {

    "SECURITY": {
        "tag": "SECURITY",
        "description": "ハック・エクスプロイト・不正流出など",
        "keywords": [
            "hack", "hacked", "hacking",
            "exploit", "exploited",
            "breach", "breached",
            "vulnerability", "vulnerable",
            "attack", "attacked",
            "drained", "drain",
            "stolen", "steal",
            "rug pull", "rugpull",
            "scam", "fraud",
        ],
    },

    "EXCHANGE_ISSUE": {
        "tag": "EXCHANGE_ISSUE",
        "description": "取引所障害・出金停止・破綻など",
        "keywords": [
            "withdrawal suspended", "withdrawals suspended",
            "withdraw", "withdrawal",
            "outage",
            "down", "offline",
            "maintenance",
            "frozen", "freeze",
            "halted", "halt",
            "suspend", "suspended",
            "insolvent", "insolvency",
            "bankrupt", "bankruptcy",
            "出金停止", "障害", "メンテナンス",
        ],
    },

    "LISTING": {
        "tag": "LISTING",
        "description": "上場・廃止・新規取り扱い開始など",
        "keywords": [
            "listing", "listed",
            "delist", "delisted", "delisting",
            "will list", "now live",
            "上場", "廃止", "取り扱い開始",
        ],
    },

    "REGULATORY": {
        "tag": "REGULATORY",
        "description": "規制・法的措置・制裁など",
        "keywords": [
            "ban", "banned",
            "lawsuit", "sued", "suing",
            "charges", "charged",
            "sanction", "sanctioned",
            "fine", "fined",
            "seized", "seizure",
            "arrest", "arrested",
            "investigation", "investigated",
            "規制", "訴訟", "制裁", "差し押さえ", "逮捕",
        ],
    },

    "MARKET_SHOCK": {
        "tag": "MARKET_SHOCK",
        "description": "急落・急騰・強制清算など",
        "keywords": [
            "crash", "crashed",
            "dump", "dumped",
            "flash crash",
            "liquidation", "liquidated",
            "margin call",
            "ATH", "all time high",
            "all time low",
            "暴落", "急落", "急騰", "清算",
        ],
    },

    "PROTOCOL": {
        "tag": "PROTOCOL",
        "description": "プロトコル緊急停止・アップグレード・フォークなど",
        "keywords": [
            "pause", "paused",
            "emergency",
            "fork", "forked",
            "migration",
            "upgrade",
            "deprecated",
            "shutdown",
            "緊急停止", "フォーク", "アップグレード",
        ],
    },
}
