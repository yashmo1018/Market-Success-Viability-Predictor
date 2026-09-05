"""Category taxonomy for data acquisition: what to keep, what to exclude.

Physical products come from Amazon Reviews 2023 (McAuley Lab, HuggingFace) —
matched by title keywords against per-source-file streams. Apps come from
Google Play via search-term discovery.

Keep/exclude rules are the categorization contract: a product enters a category
only if its title matches >=1 include pattern and 0 exclude patterns. Exclude
lists kill the classic false positives (cases, cables, replacement parts,
accessories) that would poison category profiles.
"""

from __future__ import annotations

# Amazon source file per physical category (dataset category name on HF)
AMAZON_SOURCE = {
    "wireless_headphones": "Electronics",
    "bluetooth_speakers": "Electronics",
    "smartwatches": "Electronics",
    "smartphones": "Cell_Phones_and_Accessories",
    "power_banks": "Cell_Phones_and_Accessories",
    "kitchen_appliances": "Appliances",
    # ice_makers replaces the contaminated kitchen_appliances category (see
    # scripts/select_ice_makers.py). Reviews stream from the Appliances dump.
    "ice_makers": "Appliances",
}

# title must contain >=1 include, 0 excludes (case-insensitive substring)
PHYSICAL_RULES = {
    "wireless_headphones": {
        "include": ["wireless headphone", "bluetooth headphone", "wireless earbud",
                    "bluetooth earbud", "true wireless", "wireless over-ear",
                    "wireless on-ear", "tws earbud", "anc headphone",
                    "noise cancelling headphone", "wireless earphone"],
        "exclude": ["case for", "cover for", "replacement", "ear pad", "earpad",
                    "ear tip", "eartip", "cable", "adapter", "wired headphone",
                    "stand", "hook", "charging dock", "skin for", "strap"],
    },
    "bluetooth_speakers": {
        "include": ["bluetooth speaker", "portable speaker", "wireless speaker",
                    "smart speaker", "party speaker", "shower speaker"],
        "exclude": ["case for", "cover for", "replacement", "mount", "stand for",
                    "cable", "adapter", "bag for", "skin for", "car speaker",
                    "bookshelf", "soundbar bracket"],
    },
    "smartwatches": {
        "include": ["smart watch", "smartwatch", "fitness watch", "fitness tracker",
                    "activity tracker", "gps watch"],
        "exclude": ["band for", "strap", "case for", "cover for", "replacement",
                    "screen protector", "charger for", "charging cable", "bezel",
                    "protector for"],
    },
    "smartphones": {
        "include": ["smartphone", "cell phone", "unlocked phone", "mobile phone",
                    "5g phone", "4g lte phone", "android phone", "iphone"],
        "exclude": ["case", "cover", "screen protector", "holder", "mount",
                    "charger", "cable", "adapter", "replacement", "battery for",
                    "stylus", "lens", "ring light", "grip", "wallet", "armband",
                    "skin", "tempered glass", "sim ", "stand", "tripod", "pouch"],
    },
    "power_banks": {
        "include": ["power bank", "portable charger", "battery pack",
                    "portable battery", "external battery"],
        "exclude": ["case for", "cover for", "replacement", "for laptop only",
                    "jump starter", "solar panel only", "skin for", "pouch"],
    },
    "kitchen_appliances": {
        "include": ["blender", "air fryer", "toaster", "coffee maker", "espresso",
                    "food processor", "stand mixer", "hand mixer", "rice cooker",
                    "pressure cooker", "slow cooker", "kettle", "juicer",
                    "microwave", "waffle maker", "grill", "ice maker"],
        "exclude": ["replacement", "part", "filter for", "accessory", "accessories",
                    "gasket", "blade for", "cup for", "lid for", "seal", "cover for",
                    "decal", "mat for", "cookbook", "pod holder", "descaler",
                    "cleaner for", "attachment"],
    },
    # ice_makers: the clean, coherent replacement for kitchen_appliances.
    # Scope = countertop / portable / nugget ICE-MAKER MACHINES only.
    # Excludes target refrigerator replacement PARTS (the real contaminant);
    # deliberately does NOT exclude bin/tray/scoop/filter — real machines list
    # those as features. See scripts/select_ice_makers.py for the strict picker.
    "ice_makers": {
        "include": ["ice maker", "ice machine", "nugget ice", "countertop ice",
                    "portable ice", "bullet ice"],
        "exclude": ["assembly", "auger", "solenoid", "compatible with", "replacement",
                    "for whirlpool", "for kenmore", "for ge ", "for frigidaire",
                    "for lg", "for samsung", "for kitchenaid", "for hotpoint",
                    "for maytag", "french door", "refrigerator/freezer", "cu ft",
                    "cu. ft", "cu.ft", "icemaker for", "water valve", "inlet valve"],
    },
}

