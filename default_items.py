# =====================================================================
# Category Definitions and Constraints
# =====================================================================
CATEGORIES = {
    "ja": {
        "transport": "🚗 移動・交通",
        "living":    "🍽️ 生活・環境",
        "wellbeing": "💖 心身の健康",
        "leisure":   "🎉 余暇・エンタメ",
        "learning":  "📚 自己研鑽",
    },
    "en": {
        "transport": "🚗 Transport",
        "living":    "🍽️ Living & Dining",
        "wellbeing": "💖 Well-being",
        "leisure":   "🎉 Leisure & Play",
        "learning":  "📚 Growth & Learning",
    }
}

CATEGORY_CONSTRAINTS = {
    "transport": {"or_tools_min": 1, "or_tools_max": 1,
                  "label_ja": "必須: 1つ選択（パッケージ）", "label_en": "Required: Choose 1 package"},
    "living":    {"or_tools_min": 0, "or_tools_max": 99,
                  "label_ja": "推奨: 1〜3つ", "label_en": "Recommended: 1-3"},
    "wellbeing": {"or_tools_min": 0, "or_tools_max": 99,
                  "label_ja": "推奨: 1〜2つ", "label_en": "Recommended: 1-2"},
    "leisure":   {"or_tools_min": 0, "or_tools_max": 99,
                  "label_ja": "推奨: 1〜3つ", "label_en": "Recommended: 1-3"},
    "learning":  {"or_tools_min": 0, "or_tools_max": 99,
                  "label_ja": "推奨: 1〜2つ", "label_en": "Recommended: 1-2"},
}

