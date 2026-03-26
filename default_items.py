CATEGORY_CONSTRAINTS = {
    "transport":     {"or_tools_min": 1, "or_tools_max": 1,
                      "label_ja": "必須: 1つ選択（パッケージ）",
                      "label_en": "Required: Choose 1 package"},
    "health":        {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "推奨: 1〜2つ", "label_en": "Recommended: 1-2"},
    "entertainment": {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "任意: 上限3つ推奨", "label_en": "Optional: max 3 recommended"},
    "food":          {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "推奨: 1つ", "label_en": "Recommended: 1"},
    "learning":      {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "推奨: 1つ", "label_en": "Recommended: 1"},
    "home":          {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "任意", "label_en": "Optional"},
    "wellness":      {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "推奨: 1〜2つ", "label_en": "Recommended: 1-2"},
    "hobby":         {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "任意: 上限2つ推奨", "label_en": "Optional: max 2 recommended"},
    "insurance":     {"or_tools_min": 0, "or_tools_max": 99,
                      "label_ja": "任意", "label_en": "Optional"},
}

# ─────────────────────────────────────────────────────────────────────
# スコア設計方針（-10 〜 +10）
#
# health:
#   +10 パーソナルトレーナー、毎日の本格運動
#    0  中立（保険・サブスク等）
#   -10 タバコ（最大リスク）
#
# connections:
#   +10 ボランティア、交際費・友人との時間
#    0  中立
#    -  孤立を促す活動（なし〜-2程度）
#
# freedom:
#   +10 車メイン（最大移動自由）
#    0  中立
#   -5  ペット（外出制約大）
#   -3  固定予約が必要なもの（PT・セラピー等）
#
# growth:
#   +10 資格・オンライン講座（最大成長）
#    0  中立
#   -4  タバコ（時間・健康浪費）
#   -2  アルコール（常習化リスク）
# ─────────────────────────────────────────────────────────────────────