# Play Store discovery search terms per app category
PLAY_SEARCH_TERMS = {
    "finance_apps": ["budget planner", "expense tracker", "personal finance",
                     "money manager", "investing app", "savings tracker",
                     "bill reminder", "budgeting"],
    "health_fitness_apps": ["workout tracker", "home workout", "calorie counter",
                            "meditation", "sleep tracker", "running app",
                            "yoga app", "habit health"],
    "productivity_apps": ["todo list", "task manager", "note taking", "calendar planner",
                          "focus timer", "habit tracker", "pomodoro", "mind map",
                          "notes app", "daily planner", "reminder app", "document scanner",
                          "pdf reader", "voice recorder", "journal app", "time tracker",
                          "checklist app", "grocery list", "meeting notes", "whiteboard app"],
    "education_apps": ["language learning", "math practice", "flashcards",
                       "learn coding", "exam prep", "vocabulary builder",
                       "kids learning", "study planner", "learn spanish", "learn french",
                       "english grammar", "math games kids", "brain training",
                       "piano lessons", "typing practice", "quiz game learning",
                       "science learning", "history quiz", "toddler learning",
                       "sat prep", "learn drawing", "chess learning"],
}

# Reddit context sources per category (optional; skipped on failure)
REDDIT_SUBS = {
    "wireless_headphones": ["headphones", "Earbuds"],
    "bluetooth_speakers": ["Bluetooth_Speakers", "audiophile"],
    "smartphones": ["Smartphones", "Android"],
    "smartwatches": ["smartwatch", "GalaxyWatch"],
    "power_banks": ["batteries", "UsbCHardware"],
    "kitchen_appliances": ["Cooking", "KitchenConfidential"],
    "finance_apps": ["personalfinance", "budget"],
    "health_fitness_apps": ["fitness", "loseit"],
    "productivity_apps": ["productivity", "todoist"],
    "education_apps": ["languagelearning", "GetStudying"],
}

# selection quotas / thresholds
TARGET_PRODUCTS_PER_CATEGORY = 150     # aim; fewer is acceptable (>= 60 workable)
MIN_RATING_COUNT_PHYSICAL = 50         # enough public ratings to trust popularity
MAX_REVIEWS_KEPT_PER_PRODUCT = 400     # streaming cap; cleaned down later
TARGET_APPS_PER_CATEGORY = 130
MIN_APP_INSTALLS = 50_000
MIN_APP_RATINGS = 500
REVIEWS_PER_APP = 400


# nouns that mark a product as an ACCESSORY when they appear in the title BEFORE
# the first category keyword ("BOVKE Speaker Case ... Bluetooth Speaker" = case;
# "JBL ... Bluetooth Speaker Bundle with Hardshell Case" = real speaker + bundle)
ACCESSORY_NOUNS = ["case", "cover", "sleeve", "pouch", "skin", "protector",
                   "band", "strap", "mount", "holder", "stand", "cable",
                   "charger", "adapter", "bracket", "sticker", "decal"]


def match_category(title: str, category: str) -> bool:
    t = " " + title.lower() + " "
    rules = PHYSICAL_RULES[category]
    first_kw = min((t.find(k) for k in rules["include"] if k in t), default=-1)
    if first_kw < 0:
        return False
    if any(k in t for k in rules["exclude"]):
        return False
    for noun in ACCESSORY_NOUNS:
        pos = t.find(f" {noun}")
        if 0 <= pos < first_kw:
            return False
    return True


def categorize_title(title: str, source_file: str) -> str | None:
    """First matching category whose AMAZON_SOURCE is source_file, else None."""
    for cat, src in AMAZON_SOURCE.items():
        if src == source_file and match_category(title, cat):
            return cat
    return None
