#!/usr/bin/env python3
"""
Mistri AI Reference Model
Python scikit-learn RandomForestRegressor for repair cost estimation
Trained across household appliances and electronics.
"""

import os
import json
import numpy as np
from pathlib import Path

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error
    import pickle
    print("✅ scikit-learn available")
except ImportError:
    print("❌ scikit-learn not installed. Run: pip3 install scikit-learn")
    exit(1)

# ---- Comprehensive Training Data ----
REPAIR_DATA = [
    # Fan
    ("Fan", "capacitor", "budget", 200),
    ("Fan", "capacitor", "mid", 300),
    ("Fan", "capacitor", "premium", 400),
    ("Fan", "winding", "budget", 500),
    ("Fan", "winding", "mid", 850),
    ("Fan", "winding", "premium", 1200),
    ("Fan", "blade", "budget", 250),
    ("Fan", "blade", "mid", 400),
    ("Fan", "blade", "premium", 600),
    ("Fan", "regulator", "budget", 250),
    ("Fan", "regulator", "mid", 450),
    ("Fan", "regulator", "premium", 700),
    ("Fan", "bearing", "budget", 350),
    ("Fan", "bearing", "mid", 550),
    ("Fan", "bearing", "premium", 800),
    ("Fan", "switch", "budget", 150),
    ("Fan", "switch", "mid", 250),
    ("Fan", "switch", "premium", 350),

    # Cooler
    ("Cooler", "motor", "budget", 750),
    ("Cooler", "motor", "mid", 1200),
    ("Cooler", "motor", "premium", 1800),
    ("Cooler", "pump", "budget", 450),
    ("Cooler", "pump", "mid", 800),
    ("Cooler", "pump", "premium", 1200),
    ("Cooler", "pads", "budget", 350),
    ("Cooler", "pads", "mid", 600),
    ("Cooler", "pads", "premium", 900),
    ("Cooler", "blade", "budget", 300),
    ("Cooler", "blade", "mid", 500),
    ("Cooler", "blade", "premium", 700),
    ("Cooler", "water_level", "budget", 250),
    ("Cooler", "water_level", "mid", 400),
    ("Cooler", "water_level", "premium", 600),

    # Mixer/Grinder
    ("Mixer/Grinder", "motor", "budget", 600),
    ("Mixer/Grinder", "motor", "mid", 1000),
    ("Mixer/Grinder", "motor", "premium", 1500),
    ("Mixer/Grinder", "carbon_brushes", "budget", 200),
    ("Mixer/Grinder", "carbon_brushes", "mid", 380),
    ("Mixer/Grinder", "carbon_brushes", "premium", 600),
    ("Mixer/Grinder", "jar", "budget", 350),
    ("Mixer/Grinder", "jar", "mid", 600),
    ("Mixer/Grinder", "jar", "premium", 900),
    ("Mixer/Grinder", "switch", "budget", 180),
    ("Mixer/Grinder", "switch", "mid", 300),
    ("Mixer/Grinder", "switch", "premium", 450),
    ("Mixer/Grinder", "coupler", "budget", 120),
    ("Mixer/Grinder", "coupler", "mid", 200),
    ("Mixer/Grinder", "coupler", "premium", 300),

    # Motor
    ("Motor", "winding", "budget", 1000),
    ("Motor", "winding", "mid", 2200),
    ("Motor", "winding", "premium", 4000),
    ("Motor", "bearing", "budget", 450),
    ("Motor", "bearing", "mid", 950),
    ("Motor", "bearing", "premium", 1500),
    ("Motor", "capacitor", "budget", 250),
    ("Motor", "capacitor", "mid", 500),
    ("Motor", "capacitor", "premium", 800),
    ("Motor", "shaft", "budget", 700),
    ("Motor", "shaft", "mid", 1500),
    ("Motor", "shaft", "premium", 2500),

    # Geyser
    ("Geyser", "heating_element", "budget", 700),
    ("Geyser", "heating_element", "mid", 1200),
    ("Geyser", "heating_element", "premium", 1800),
    ("Geyser", "thermostat", "budget", 450),
    ("Geyser", "thermostat", "mid", 800),
    ("Geyser", "thermostat", "premium", 1200),
    ("Geyser", "pressure_valve", "budget", 350),
    ("Geyser", "pressure_valve", "mid", 550),
    ("Geyser", "pressure_valve", "premium", 800),
    ("Geyser", "wiring", "budget", 350),
    ("Geyser", "wiring", "mid", 650),
    ("Geyser", "wiring", "premium", 1000),
    ("Geyser", "tank", "budget", 1800),
    ("Geyser", "tank", "mid", 3200),
    ("Geyser", "tank", "premium", 5000),

    # Pump
    ("Pump", "motor", "budget", 1000),
    ("Pump", "motor", "mid", 2200),
    ("Pump", "motor", "premium", 3500),
    ("Pump", "impeller", "budget", 600),
    ("Pump", "impeller", "mid", 1100),
    ("Pump", "impeller", "premium", 1800),
    ("Pump", "seal", "budget", 450),
    ("Pump", "seal", "mid", 800),
    ("Pump", "seal", "premium", 1200),
    ("Pump", "valve", "budget", 350),
    ("Pump", "valve", "mid", 600),
    ("Pump", "valve", "premium", 900),
    ("Pump", "capacitor", "budget", 250),
    ("Pump", "capacitor", "mid", 450),
    ("Pump", "capacitor", "premium", 700),

    # Mobile
    ("Mobile", "screen", "premium", 5000),
    ("Mobile", "screen", "mid", 3200),
    ("Mobile", "screen", "budget", 1800),
    ("Mobile", "battery", "premium", 1800),
    ("Mobile", "battery", "mid", 1100),
    ("Mobile", "battery", "budget", 700),
    ("Mobile", "motherboard", "premium", 10000),
    ("Mobile", "motherboard", "mid", 6000),
    ("Mobile", "motherboard", "budget", 3500),
    ("Mobile", "charging_port", "premium", 1400),
    ("Mobile", "charging_port", "mid", 900),
    ("Mobile", "charging_port", "budget", 500),

    # Laptop
    ("Laptop", "screen", "premium", 8500),
    ("Laptop", "screen", "mid", 5500),
    ("Laptop", "screen", "budget", 3500),
    ("Laptop", "battery", "premium", 4500),
    ("Laptop", "battery", "mid", 3000),
    ("Laptop", "battery", "budget", 2000),
    ("Laptop", "motherboard", "premium", 18000),
    ("Laptop", "motherboard", "mid", 10000),
    ("Laptop", "motherboard", "budget", 6000),

    # TV
    ("TV", "screen", "premium", 12000),
    ("TV", "screen", "mid", 7000),
    ("TV", "screen", "budget", 4000),
    ("TV", "power", "premium", 3500),
    ("TV", "power", "mid", 2200),
    ("TV", "power", "budget", 1500),

    # Other
    ("Other", "general", "budget", 400),
    ("Other", "general", "mid", 800),
    ("Other", "general", "premium", 1500),
]