DEFAULT_ITEMS = [
    # ── 移動手段（パッケージ・最大1つ）────────────────────────────
    {"category": "transport", "priority": 2,
     "name_ja": "車メイン",           "name_en": "Car (Primary)",
     "initial_cost": 25000, "monthly_cost": 650,
     "health": 1,  "connections": 3,  "freedom": 10, "growth": 1,
     "note_ja": "車両＋保険$120＋ガス$150＋駐車場$100＋メンテ$80",
     "note_en": "Vehicle + Insurance$120 + Gas$150 + Parking$100 + Maintenance$80"},

    {"category": "transport", "priority": 3,
     "name_ja": "カーシェア＋自転車", "name_en": "Car Share + Bicycle",
     "initial_cost": 500,   "monthly_cost": 130,
     "health": 6,  "connections": 3,  "freedom": 5,  "growth": 3,
     "note_ja": "カーシェア$100＋自転車維持$30", "note_en": "Car share$100 + Bicycle upkeep$30"},

    {"category": "transport", "priority": 3,
     "name_ja": "電動自転車＋Uber",   "name_en": "E-Bike + Uber",
     "initial_cost": 2000,  "monthly_cost": 160,
     "health": 5,  "connections": 2,  "freedom": 5,  "growth": 2,
     "note_ja": "電動自転車維持$10＋Uber$150", "note_en": "E-bike upkeep$10 + Uber$150"},

    {"category": "transport", "priority": 4,
     "name_ja": "公共交通メイン",     "name_en": "Public Transit",
     "initial_cost": 0,     "monthly_cost": 80,
     "health": 3,  "connections": 4,  "freedom": 2,  "growth": 1,
     "note_ja": "定期券・バス等", "note_en": "Pass / Bus etc."},

    {"category": "transport", "priority": 4,
     "name_ja": "自転車のみ",         "name_en": "Bicycle Only",
     "initial_cost": 500,   "monthly_cost": 10,
     "health": 9,  "connections": 2,  "freedom": 4,  "growth": 3,
     "note_ja": "自転車＋維持費", "note_en": "Bicycle + upkeep"},

    {"category": "transport", "priority": 5,
     "name_ja": "Uberのみ",           "name_en": "Uber/Lyft Only",
     "initial_cost": 0,     "monthly_cost": 250,
     "health": -2, "connections": 2,  "freedom": 5,  "growth": 0,
     "note_ja": "座位時間が長くなりやすい", "note_en": "Tends to increase sedentary time"},

    # ── 健康・フィットネス──────────────────────────────────────────
    {"category": "health", "priority": 1,
     "name_ja": "ランニング",              "name_en": "Running (Shoes)",
     "initial_cost": 150,  "monthly_cost": 0,
     "health": 8,  "connections": 3,  "freedom": 5,  "growth": 4,
     "note_ja": "シューズ等", "note_en": "Shoes etc."},

    {"category": "health", "priority": 2,
     "name_ja": "ジム",                    "name_en": "Gym",
     "initial_cost": 100,  "monthly_cost": 50,
     "health": 9,  "connections": 5,  "freedom": -1, "growth": 4,
     "note_ja": "入会金＋月会費", "note_en": "Enrollment + monthly fee"},

    {"category": "health", "priority": 3,
     "name_ja": "ヨガ・ストレッチ",        "name_en": "Yoga / Stretching",
     "initial_cost": 50,   "monthly_cost": 30,
     "health": 7,  "connections": 4,  "freedom": 2,  "growth": 5,
     "note_ja": "マット等", "note_en": "Mat etc."},

    {"category": "health", "priority": 4,
     "name_ja": "栄養サプリ",              "name_en": "Supplements",
     "initial_cost": 0,    "monthly_cost": 40,
     "health": 4,  "connections": 0,  "freedom": 0,  "growth": 1,
     "note_ja": "", "note_en": ""},

    {"category": "health", "priority": 5,
     "name_ja": "スマートウォッチ",        "name_en": "Smartwatch",
     "initial_cost": 300,  "monthly_cost": 0,
     "health": 5,  "connections": 1,  "freedom": 1,  "growth": 3,
     "note_ja": "", "note_en": ""},

    {"category": "health", "priority": 6,
     "name_ja": "ヨガスタジオ",            "name_en": "Yoga Studio",
     "initial_cost": 0,    "monthly_cost": 80,
     "health": 8,  "connections": 6,  "freedom": -2, "growth": 5,
     "note_ja": "", "note_en": ""},

    {"category": "health", "priority": 7,
     "name_ja": "パーソナルトレーナー",    "name_en": "Personal Trainer",
     "initial_cost": 0,    "monthly_cost": 200,
     "health": 10, "connections": 4,  "freedom": -3, "growth": 7,
     "note_ja": "", "note_en": ""},

    {"category": "health", "priority": 8,
     "name_ja": "フィットネスマシーン",    "name_en": "Fitness Machine",
     "initial_cost": 1500, "monthly_cost": 0,
     "health": 8,  "connections": -1, "freedom": 2,  "growth": 3,
     "note_ja": "ホームジム・孤独になりやすい", "note_en": "Home gym — can be isolating"},

    {"category": "health", "priority": 9,
     "name_ja": "スポーツ用品",            "name_en": "Sports Equipment",
     "initial_cost": 200,  "monthly_cost": 0,
     "health": 7,  "connections": 4,  "freedom": 3,  "growth": 4,
     "note_ja": "", "note_en": ""},

    # ── エンタメ・サブスク────────────────────────────────────────
    {"category": "entertainment", "priority": 1,
     "name_ja": "Spotify",              "name_en": "Spotify",
     "initial_cost": 0,    "monthly_cost": 11,
     "health": 1,  "connections": 2,  "freedom": 3,  "growth": 1,
     "note_ja": "", "note_en": ""},

    {"category": "entertainment", "priority": 2,
     "name_ja": "Netflix",              "name_en": "Netflix",
     "initial_cost": 0,    "monthly_cost": 18,
     "health": -2, "connections": 3,  "freedom": 2,  "growth": 1,
     "note_ja": "長時間視聴は座位時間・睡眠に影響", "note_en": "Binge-watching affects sleep & activity"},

    {"category": "entertainment", "priority": 3,
     "name_ja": "YouTube Premium",      "name_en": "YouTube Premium",
     "initial_cost": 0,    "monthly_cost": 14,
     "health": -1, "connections": 1,  "freedom": 3,  "growth": 4,
     "note_ja": "", "note_en": ""},

    {"category": "entertainment", "priority": 4,
     "name_ja": "Audible",              "name_en": "Audible",
     "initial_cost": 0,    "monthly_cost": 15,
     "health": 1,  "connections": 1,  "freedom": 3,  "growth": 7,
     "note_ja": "運動しながら聴ける", "note_en": "Can listen while exercising"},

    {"category": "entertainment", "priority": 5,
     "name_ja": "映画・コンサート",     "name_en": "Movies / Concerts",
     "initial_cost": 0,    "monthly_cost": 40,
     "health": 1,  "connections": 7,  "freedom": 2,  "growth": 4,
     "note_ja": "", "note_en": ""},

    {"category": "entertainment", "priority": 6,
     "name_ja": "ゲーム",               "name_en": "Gaming",
     "initial_cost": 500,  "monthly_cost": 20,
     "health": -3, "connections": 4,  "freedom": 2,  "growth": 2,
     "note_ja": "長時間プレイは健康・睡眠に影響", "note_en": "Extended play affects health & sleep"},

    {"category": "entertainment", "priority": 7,
     "name_ja": "その他サブスク",       "name_en": "Other Subscriptions",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": -1, "connections": 1,  "freedom": 0,  "growth": 1,
     "note_ja": "", "note_en": ""},

    # ── 食・生活（基本食費以上）──────────────────────────────────
    {"category": "food", "priority": 1,
     "name_ja": "外食（ランチ中心）",   "name_en": "Dining Out (Lunch)",
     "initial_cost": 0,    "monthly_cost": 150,
     "health": 1,  "connections": 6,  "freedom": 4,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "food", "priority": 2,
     "name_ja": "コーヒー・カフェ代",  "name_en": "Coffee / Cafe",
     "initial_cost": 0,    "monthly_cost": 60,
     "health": -1, "connections": 5,  "freedom": 3,  "growth": 2,
     "note_ja": "過剰摂取は睡眠・健康に影響", "note_en": "Excess caffeine affects sleep & health"},

    {"category": "food", "priority": 3,
     "name_ja": "食材宅配サービス",     "name_en": "Meal Kit Delivery",
     "initial_cost": 0,    "monthly_cost": 120,
     "health": 6,  "connections": 2,  "freedom": 2,  "growth": 5,
     "note_ja": "HelloFresh等", "note_en": "HelloFresh etc."},

    {"category": "food", "priority": 4,
     "name_ja": "外食（ディナー中心）", "name_en": "Dining Out (Dinner)",
     "initial_cost": 0,    "monthly_cost": 250,
     "health": 0,  "connections": 8,  "freedom": 2,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "food", "priority": 5,
     "name_ja": "食材こだわり（高品質）","name_en": "Premium Groceries",
     "initial_cost": 0,    "monthly_cost": 100,
     "health": 7,  "connections": 1,  "freedom": 2,  "growth": 3,
     "note_ja": "オーガニック・地産地消等", "note_en": "Organic / local produce etc."},

    # ── 学習・自己投資────────────────────────────────────────────
    {"category": "learning", "priority": 1,
     "name_ja": "オンライン講座",       "name_en": "Online Courses",
     "initial_cost": 0,    "monthly_cost": 30,
     "health": 1,  "connections": 2,  "freedom": 3,  "growth": 10,
     "note_ja": "Udemy/Coursera等", "note_en": "Udemy / Coursera etc."},

    {"category": "learning", "priority": 2,
     "name_ja": "語学学習",             "name_en": "Language Learning",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": 1,  "connections": 5,  "freedom": 5,  "growth": 9,
     "note_ja": "Duolingo等", "note_en": "Duolingo etc."},

    {"category": "learning", "priority": 3,
     "name_ja": "本・電子書籍",         "name_en": "Books / E-books",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": 1,  "connections": 2,  "freedom": 3,  "growth": 8,
     "note_ja": "", "note_en": ""},

    {"category": "learning", "priority": 4,
     "name_ja": "セミナー・ワークショップ","name_en": "Seminars / Workshops",
     "initial_cost": 0,    "monthly_cost": 100,
     "health": 1,  "connections": 6,  "freedom": 1,  "growth": 8,
     "note_ja": "", "note_en": ""},

    {"category": "learning", "priority": 5,
     "name_ja": "資格取得",             "name_en": "Professional Certification",
     "initial_cost": 500,  "monthly_cost": 50,
     "health": 0,  "connections": 3,  "freedom": 4,  "growth": 10,
     "note_ja": "", "note_en": ""},

    # ── 住環境・快適性────────────────────────────────────────────
    {"category": "home", "priority": 1,
     "name_ja": "高速インターネット",   "name_en": "High-Speed Internet",
     "initial_cost": 0,    "monthly_cost": 80,
     "health": 0,  "connections": 4,  "freedom": 4,  "growth": 5,
     "note_ja": "リモートワーク・学習の基盤", "note_en": "Foundation for remote work & learning"},

    {"category": "home", "priority": 2,
     "name_ja": "エルゴノミクスチェア", "name_en": "Ergonomic Chair",
     "initial_cost": 500,  "monthly_cost": 0,
     "health": 6,  "connections": 0,  "freedom": 2,  "growth": 3,
     "note_ja": "腰痛・姿勢改善", "note_en": "Prevents back pain, improves posture"},

    {"category": "home", "priority": 3,
     "name_ja": "空気清浄機",           "name_en": "Air Purifier",
     "initial_cost": 300,  "monthly_cost": 5,
     "health": 7,  "connections": 0,  "freedom": 1,  "growth": 1,
     "note_ja": "", "note_en": ""},

    {"category": "home", "priority": 4,
     "name_ja": "スタンディングデスク", "name_en": "Standing Desk",
     "initial_cost": 500,  "monthly_cost": 0,
     "health": 5,  "connections": 0,  "freedom": 2,  "growth": 4,
     "note_ja": "", "note_en": ""},

    {"category": "home", "priority": 5,
     "name_ja": "観葉植物・インテリア", "name_en": "Plants / Interior",
     "initial_cost": 200,  "monthly_cost": 10,
     "health": 3,  "connections": 2,  "freedom": 1,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "home", "priority": 6,
     "name_ja": "収納・整理用品",       "name_en": "Storage / Organization",
     "initial_cost": 200,  "monthly_cost": 0,
     "health": 2,  "connections": 0,  "freedom": 3,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "home", "priority": 7,
     "name_ja": "コーヒーメーカー",     "name_en": "Coffee Maker",
     "initial_cost": 200,  "monthly_cost": 20,
     "health": 0,  "connections": 3,  "freedom": 2,  "growth": 1,
     "note_ja": "", "note_en": ""},

    {"category": "home", "priority": 8,
     "name_ja": "食洗機",               "name_en": "Dishwasher",
     "initial_cost": 800,  "monthly_cost": 5,
     "health": 1,  "connections": 1,  "freedom": 6,  "growth": 1,
     "note_ja": "家事時間を削減し自由時間を増やす", "note_en": "Frees up time for other activities"},

    # ── メンタル・ウェルネス──────────────────────────────────────
    {"category": "wellness", "priority": 1,
     "name_ja": "旅行・小旅行積立",          "name_en": "Travel Fund",
     "initial_cost": 0,    "monthly_cost": 150,
     "health": 3,  "connections": 7,  "freedom": 9,  "growth": 7,
     "note_ja": "", "note_en": ""},

    {"category": "wellness", "priority": 2,
     "name_ja": "交際費・友人との時間",      "name_en": "Social Activities",
     "initial_cost": 0,    "monthly_cost": 100,
     "health": 3,  "connections": 10, "freedom": 2,  "growth": 4,
     "note_ja": "", "note_en": ""},

    {"category": "wellness", "priority": 3,
     "name_ja": "瞑想・マインドフルネス",    "name_en": "Meditation App",
     "initial_cost": 0,    "monthly_cost": 13,
     "health": 5,  "connections": 0,  "freedom": 3,  "growth": 6,
     "note_ja": "Calm/Headspace等", "note_en": "Calm/Headspace etc."},

    {"category": "wellness", "priority": 4,
     "name_ja": "マッサージ・スパ",          "name_en": "Massage / Spa",
     "initial_cost": 0,    "monthly_cost": 80,
     "health": 6,  "connections": 2,  "freedom": 2,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "wellness", "priority": 5,
     "name_ja": "ペット",                    "name_en": "Pet",
     "initial_cost": 500,  "monthly_cost": 100,
     "health": 5,  "connections": 7,  "freedom": -5, "growth": 3,
     "note_ja": "外出・旅行・残業に制約が生まれる", "note_en": "Restricts travel, overtime, and spontaneous plans"},

    {"category": "wellness", "priority": 6,
     "name_ja": "セラピー・カウンセリング",  "name_en": "Therapy / Counseling",
     "initial_cost": 0,    "monthly_cost": 150,
     "health": 5,  "connections": 3,  "freedom": -2, "growth": 9,
     "note_ja": "", "note_en": ""},

    {"category": "wellness", "priority": 7,
     "name_ja": "ボランティア・コミュニティ","name_en": "Volunteering / Community",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": 3,  "connections": 10, "freedom": -1, "growth": 7,
     "note_ja": "", "note_en": ""},

    # ── 趣味・嗜好────────────────────────────────────────────────
    {"category": "hobby", "priority": 1,
     "name_ja": "習い事",               "name_en": "Hobby Classes",
     "initial_cost": 100,  "monthly_cost": 80,
     "health": 3,  "connections": 7,  "freedom": -1, "growth": 8,
     "note_ja": "音楽・アート等", "note_en": "Music, Art etc."},

    {"category": "hobby", "priority": 2,
     "name_ja": "アウトドア・スポーツ", "name_en": "Outdoor / Sports",
     "initial_cost": 300,  "monthly_cost": 30,
     "health": 7,  "connections": 6,  "freedom": 7,  "growth": 5,
     "note_ja": "ハイキング等", "note_en": "Hiking etc."},

    {"category": "hobby", "priority": 3,
     "name_ja": "ファッション・美容",   "name_en": "Fashion / Beauty",
     "initial_cost": 0,    "monthly_cost": 100,
     "health": 1,  "connections": 4,  "freedom": 2,  "growth": 2,
     "note_ja": "", "note_en": ""},

    {"category": "hobby", "priority": 4,
     "name_ja": "料理・グルメ",         "name_en": "Cooking / Gourmet",
     "initial_cost": 100,  "monthly_cost": 50,
     "health": 4,  "connections": 6,  "freedom": 1,  "growth": 7,
     "note_ja": "道具・食材等", "note_en": "Tools + ingredients"},

    {"category": "hobby", "priority": 5,
     "name_ja": "読書・マンガ",         "name_en": "Reading / Manga",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": 1,  "connections": 2,  "freedom": 3,  "growth": 7,
     "note_ja": "", "note_en": ""},

    {"category": "hobby", "priority": 6,
     "name_ja": "その他趣味",           "name_en": "Other Hobbies",
     "initial_cost": 200,  "monthly_cost": 50,
     "health": 2,  "connections": 4,  "freedom": 3,  "growth": 5,
     "note_ja": "", "note_en": ""},

    {"category": "hobby", "priority": 7,
     "name_ja": "お酒",                 "name_en": "Alcohol",
     "initial_cost": 0,    "monthly_cost": 60,
     "health": -5, "connections": 5,  "freedom": 2,  "growth": -2,
     "note_ja": "常習化すると健康・判断力に影響", "note_en": "Habitual use affects health & judgment"},

    {"category": "hobby", "priority": 8,
     "name_ja": "タバコ/Vape",          "name_en": "Tobacco / Vape",
     "initial_cost": 50,   "monthly_cost": 80,
     "health": -9, "connections": 0,  "freedom": -1, "growth": -4,
     "note_ja": "健康リスク最大・依存性あり", "note_en": "Highest health risk — addictive"},

    # ── 保険────────────────────────────────────────────────────
    {"category": "insurance", "priority": 1,
     "name_ja": "賃貸保険",       "name_en": "Renters Insurance",
     "initial_cost": 0,    "monthly_cost": 20,
     "health": 1,  "connections": 0,  "freedom": 3,  "growth": 1,
     "note_ja": "万一の際の経済的安心", "note_en": "Financial peace of mind"},

    {"category": "insurance", "priority": 2,
     "name_ja": "生命保険",       "name_en": "Life Insurance",
     "initial_cost": 0,    "monthly_cost": 50,
     "health": 1,  "connections": 4,  "freedom": 1,  "growth": 2,
     "note_ja": "家族・パートナーへの安心", "note_en": "Security for family / partner"},

    {"category": "insurance", "priority": 3,
     "name_ja": "車保険",         "name_en": "Car Insurance",
     "initial_cost": 0,    "monthly_cost": 120,
     "health": 1,  "connections": 0,  "freedom": 2,  "growth": 1,
     "note_ja": "車メイン選択時は必須", "note_en": "Required if Car (Primary)"},

    {"category": "insurance", "priority": 4,
     "name_ja": "所得補償保険",   "name_en": "Disability Insurance",
     "initial_cost": 0,    "monthly_cost": 30,
     "health": 1,  "connections": 0,  "freedom": 4,  "growth": 2,
     "note_ja": "病気・怪我時の収入保障", "note_en": "Income protection during illness/injury"},

    {"category": "insurance", "priority": 5,
     "name_ja": "ペット保険",     "name_en": "Pet Insurance",
     "initial_cost": 0,    "monthly_cost": 40,
     "health": 1,  "connections": 1,  "freedom": 2,  "growth": 1,
     "note_ja": "ペット選択時に推奨", "note_en": "Recommended if Pet selected"},
]

CATEGORIES = {
    "ja": {
        "transport":     "🚗 移動手段",
        "health":        "💪 健康・フィットネス",
        "entertainment": "🎬 エンタメ・サブスク",
        "food":          "🍽 食・生活",
        "learning":      "📚 学習・自己投資",
        "home":          "🏠 住環境・快適性",
        "wellness":      "🧘 メンタル・ウェルネス",
        "hobby":         "🎨 趣味・嗜好",
        "insurance":     "🛡 保険",
    },
    "en": {
        "transport":     "🚗 Transport",
        "health":        "💪 Health & Fitness",
        "entertainment": "🎬 Entertainment",
        "food":          "🍽 Food & Living",
        "learning":      "📚 Learning",
        "home":          "🏠 Home & Comfort",
        "wellness":      "🧘 Mental Wellness",
        "hobby":         "🎨 Hobbies",
        "insurance":     "🛡 Insurance",
    }
}