# =====================================================================
# Default Items List (Refined and Integrated)
# =====================================================================
DEFAULT_ITEMS = [
    # ── 1. Transport ────────────────────────────
    {"id": "default_transport_car_primary", "category": "transport", "priority": 2,
     "name_ja": "車メイン", "name_en": "Car (Primary)",
     "initial_cost": 25000, "monthly_cost": 650,
     "health": 0, "connections": 3, "freedom": 10, "growth": 1,
     "note_ja": "車両＋保険$120＋ガス$150＋駐車場等込み", "note_en": "Includes Vehicle, Insurance$120, Gas, etc."},
    {"id": "default_transport_motorcycle_primary", "category": "transport", "priority": 4,
     "name_ja": "バイクメイン", "name_en": "Motorcycle (Primary)",
     "initial_cost": 5000, "monthly_cost": 120,
     "health": 2, "connections": 4, "freedom": 8, "growth": 2,
     "note_ja": "車両$5000＋維持費(保険・ガス)$120", "note_en": "Vehicle$5000 + Maintenance$120"},
    {"id": "default_transport_car_share_bicycle", "category": "transport", "priority": 3,
     "name_ja": "カーシェア＋自転車", "name_en": "Car Share + Bicycle",
     "initial_cost": 500, "monthly_cost": 130,
     "health": 6, "connections": 3, "freedom": 5, "growth": 3,
     "note_ja": "カーシェア$100＋自転車維持$30", "note_en": "Car share$100 + Bicycle upkeep$30"},
    {"id": "default_transport_ebike_uber", "category": "transport", "priority": 4,
     "name_ja": "電動自転車＋Uber", "name_en": "E-Bike + Uber",
     "initial_cost": 2000, "monthly_cost": 160,
     "health": 5, "connections": 2, "freedom": 5, "growth": 2,
     "note_ja": "電動自転車維持$10＋Uber$150", "note_en": "E-Bike upkeep$10 + Uber$150"},
    {"id": "default_transport_public_transit", "category": "transport", "priority": 5,
     "name_ja": "公共交通メイン", "name_en": "Public Transit",
     "initial_cost": 0, "monthly_cost": 80,
     "health": 4, "connections": 4, "freedom": 2, "growth": 1,
     "note_ja": "定期券・バス等", "note_en": "Pass / Bus etc."},
    {"id": "default_transport_bicycle_only", "category": "transport", "priority": 6,
     "name_ja": "自転車のみ", "name_en": "Bicycle Only",
     "initial_cost": 500, "monthly_cost": 10,
     "health": 9, "connections": 2, "freedom": 4, "growth": 3,
     "note_ja": "健康効果最大", "note_en": "Maximum health benefits"},
    {"id": "default_transport_uber_only", "category": "transport", "priority": 7,
     "name_ja": "Uberのみ", "name_en": "Uber/Lyft Only",
     "initial_cost": 0, "monthly_cost": 250,
     "health": 0, "connections": 2, "freedom": 5, "growth": 2,
     "note_ja": "移動時間を有効活用", "note_en": "Efficient use of travel time"},

    # ── 2. Living & Dining ────────────────────────────
    {"id": "default_living_coffee_cafe", "category": "living", "priority": 1,
     "name_ja": "コーヒー・カフェ代", "name_en": "Coffee / Cafe",
     "initial_cost": 0, "monthly_cost": 60,
     "health": -1, "connections": 4, "freedom": 3, "growth": 2, "note_ja": "", "note_en": ""},
    {"id": "default_living_time_saving_appliances", "category": "living", "priority": 4,
     "name_ja": "時短家電（食洗機・ルンバ等）", "name_en": "Time-saving Appliances",
     "initial_cost": 800, "monthly_cost": 0,
     "health": 2, "connections": 1, "freedom": 8, "growth": 1, "note_ja": "家事時間を削減", "note_en": "Reduces chore time"},
    {"id": "default_living_housekeeping_service", "category": "living", "priority": 5,
     "name_ja": "家事代行サービス（月2回）", "name_en": "Housekeeping Service",
     "initial_cost": 0, "monthly_cost": 150,
     "health": 3, "connections": 0, "freedom": 9, "growth": 1, "note_ja": "時間と心の余裕", "note_en": "Frees up time and mental space"},

    # ── 3. Well-being ────────────────────────────
    {"id": "default_wellbeing_gym_yoga", "category": "wellbeing", "priority": 1,
     "name_ja": "ジム・ヨガスタジオ", "name_en": "Gym / Yoga",
     "initial_cost": 100, "monthly_cost": 60,
     "health": 9, "connections": 5, "freedom": -1, "growth": 4, "note_ja": "入会金＋月会費", "note_en": "Enrollment + monthly fee"},
    {"id": "default_wellbeing_massage_spa_sauna", "category": "wellbeing", "priority": 5,
     "name_ja": "マッサージ・スパ・サウナ", "name_en": "Massage / Spa / Sauna",
     "initial_cost": 0, "monthly_cost": 80,
     "health": 6, "connections": 2, "freedom": 2, "growth": 2, "note_ja": "フィジカルのメンテナンス", "note_en": "Physical maintenance"},
    {"id": "default_wellbeing_travel_retreat_fund", "category": "wellbeing", "priority": 6,
     "name_ja": "旅行・リトリート積立", "name_en": "Travel / Retreat Fund",
     "initial_cost": 0, "monthly_cost": 150,
     "health": 3, "connections": 7, "freedom": 9, "growth": 7, "note_ja": "非日常によるリフレッシュ", "note_en": "Refresh through extraordinary experiences"},


    # ── 4. Leisure & Play ────────────────────────────
    {"id": "default_leisure_socializing_drinks", "category": "leisure", "priority": 1,
     "name_ja": "交際費・飲み代", "name_en": "Socializing / Drinks",
     "initial_cost": 0, "monthly_cost": 150,
     "health": -2, "connections": 10, "freedom": 2, "growth": 2, "note_ja": "過度な飲酒は健康に影響", "note_en": "Excess affects health"},
    {"id": "default_leisure_home_drinks", "category": "leisure", "priority": 3,
     "name_ja": "宅飲み", "name_en": "Home Drinks",
     "initial_cost": 0, "monthly_cost": 70,
     "health": -1, "connections": 4, "freedom": 3, "growth": 1, "note_ja": "外飲みより低コスト", "note_en": "Lower cost than going out"},
    {"id": "default_leisure_fashion_beauty", "category": "leisure", "priority": 7,
     "name_ja": "ファッション・美容", "name_en": "Fashion / Beauty",
     "initial_cost": 0, "monthly_cost": 100,
     "health": 1, "connections": 4, "freedom": 2, "growth": 2, "note_ja": "自己表現と自信", "note_en": "Self-expression and confidence"},

    # ── 5. Growth & Learning ────────────────────────────
    {"id": "default_learning_books_audible", "category": "learning", "priority": 1,
     "name_ja": "本・電子書籍・Audible", "name_en": "Books / Audible",
     "initial_cost": 0, "monthly_cost": 30,
     "health": 1, "connections": 1, "freedom": 3, "growth": 8, "note_ja": "コスパの良い自己投資", "note_en": "High ROI self-investment"},

]