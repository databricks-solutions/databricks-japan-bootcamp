"""
Bootcamp 大阪 v2.1 用 ハンズオンデータ生成スクリプト

変更点 (v2.0 → v2.1):
- dirty_companies と transactions を統合 → raw_transactions
- 期間を 3 ヶ月 → 15 ヶ月 (2025-01 〜 2026-03) に拡張
- 取引先間の売上格差を明確化 (Top tier / Middle / Bottom)
- YoY 成長 / 季節変動 を組み込む (Metric View 比較デモ用)

出力 CSV:
- master_companies.csv (25 社・変更なし)
- raw_transactions.csv (~2500 行・15 ヶ月・dirty company_name 含む)
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path
from calendar import monthrange

random.seed(42)

OUT_DIR = Path(__file__).parent / "csv_v2"
OUT_DIR.mkdir(exist_ok=True)

# ============================================================
# 1. マスタ: 正式取引先 25 社 (変更なし)
# ============================================================
MASTERS = [
    ("M001", "株式会社ABC商事",         "商社",       "大阪",   1985),
    ("M002", "XYZコーポレーション",      "IT",         "東京",   2002),
    ("M003", "大阪電子工業株式会社",     "製造業",     "大阪",   1968),
    ("M004", "京都製造株式会社",         "製造業",     "京都",   1975),
    ("M005", "神戸物産株式会社",         "食品",       "兵庫",   1990),
    ("M006", "関西エネルギー株式会社",   "エネルギー", "大阪",   1972),
    ("M007", "大阪鉄鋼株式会社",         "製造業",     "大阪",   1958),
    ("M008", "西日本電気株式会社",       "エネルギー", "広島",   1962),
    ("M009", "日本化学工業株式会社",     "化学",       "東京",   1955),
    ("M010", "阪神運輸株式会社",         "物流",       "兵庫",   1980),
    ("M011", "兵庫食品工業株式会社",     "食品",       "兵庫",   1965),
    ("M012", "九州自動車工業株式会社",   "製造業",     "福岡",   1970),
    ("M013", "北海道乳業株式会社",       "食品",       "北海道", 1948),
    ("M014", "東京メディカル株式会社",   "医療",       "東京",   1995),
    ("M015", "中部不動産株式会社",       "不動産",     "愛知",   1988),
    ("M016", "近畿システムズ株式会社",   "IT",         "大阪",   2005),
    ("M017", "東海運輸株式会社",         "物流",       "愛知",   1975),
    ("M018", "山陽建設株式会社",         "建設",       "岡山",   1960),
    ("M019", "四国電機株式会社",         "製造業",     "香川",   1972),
    ("M020", "瀬戸内テクノロジー株式会社","IT",         "広島",   2010),
    ("M021", "大阪ファイナンス株式会社", "金融",       "大阪",   1992),
    ("M022", "ジャパン医薬品株式会社",   "医療",       "東京",   1985),
    ("M023", "東北機械工業株式会社",     "製造業",     "宮城",   1968),
    ("M024", "新潟食品株式会社",         "食品",       "新潟",   1970),
    ("M025", "全国保険株式会社",         "金融",       "東京",   1955),
]

with open(OUT_DIR / "master_companies.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["master_id", "official_name", "industry", "region", "established_year"])
    w.writerows(MASTERS)
print(f"✅ master_companies.csv: {len(MASTERS)} 社")

# ============================================================
# 2. 取引先別の特性 (Tier / 成長率 / 季節性)
# ============================================================
# Top 5: 売上大、高成長  /  Middle 10: 普通  /  Bottom 10: 売上小、停滞
COMPANY_TIER = {}
for i, m in enumerate(MASTERS):
    mid = m[0]
    if i < 5:
        COMPANY_TIER[mid] = {
            "tier": "top",
            "transactions_per_month": (15, 30),     # 月の取引件数レンジ
            "amount_range": (1_000_000, 5_000_000),  # 取引額レンジ
            "yoy_growth": random.uniform(0.20, 0.50),  # 2026 は 2025 比 +20-50%
        }
    elif i < 15:
        COMPANY_TIER[mid] = {
            "tier": "middle",
            "transactions_per_month": (5, 15),
            "amount_range": (200_000, 800_000),
            "yoy_growth": random.uniform(-0.10, 0.20),
        }
    else:
        COMPANY_TIER[mid] = {
            "tier": "bottom",
            "transactions_per_month": (1, 5),
            "amount_range": (50_000, 200_000),
            "yoy_growth": random.uniform(-0.30, 0.10),
        }

# 季節性: Oct-Dec が +30%, Mar が +20%, それ以外は通常
SEASONAL_BOOST = {1: 1.0, 2: 0.9, 3: 1.2, 4: 1.0, 5: 1.0, 6: 1.0,
                  7: 0.9, 8: 0.85, 9: 1.0, 10: 1.3, 11: 1.3, 12: 1.4}

# ============================================================
# 3. 表記揺れパターン (v2.0 と同じ)
# ============================================================
def variants(official: str) -> list[str]:
    v = set()
    name = official
    if "株式会社" in name:
        core = name.replace("株式会社", "").strip()
        v.add(f"(株){core}")
        v.add(f"{core}(株)")
        v.add(f"株式会社 {core}")
        v.add(f"{core}株式会社")
        v.add(core)
        v.add(f"{core} ")
        kana_map = {
            "ABC商事": "エービーシー商事",
            "XYZコーポレーション": "エックスワイゼットコーポレーション",
        }
        if core in kana_map:
            v.add(kana_map[core])
        eng_map = {
            "ABC商事": "ABC Corp.",
            "XYZコーポレーション": "XYZ Corp.",
            "大阪電子工業": "OSAKA ELECTRONICS",
            "神戸物産": "Kobe Bussan",
        }
        if core in eng_map:
            v.add(eng_map[core])
    return list(v) or [official]

# ============================================================
# 4. 各取引行を生成する関数 (汚染込み)
# ============================================================
PERSON_NAMES = ["田中様", "鈴木様", "佐藤様", "山田部長", "高橋課長", "渡辺さん"]
DEPT_NAMES = ["経理部", "営業部", "総務部", "購買部", "経営企画"]
MEMOS = ["(4月から)", "(新規)", "[要確認]", "(継続)", "(契約更新)"]
INDUSTRIES_NOTE = ["(食品)", "(IT)", "(物流)", "(医療)"]
INPUT_DEPTS = ["営業部", "経理部", "サポート部"]

def make_dirty_name(official: str) -> str:
    """正式名から汚い表記を選んで返す。一定確率で人名/部署名/メモ等が混入"""
    base = random.choice(variants(official) + [official])
    if random.random() < 0.15:
        base = base + "  "
    if random.random() < 0.05:
        base = base.replace("(", "（").replace(")", "）")

    roll = random.random()
    if roll < 0.05:
        return random.choice(["", "N/A", "-", "未設定", "(不明)"])
    elif roll < 0.10:
        return f"{base.rstrip()} {random.choice(PERSON_NAMES)}"
    elif roll < 0.14:
        return f"{base.rstrip()} {random.choice(DEPT_NAMES)}"
    elif roll < 0.18:
        return f"{base.rstrip()} {random.choice(MEMOS)}"
    elif roll < 0.21:
        return f"{base.rstrip()} {random.choice(INDUSTRIES_NOTE)}"
    elif roll < 0.23:
        return base.rstrip() + "\t"
    elif roll < 0.25:
        return f"旧{base.rstrip()}"
    return base

# ============================================================
# 5. 取引データ生成 (15 ヶ月分)
# ============================================================
# 2025-01 〜 2026-03
def month_iter(start_year, start_month, n_months):
    y, m = start_year, start_month
    for _ in range(n_months):
        yield (y, m)
        m += 1
        if m > 12:
            m = 1
            y += 1

tx_rows = []
tx_seq = 0

for (yr, mo) in month_iter(2025, 1, 15):
    # 各月のシード調整
    days_in_month = monthrange(yr, mo)[1]
    season = SEASONAL_BOOST[mo]

    for m in MASTERS:
        mid, official, *_ = m
        cfg = COMPANY_TIER[mid]
        # 2026 年は YoY 成長率を反映
        yoy_mult = (1 + cfg["yoy_growth"]) if yr == 2026 else 1.0
        # 月の取引件数 (季節 + YoY 反映)
        base_count = random.randint(*cfg["transactions_per_month"])
        n_tx = max(1, int(base_count * season * (yoy_mult ** 0.5)))

        for _ in range(n_tx):
            tx_seq += 1
            day = random.randint(1, days_in_month)
            tx_date = date(yr, mo, day).isoformat()
            amount = random.randint(*cfg["amount_range"])
            amount = int(amount * season * yoy_mult)

            tx_rows.append({
                "transaction_id": f"T{tx_seq:06d}",
                "company_name": make_dirty_name(official),
                "department": random.choice(INPUT_DEPTS),
                "transaction_date": tx_date,
                "amount": amount,
            })

random.shuffle(tx_rows)

with open(OUT_DIR / "raw_transactions.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["transaction_id", "company_name", "department", "transaction_date", "amount"])
    w.writeheader()
    w.writerows(tx_rows)

print(f"✅ raw_transactions.csv: {len(tx_rows)} 行")

# ============================================================
# 6. サマリ
# ============================================================
print()
print("=== データサマリ ===")
print(f"期間: 2025-01 〜 2026-03 (15 ヶ月)")
print(f"取引先: 25 社 (Top 5 / Middle 10 / Bottom 10)")
print(f"総取引数: {len(tx_rows)} 行")
print(f"出力ディレクトリ: {OUT_DIR}")