# Add variance for training realism
np.random.seed(42)
X_raw, y = [], []
for row in REPAIR_DATA:
    for _ in range(8):  # Data augmentation
        device, issue, tier, base_cost = row
        X_raw.append([device, issue, tier])
        y.append(max(150, int(base_cost * np.random.uniform(0.85, 1.15))))

device_enc = LabelEncoder()
issue_enc = LabelEncoder()
tier_enc = LabelEncoder()

devices = [r[0] for r in X_raw]
issues = [r[1] for r in X_raw]
tiers = [r[2] for r in X_raw]

X = np.column_stack([
    device_enc.fit_transform(devices),
    issue_enc.fit_transform(issues),
    tier_enc.fit_transform(tiers)
])

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

model = RandomForestRegressor(n_estimators=100, random_state=42, max_depth=12)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
mae = mean_absolute_error(y_test, y_pred)
print(f"\n📊 Model Evaluation:")
print(f"   Mean Absolute Error: ₹{mae:.1f}")
print(f"   Total training samples: {len(X_train)}")

# Save model dictionary to multiple reachable locations
bundle = {
    "model": model,
    "device_enc": device_enc,
    "issue_enc": issue_enc,
    "tier_enc": tier_enc
}

save_dirs = [
    Path(__file__).parent,
    Path(__file__).parent.parent / "backend",
    Path(__file__).parent.parent
]

for d in save_dirs:
    dest = d / "mistri_cost_model.pkl"
    with open(dest, "wb") as f:
        pickle.dump(bundle, f)
    print(f"💾 Model saved to: {dest}")

def predict_cost(device_type, issue_category, brand_tier="mid"):
    """Predict repair cost using trained model with safe fallback."""
    try:
        d = device_enc.transform([device_type])[0]
        i = issue_enc.transform([issue_category])[0]
        t = tier_enc.transform([brand_tier])[0]
        pred = model.predict([[d, i, t]])[0]
        return round(float(pred), -1)
    except Exception:
        return None

print("\n🤖 Sample Predictions:")
test_samples = [
    ("Fan", "capacitor", "budget"),
    ("Fan", "winding", "mid"),
    ("Cooler", "motor", "mid"),
    ("Geyser", "heating_element", "premium"),
    ("Pump", "impeller", "mid"),
]
for d, i, t in test_samples:
    print(f"   {d} ({i}, {t}): ₹{predict_cost(d, i, t):.0f}")
