"""
Mistri AI Cost Estimator - Enhanced v2
Hybrid Engine: Domain NLP + Scikit-Learn RandomForest + Hinglish Customer Explanations
Features: multi-keyword scoring, parts/labor breakdown, confidence levels, follow-up questions
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import re
import os
import pickle
from pathlib import Path
from db.database import get_db
from middleware.auth import get_current_user, require_role

router = APIRouter(prefix="/api/ai", tags=["ai"])

# ----------------------------------------------------
# 1. Load Trained Scikit-Learn Model
# ----------------------------------------------------
ML_BUNDLE = None
model_paths = [
    Path(__file__).parent.parent / "mistri_cost_model.pkl",
    Path(__file__).parent.parent.parent / "ai_model" / "mistri_cost_model.pkl",
    Path(__file__).parent.parent.parent / "mistri_cost_model.pkl"
]
for p in model_paths:
    if p.exists():
        try:
            with open(p, "rb") as f:
                ML_BUNDLE = pickle.load(f)
            break
        except Exception:
            pass

# ----------------------------------------------------
# 2. Comprehensive Hindi & Hinglish Normalizer
# ----------------------------------------------------
HINGLISH_MAP = [
    # Water / pump (specific phrases first)
    (r"\b(pani nahi aa raha|paani nahi aa raha|pani nahi|paani nahi|dry|sukha|pani nahi phenk|choo raha|tapak|leak|paani kam|pressure nahi|water nahi)\b", "pump water not circulating dry leaking low pressure"),
    (r"\b(पानी नहीं आ रहा|पानी नहीं|सूखा|लीक|टपक)\b", "pump water not circulating dry leaking"),
    # Cooling issues (specific phrases first)
    (r"\b(thanda nahi|cooling nahi|thandi nahi aati|garm hawa|hot air|cool nahi|anda|sar nahi|cooling kam|cooling problem)\b", "no cooling warm air pads pump water"),
    (r"\b(ठंडा नहीं|कूलिंग नहीं|गर्म हवा)\b", "no cooling warm air pads pump"),
    # Heating issues (geyser)
    (r"\b(garam pani nahi|thanda pani|pani garam nahi|hot water nahi|heat nahi|garam nahi ho raha|heating nahi)\b", "heating element not heating cold water"),
    (r"\b(गर्म पानी नहीं|ठंडा पानी|हीटिंग नहीं)\b", "heating element not heating cold water"),
    # Slow / stuck (Fan/Motor)
    (r"\b(dheema|dhire|dheere|slow|ghoom nahi|ghoomta nahi|stuck|jaam|ruk ruk|atak|halka|bahut slow|bohot dheema|ghoom nahi raha|ghoom nahi rahi|low speed|speed nahi)\b", "slow capacitor humming stuck low speed"),
    (r"\b(धीमा|धीरे|घूम नहीं रहा|जाम|अटक|धीमी गति)\b", "slow capacitor humming stuck"),
    # Burning / smell / smoke
    (r"\b(dhua|dhuan|dhuaan|jal|jala|jal gaya|jalke|badboo|garam|tatta|garmi|overheating|phat gaya|phat gayi|phata|smoke|smell|boo|jal raha|jal rahi)\b", "burnt smoke smell overheating winding"),
    (r"\b(धुआं|जल गया|बदबू|गर्म|जल रहा|धुआ)\b", "burnt smoke smell overheating winding"),
    # Noise / vibration
    (r"\b(aawaz|awaz|aawaze|shor|khat khat|gar gar|ghur ghur|screech|khatkhat|tiktik|tiktak|khadakta|khadakti|kharr|kharr kharr|jhankar|takar)\b", "noise bearing vibration grinding"),
    (r"\b(आवाज|शोर|खट खट|घुर घुर|कड़कड़|झनझन)\b", "noise bearing vibration grinding"),
    # Starting / power issues
    (r"\b(chalu nahi|on nahi|start nahi|band ho gaya|nahi chalta|nahi chalti|chal nahi raha|chal nahi rahi|dead|khatam|power nahi|kaam nahi karta|kaam nahi karti)\b", "not starting dead no power stopped"),
    (r"\b(चालू नहीं|बंद|स्टार्ट नहीं|शुरू नहीं|नहीं चलता|काम नहीं करता)\b", "not starting dead no power stopped"),
    # Sparks / tripping
    (r"\b(trip|mcb|current|chingari|spark|short|short circuit|bijli|shock|checkmat|tripping|jhadak)\b", "tripping short circuit wiring spark"),
    (r"\b(चिंगारी|करंट|ट्रिप|शॉर्ट सर्किट|बिजली झटका)\b", "tripping short circuit wiring spark"),
    # Screen / display
    (r"\b(screen|display|touch|glass|broken screen|toota hua screen|display broken|lines on screen|screen black|kala screen)\b", "screen display touch glass broken"),
    # Battery / charging
    (r"\b(battery|charging nahi|charge nahi|battery drain|backup nahi|fast drain|jaldi khatam)\b", "battery draining charging slow"),
    # Leaking / dripping
    (r"\b(tapakna|tapak|leak|drip|choo raha|ooze|paani tapak|leaking water)\b", "leaking dripping water"),
]

def normalize_symptoms(text: str) -> str:
    """Normalize Hindi/Hinglish text to canonical diagnostic keywords."""
    normalized = text.lower().strip()
    for pattern, replacement in HINGLISH_MAP:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE | re.UNICODE)
    return normalized

# ----------------------------------------------------
# 3. Domain Knowledge Base — Parts + Labor Separated
# ----------------------------------------------------
REPAIR_DB = {
    "Fan": {
        "capacitor": {
            "keywords": ["capacitor", "slow", "hum", "humming", "starts slow", "not starting", "low speed", "stuck"],
            "parts_cost": (80, 250), "labor_cost": (100, 200), "time": (0.5, 1),
            "part": "Capacitor", "diagnostic": "Weak or failed starting/running capacitor",
            "hinglish": "Fan ki capacitor kharab ho sakti hai. Capacitor hi fan ko chalu karne mein madad karta hai. Isko replace karna padega."
        },
        "winding": {
            "keywords": ["winding", "coil", "burnt", "burn", "smell", "smoke", "overheating", "dead", "not starting dead", "jal"],
            "parts_cost": (300, 900), "labor_cost": (200, 400), "time": (2, 6),
            "part": "Motor Winding", "diagnostic": "Burnt motor stator/rotor winding",
            "hinglish": "Fan ki motor ki winding jal gayi lag rahi hai. Motor ke andar ke copper coil ko rewind karna padega jo ek bade kaam ka kaam hai."
        },
        "blade": {
            "keywords": ["blade", "vibration", "wobble", "bent"],
            "parts_cost": (120, 400), "labor_cost": (100, 200), "time": (0.5, 1.5),
            "part": "Fan Blade", "diagnostic": "Imbalanced or deformed fan blades causing vibration",
            "hinglish": "Fan ke blade tede ho gaye hain ya unka balance bigad gaya hai. Blade badalne se problem solve ho sakti hai."
        },
        "regulator": {
            "keywords": ["regulator", "speed control", "stuck speed", "speed nahi"],
            "parts_cost": (150, 500), "labor_cost": (100, 200), "time": (0.5, 2),
            "part": "Regulator", "diagnostic": "Faulty electrical/electronic speed controller",
            "hinglish": "Fan ka speed regulator (jo speed control karta hai) kharab ho gaya hai. Isko replace karna hoga."
        },
        "bearing": {
            "keywords": ["bearing", "grinding", "screeching", "noise", "rough", "khat khat", "kharr"],
            "parts_cost": (150, 500), "labor_cost": (150, 300), "time": (1, 3),
            "part": "Bearing", "diagnostic": "Worn ball bearings requiring replacement and lubrication",
            "hinglish": "Fan ki bearing ghas gayi hai jisse khat khat ya screech ki aawaz aa rahi hai. Bearing badalne se aawaz band ho jayegi."
        },
        "switch": {
            "keywords": ["switch", "button", "not turning on", "power switch"],
            "parts_cost": (50, 200), "labor_cost": (80, 150), "time": (0.5, 1),
            "part": "Switch", "diagnostic": "Defective fan switch",
            "hinglish": "Fan ka switch kharab ho gaya hai. Switch replace karna ek simple aur sasta kaam hai."
        },
    },
    "Cooler": {
        "motor": {
            "keywords": ["cooler motor", "fan not spinning", "motor stopped", "motor dead", "motor noise", "motor jal"],
            "parts_cost": (400, 1400), "labor_cost": (200, 400), "time": (2, 5),
            "part": "Cooler Motor", "diagnostic": "Internal motor shaft seizure or burnt coils",
            "hinglish": "Cooler ka main motor kharab ho gaya hai. Motor ya toh jal gayi ya jam gayi hai. Motor replace ya rewind karna padega."
        },
        "pump": {
            "keywords": ["pump", "water pump", "water not circulating", "dry", "no water", "pani nahi", "paani", "cooling nahi", "water"],
            "parts_cost": (250, 900), "labor_cost": (150, 300), "time": (1, 3),
            "part": "Water Pump", "diagnostic": "Submersible pump impeller failure or motor burnout",
            "hinglish": "Cooler ka water pump kharab hai jis wajah se pani pads tak nahi pahunch raha aur thandi hawa nahi aa rahi. Pump badal dene se cooling sahi ho jayegi."
        },
        "pads": {
            "keywords": ["pads", "cooling pads", "honeycomb", "dirty pads", "warm air", "no cooling warm air"],
            "parts_cost": (200, 700), "labor_cost": (100, 200), "time": (1, 2),
            "part": "Cooling Pads", "diagnostic": "Clogged or deteriorated cooling pads",
            "hinglish": "Cooler ke pads (cooling pads ya honeycomb) gande ya kharab ho gaye hain. Pads saaf karne ya badle se cooling kaafi improve ho jayegi."
        },
        "water_level": {
            "keywords": ["water level", "sensor", "float", "overflow", "leaking", "tapak"],
            "parts_cost": (100, 400), "labor_cost": (100, 200), "time": (0.5, 1.5),
            "part": "Float Valve", "diagnostic": "Faulty float valve or tank leak",
            "hinglish": "Cooler ki water tank se paani leak ho raha hai ya float valve kharab hai. Yeh ek chhoti si repair hai."
        },
    },
    "Mixer/Grinder": {
        "motor": {
            "keywords": ["motor", "dead", "burnt smell", "no power", "stopped working", "not starting dead no power"],
            "parts_cost": (350, 1200), "labor_cost": (200, 400), "time": (2, 5),
            "part": "Motor", "diagnostic": "Motor burnout due to overloading or voltage fluctuation",
            "hinglish": "Mixer ki motor jal gayi lag rahi hai. Zyada load dene se ya voltage problem se motor kharab hoti hai. Motor replace ya rewind karni padegi."
        },
        "carbon_brushes": {
            "keywords": ["brushes", "carbon brushes", "sparking", "spark", "arcing", "tripping short circuit wiring spark"],
            "parts_cost": (100, 400), "labor_cost": (100, 200), "time": (0.5, 2),
            "part": "Carbon Brushes", "diagnostic": "Worn carbon brushes causing sparking",
            "hinglish": "Mixer ke carbon brushes ghis gaye hain jis wajah se sparking ho rahi hai. Brushes badlna ek chhota aur sasta kaam hai."
        },
        "jar": {
            "keywords": ["jar", "blade jar", "jar cracked", "lid", "seal", "leaking"],
            "parts_cost": (200, 700), "labor_cost": (80, 150), "time": (0.5, 1),
            "part": "Jar Assembly", "diagnostic": "Leaking jar or damaged blade assembly",
            "hinglish": "Mixer ka jar ya toh toot gaya hai ya uski sealing kharab ho gayi hai. Jar ya bushing badlna padega."
        },
        "coupler": {
            "keywords": ["coupler", "coupling", "rattling", "blade not rotating"],
            "parts_cost": (50, 200), "labor_cost": (80, 150), "time": (0.5, 1),
            "part": "Coupler", "diagnostic": "Stripped drive coupler",
            "hinglish": "Mixer ka coupler (jo jar aur motor ko connect karta hai) toot gaya hai. Yeh bahut sasti aur aasaan repair hai."
        },
    },
    "Motor": {
        "winding": {
            "keywords": ["winding", "burnt", "burn", "smoke", "smell", "short circuit", "dead", "not starting dead"],
            "parts_cost": (500, 3000), "labor_cost": (400, 1200), "time": (4, 12),
            "part": "Motor Winding", "diagnostic": "Phase winding insulation breakdown requiring full rewinding",
            "hinglish": "Motor ki winding (copper coil) jal gayi hai. Yeh ek bada kaam hai jisme motor ko puri tarah se rewind karna padega."
        },
        "bearing": {
            "keywords": ["bearing", "noise", "grinding", "vibration", "seized", "noise bearing vibration"],
            "parts_cost": (300, 1200), "labor_cost": (200, 500), "time": (2, 6),
            "part": "Bearing", "diagnostic": "Severe bearing wear and mechanical friction",
            "hinglish": "Motor ki bearing ghis gayi hai jis wajah se vibration aur aawaz aa rahi hai. Bearing badalne se motor smooth chalegi."
        },
        "capacitor": {
            "keywords": ["capacitor", "not starting", "hum", "humming", "slow start"],
            "parts_cost": (150, 600), "labor_cost": (150, 300), "time": (0.5, 2),
            "part": "Capacitor", "diagnostic": "Capacitor failure causing motor not to start",
            "hinglish": "Motor ki capacitor kharab ho gayi hai jis wajah se motor start nahi ho rahi ya humming aa rahi hai."
        },
    },
    "Geyser": {
        "heating_element": {
            "keywords": ["heating element", "element", "not heating", "no hot water", "cold water", "heating element not heating cold water"],
            "parts_cost": (400, 1400), "labor_cost": (200, 400), "time": (1, 3),
            "part": "Heating Element", "diagnostic": "Corroded or scaled heating element",
            "hinglish": "Geyser ka heating element (jo paani garam karta hai) kharab ho gaya hai ya uspe scale jam gayi hai. Ise replace karna padega."
        },
        "thermostat": {
            "keywords": ["thermostat", "temperature", "too hot", "not cutting off", "tripping"],
            "parts_cost": (300, 900), "labor_cost": (150, 300), "time": (1, 2),
            "part": "Thermostat", "diagnostic": "Thermostat malfunction",
            "hinglish": "Geyser ka thermostat kharab ho gaya hai. Thermostat hi temperature control karta hai — ise replace karna padega."
        },
        "pressure_valve": {
            "keywords": ["pressure valve", "prv", "leaking", "dripping", "tapak"],
            "parts_cost": (200, 600), "labor_cost": (150, 300), "time": (0.5, 2),
            "part": "Pressure Relief Valve", "diagnostic": "Defective safety pressure valve causing dripping",
            "hinglish": "Geyser ka pressure valve kharab ho gaya hai jis wajah se paani tapak raha hai. Valve replace karna ek chhota kaam hai."
        },
        "wiring": {
            "keywords": ["wiring", "wire", "tripping", "short circuit", "mcb", "tripping short circuit"],
            "parts_cost": (200, 800), "labor_cost": (200, 400), "time": (1, 3),
            "part": "Internal Wiring", "diagnostic": "Faulty internal wiring causing tripping or shock risk",
            "hinglish": "Geyser ki internal wiring mein problem hai jis wajah se MCB trip ho raha hai ya shock ka darr hai. Wiring check aur replace karni padegi — yeh urgent hai."
        },
    },
    "Pump": {
        "motor": {
            "keywords": ["motor", "dead", "no power", "burnt", "overheating", "not starting dead"],
            "parts_cost": (600, 2800), "labor_cost": (300, 700), "time": (2, 6),
            "part": "Pump Motor", "diagnostic": "Pump motor winding burnout",
            "hinglish": "Pump ki motor jal gayi hai. Motor ya toh rewind hogi ya replace hogi."
        },
        "impeller": {
            "keywords": ["impeller", "no suction", "low pressure", "reduced output", "pani kam"],
            "parts_cost": (350, 1400), "labor_cost": (200, 400), "time": (2, 5),
            "part": "Impeller", "diagnostic": "Worn impeller causing low water pressure",
            "hinglish": "Pump ka impeller ghis gaya hai jis wajah se paani ka pressure kam ho gaya hai. Impeller badlna padega."
        },
        "seal": {
            "keywords": ["seal", "mechanical seal", "leaking", "dripping from pump", "tapak"],
            "parts_cost": (300, 900), "labor_cost": (200, 400), "time": (1, 4),
            "part": "Mechanical Seal", "diagnostic": "Mechanical seal failure causing water leakage",
            "hinglish": "Pump ki mechanical seal kharab ho gayi hai jis wajah se paani bahaar tapak raha hai."
        },
    },
    "Mobile": {
        "screen": {
            "keywords": ["screen", "display", "touch", "glass broken", "screen display touch", "toota"],
            "parts_cost": (1200, 4500), "labor_cost": (300, 600), "time": (1, 3),
            "part": "Display/Touch", "diagnostic": "Cracked display or digitizer failure",
            "hinglish": "Mobile ki screen toot gayi hai ya touch kaam nahi kar raha. Display unit replace karni padegi."
        },
        "battery": {
            "keywords": ["battery", "draining", "backup", "charging slow", "battery draining charging"],
            "parts_cost": (500, 1500), "labor_cost": (150, 300), "time": (0.5, 1.5),
            "part": "Battery", "diagnostic": "Degraded battery health",
            "hinglish": "Mobile ki battery kharab ho gayi hai — backup bahut kam ho gayi hai. Battery replace karna hoga."
        },
        "charging_port": {
            "keywords": ["port", "pin", "loose pin", "not charging", "charging nahi"],
            "parts_cost": (300, 1200), "labor_cost": (200, 400), "time": (0.5, 1.5),
            "part": "Charging Port", "diagnostic": "Damaged charging connector",
            "hinglish": "Mobile ka charging port kharab ho gaya hai. Port replace karne se charging sahi ho jayegi."
        },
    },
    "Laptop": {
        "screen": {
            "keywords": ["screen", "display", "lines on screen", "flicker", "blank", "screen display touch"],
            "parts_cost": (2500, 8000), "labor_cost": (400, 800), "time": (2, 4),
            "part": "Laptop Screen", "diagnostic": "Display panel or cable failure",
            "hinglish": "Laptop ki screen kharab ho gayi hai — lines aa rahi hain ya blank hai. Screen replace karni padegi."
        },
        "battery": {
            "keywords": ["battery", "battery dead", "plugged in not charging", "battery draining"],
            "parts_cost": (1500, 4000), "labor_cost": (200, 400), "time": (1, 2),
            "part": "Laptop Battery", "diagnostic": "Battery cell exhaustion",
            "hinglish": "Laptop ki battery khatam ho gayi hai. Original battery replace karne se laptop hours chalega."
        },
    },
    "Other": {
        "general": {
            "keywords": ["*"],
            "parts_cost": (200, 1500), "labor_cost": (150, 500), "time": (1, 4),
            "part": "General Repair", "diagnostic": "General electrical component diagnosis",
            "hinglish": "Device mein koi electrical fault aa gayi hai. Technician inspection ke baad exact problem pata chalegi."
        },
    }
}

# Follow-up questions per device
FOLLOW_UP_QUESTIONS = {
    "Fan": [
        "Fan bilkul start nahi ho raha ya ghoom raha hai lekin hawa nahi aa rahi?",
        "Koi aawaz aa rahi hai (khat khat, ghur ghur, screech)?",
        "Fan chalte chalte ruk jaata hai ya ek baar bhi start nahi hota?",
        "Koi burning smell (jalne ki boo) aa rahi hai?"
    ],
    "Cooler": [
        "Cooler ka motor chal raha hai ya bilkul band hai?",
        "Cooling nahi aa rahi ya paani proper nahi aa raha pads par?",
        "Koi ajeeb aawaz aa rahi hai?",
        "Pani tank mein hai ya sukha hai?"
    ],
    "Mixer/Grinder": [
        "Mixer bilkul start nahi hota ya start hota hai phir ruk jaata hai?",
        "Chalate waqt spark (chingari) dikhti hai?",
        "Jalne ki boo aati hai?",
        "Kon sa speed setting (1, 2, 3) mein problem hai?"
    ],
    "Motor": [
        "Motor bilkul start nahi hoti ya chalti hai lekin zyada load nahi le rahi?",
        "Koi specific aawaz aa rahi hai (vibration, grinding, humming)?",
        "Motor kab se use mein hai aur kitna load rehta hai?",
        "Koi burning smell aa rahi hai?"
    ],
    "Geyser": [
        "Paani garam nahi ho raha ya paani bahut zyada garam hota hai?",
        "MCB bar bar trip ho raha hai?",
        "Paani tapak raha hai kahiin se?",
        "Geyser kitne time se use mein hai?"
    ],
    "Pump": [
        "Pump start ho rahi hai ya motor bilkul band hai?",
        "Paani aa raha hai lekin pressure kam hai ya bilkul nahi aa raha?",
        "Koi paani tapakna ya leak dikhta hai?",
        "Pump submersible hai ya monoblock (surface mount)?"
    ],
    "Mobile": [
        "Screen toot gayi hai ya sirf display nahi aa raha?",
        "Charging hoti hai ya charging port mein problem hai?",
        "Phone on hota hai ya bilkul dead hai?",
        "Koi baar gira tha ya paani gaya tha?"
    ],
    "Other": [
        "Device ka model number kya hai?",
        "Problem kab se aa rahi hai?",
        "Koi specific symptom (aawaz, smell, spark) dekha kya?",
        "Pehle koi repair hui hai is device mein?"
    ]
}

def estimate_cost(device_type: str, problem: str, brand_tier: str = "mid") -> dict:
    """
    Improved Hybrid Estimator:
    1. Normalizes Hindi/Hinglish to canonical keywords
    2. Weighted multi-keyword matching for confidence
    3. Uses separate parts + labor cost ranges
    4. Returns Hinglish explanation + confidence level + follow-up questions
    """
    normalized = normalize_symptoms(problem)
    text_lower = problem.lower() + " " + normalized

    device_db = REPAIR_DB.get(device_type, REPAIR_DB["Other"])

    best_match = None
    best_score = 0
    match_count = 0

    for repair_type, data in device_db.items():
        if data["keywords"] == ["*"]:
            continue
        score = 0
        count = 0
        for kw in data["keywords"]:
            if kw in text_lower:
                score += 2 if len(kw.split()) > 1 else 1  # Multi-word match = more weight
                count += 1
        if score > best_score:
            best_score = score
            best_match = data
            match_count = count

    # Fallback to first entry
    if not best_match:
        first_key = list(device_db.keys())[0]
        best_match = device_db[first_key]
        match_count = 0
        best_score = 0

    # Confidence calculation
    if best_score >= 4 or match_count >= 3:
        confidence_level = "High"
        confidence_pct = min(95, 75 + best_score * 3)
    elif best_score >= 2 or match_count >= 1:
        confidence_level = "Medium"
        confidence_pct = min(74, 50 + best_score * 5)
    else:
        confidence_level = "Low"
        confidence_pct = 35

    # Adjust cost for brand tier
    tier_multiplier = {"budget": 0.8, "mid": 1.0, "premium": 1.4}.get(brand_tier, 1.0)
    parts_min = int(best_match["parts_cost"][0] * tier_multiplier)
    parts_max = int(best_match["parts_cost"][1] * tier_multiplier)
    labor_min = best_match["labor_cost"][0]
    labor_max = best_match["labor_cost"][1]
    total_min = parts_min + labor_min
    total_max = parts_max + labor_max

    # ML model adjustment
    matched_key = None
    for k, v in device_db.items():
        if v is best_match:
            matched_key = k
            break
    matched_key = matched_key or "general"

    ml_cost = None
    if ML_BUNDLE:
        try:
            d_enc = ML_BUNDLE["device_enc"].transform([device_type])[0]
            i_enc = ML_BUNDLE["issue_enc"].transform([matched_key])[0]
            t_enc = ML_BUNDLE["tier_enc"].transform([brand_tier])[0]
            raw = ML_BUNDLE["model"].predict([[d_enc, i_enc, t_enc]])[0]
            ml_cost = round(float(raw), -1)
        except Exception:
            ml_cost = None

    if ml_cost:
        total_min = int(min(total_min, ml_cost * 0.85))
        total_max = int(max(total_max, ml_cost * 1.15))

    # English explanation
    eng_explanation = (
        f"Based on your description of '{device_type}' with symptoms suggesting '{best_match['diagnostic']}', "
        f"the likely repair involves {best_match['part']}. "
        f"Parts typically cost ₹{parts_min:,}–₹{parts_max:,} and labor ₹{labor_min}–₹{labor_max}."
    )

    # Hinglish explanation
    hinglish_exp = best_match.get("hinglish", "Device mein koi electrical problem hai jo technician inspection ke baad pata chalegi.")

    # Follow-up questions for Low confidence
    follow_up = []
    if confidence_level == "Low":
        follow_up = FOLLOW_UP_QUESTIONS.get(device_type, FOLLOW_UP_QUESTIONS["Other"])

    return {
        "device_type": device_type,
        "repair_category": matched_key.replace("_", " ").title(),
        "symptom_detected": best_match["diagnostic"],
        "primary_part": best_match["part"],
        "parts_cost_min": parts_min,
        "parts_cost_max": parts_max,
        "labor_cost_min": labor_min,
        "labor_cost_max": labor_max,
        "estimated_cost_min": total_min,
        "estimated_cost_max": total_max,
        "ml_predicted_cost": ml_cost,
        "estimated_time_min_hours": best_match["time"][0],
        "estimated_time_max_hours": best_match["time"][1],
        "confidence": confidence_pct,
        "confidence_level": confidence_level,
        "explanation": eng_explanation,
        "hinglish_explanation": hinglish_exp,
        "follow_up_questions": follow_up,
        "model_used": "Mistri NLP v2 + RandomForest Hybrid",
        "currency": "INR",
        "disclaimer": "Ye sirf ek AI-based prarambhik anuman hai. Final cost aur problem technician ke physical inspection ke baad confirm hogi."
    }


class EstimateRequest(BaseModel):
    device_type: str
    problem_description: str
    brand_tier: Optional[str] = "mid"

@router.post("/estimate")
def get_estimate(req: EstimateRequest):
    """Enhanced AI-based repair cost estimation with Hinglish explanation and confidence levels."""
    supported = ["Fan", "Cooler", "Mixer/Grinder", "Motor", "Geyser", "Pump", "Mobile", "Laptop", "TV", "Other"]
    device_type = req.device_type if req.device_type in supported else "Other"
    if len(req.problem_description.strip()) < 5:
        raise HTTPException(400, "Kripaya thodi zyada detail mein problem batayein (kam se kam 5 words).")
    return estimate_cost(device_type, req.problem_description, req.brand_tier or "mid")

@router.get("/repair-tips/{device_type}")
def get_repair_tips(device_type: str):
    """Get common repair types and average costs for a device type."""
    device_db = REPAIR_DB.get(device_type, REPAIR_DB["Other"])
    tips = []
    for repair_type, data in device_db.items():
        if data["keywords"] != ["*"]:
            tips.append({
                "repair_type": repair_type.replace("_", " ").title(),
                "part": data.get("part"),
                "diagnostic": data.get("diagnostic", ""),
                "parts_cost": f"₹{data['parts_cost'][0]:,} – ₹{data['parts_cost'][1]:,}",
                "labor_cost": f"₹{data['labor_cost'][0]:,} – ₹{data['labor_cost'][1]:,}",
                "avg_cost": f"₹{data['parts_cost'][0]+data['labor_cost'][0]:,} – ₹{data['parts_cost'][1]+data['labor_cost'][1]:,}",
                "avg_time": f"{data['time'][0]}–{data['time'][1]} ghante"
            })
    return tips

@router.get("/follow-up-questions/{device_type}")
def get_follow_up_questions(device_type: str):
    """Get diagnostic follow-up questions for a device type."""
    return {"device_type": device_type, "questions": FOLLOW_UP_QUESTIONS.get(device_type, FOLLOW_UP_QUESTIONS["Other"])}

# ----------------------------------------------------
# 4. AI Technician Recommendation
# ----------------------------------------------------
@router.get("/recommend-technician/{job_id}")
def recommend_technician(job_id: int, current_user: dict = Depends(require_role("admin"))):
    conn = get_db()
    job = conn.execute("""
        SELECT rj.*, d.device_type, d.brand, d.model
        FROM repair_jobs rj
        JOIN devices d ON rj.device_id = d.id
        WHERE rj.id = ?
    """, (job_id,)).fetchone()
    if not job:
        conn.close()
        raise HTTPException(404, "Repair job not found")
    device_type = job["device_type"]
    techs = conn.execute("SELECT id, name, email, phone FROM users WHERE role='staff'").fetchall()
    if not techs:
        conn.close()
        raise HTTPException(404, "No technicians available.")
    scored = []
    for t in techs:
        tid = t["id"]
        similar = conn.execute("""SELECT COUNT(*) FROM repair_jobs rj JOIN devices d ON rj.device_id=d.id
            WHERE rj.technician_id=? AND d.device_type=? AND rj.status IN ('Completed','Delivered')""", (tid, device_type)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM repair_jobs WHERE technician_id=? AND status IN ('Completed','Delivered')", (tid,)).fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM repair_jobs WHERE technician_id=? AND status NOT IN ('Completed','Delivered','Cancelled','Rejected')", (tid,)).fetchone()[0]
        rating_row = conn.execute("SELECT AVG(COALESCE(technician_rating, rating)) FROM feedback WHERE technician_id=?", (tid,)).fetchone()[0]
        rating = float(rating_row) if rating_row else 4.8
        score = (similar * 6.0) + (total * 1.5) + (rating * 4.0) - (active * 5.0)
        scored.append({"technician_id": tid, "name": t["name"], "email": t["email"], "phone": t["phone"],
                       "similar_completed": similar, "total_completed": total, "active_workload": active,
                       "rating": round(rating, 1), "score": round(score, 1)})
    conn.close()
    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0]
    max_s = max(t["score"] for t in scored) if scored else 1
    recs = []
    for t in scored:
        ns = int(70 + (t["score"] / max(max_s, 1)) * 28) if max_s > 0 else 85
        ns = min(99, max(65, ns))
        recs.append({"technician_id": t["technician_id"], "name": t["name"], "email": t["email"],
                     "match_score": ns, "completed_same_device": t["similar_completed"],
                     "total_completed": t["total_completed"], "current_workload": t["active_workload"],
                     "avg_rating": t["rating"],
                     "rationale": f"{t['similar_completed']} similar repairs, {t['rating']}★ rating, {t['active_workload']} active jobs."})
    return {"repair_id": job["repair_id"], "device_type": device_type,
            "recommended_technician": best, "recommendations": recs,
            "reason": f"{best['name']} has {best['similar_completed']} similar {device_type} repairs with {best['rating']}★ rating."}
