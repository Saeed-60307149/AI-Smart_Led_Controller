import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib
import sys
import os

if not os.path.exists("../data"):
    os.makedirs("../data")

print("=" * 50)
print("  AI LED MODEL TRAINING (ThingsBoard Version)")
print("=" * 50)

# ========== 1. LOAD DATA ==========
try:
    df = pd.read_csv("../data/thingsboard_history.csv")
    print(f"\n✓ Data loaded: {len(df)} rows from ThingsBoard export")
except FileNotFoundError:
    print("\n✗ ERROR: thingsboard_history.csv not found!")
    print("  Run export_thingsboard.py first.")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ ERROR loading CSV: {e}")
    sys.exit(1)

# ========== 2. INITIAL DATA INSPECTION ==========
print(f"\nColumns found: {list(df.columns)}")
print(f"Data types:\n{df.dtypes}")
print(f"\nFirst few rows:")
print(df.head())

# ========== 3. DATA CLEANING ==========
print("\n" + "-" * 50)
print("DATA CLEANING")
print("-" * 50)

# Remove timestamp column if exists
if 'ts' in df.columns or 'Unnamed: 0' in df.columns:
    df = df.drop(columns=[col for col in ['ts', 'Unnamed: 0'] if col in df.columns])
    print("✓ Removed timestamp column(s)")

# Check for required columns
required_cols = ['ldr', 'motion', 'led']
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    print(f"✗ ERROR: Missing columns: {missing_cols}")
    sys.exit(1)

# Keep only required columns
df = df[required_cols].copy()

# Handle missing values
initial_rows = len(df)
missing_before = df.isnull().sum().sum()
if missing_before > 0:
    print(f"\n⚠ Found {missing_before} missing values")
    print(df.isnull().sum())
    df = df.dropna()
    dropped = initial_rows - len(df)
    print(f"✓ Dropped {dropped} rows with missing values")

# Convert to numeric (if string)
for col in df.columns:
    df[col] = pd.to_numeric(df[col], errors='coerce')

df = df.dropna()

# Remove duplicates
duplicates = df.duplicated().sum()
if duplicates > 0:
    df = df.drop_duplicates()
    print(f"✓ Removed {duplicates} duplicate rows")

# ========== 4. VALIDATION ==========
print("\n" + "-" * 50)
print("DATA VALIDATION")
print("-" * 50)

print(f"\nLDR range: {df['ldr'].min():.0f} - {df['ldr'].max():.0f}")
print(f"Motion range: {df['motion'].min():.0f} - {df['motion'].max():.0f}")
print(f"LED range: {df['led'].min():.0f} - {df['led'].max():.0f}")

# Validate ranges
df = df[(df['ldr'] >= 0) & (df['ldr'] <= 4095)]
df = df[(df['motion'].isin([0, 1]))]
df = df[(df['led'] >= 0) & (df['led'] <= 255)]

if len(df) < 50:
    print(f"\n✗ ERROR: Only {len(df)} valid samples remaining!")
    print("  Collect more telemetry in ThingsBoard for training.")
    sys.exit(1)

print(f"\n✓ Clean dataset: {len(df)} valid samples")

# ========== 5. OUTLIER DETECTION ==========
print("\n" + "-" * 50)
print("OUTLIER DETECTION")
print("-" * 50)

Q1, Q3 = df['led'].quantile([0.25, 0.75])
IQR = Q3 - Q1
low, high = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR

outliers = df[(df['led'] < low) | (df['led'] > high)]
if len(outliers) > 0 and len(outliers) < len(df) * 0.1:
    df = df[(df['led'] >= low) & (df['led'] <= high)]
    print(f"✓ Removed {len(outliers)} LED outliers")
else:
    print("✓ No significant outliers detected")

# ========== 6. FEATURE STATISTICS ==========
print("\n" + "-" * 50)
print("FEATURE STATISTICS")
print("-" * 50)
print(df.describe())

for col in ['ldr', 'led']:
    if df[col].std() < 1:
        print(f"\n⚠ WARNING: {col} variance too low — model may not learn well.")

# ========== 7. TRAIN / TEST SPLIT ==========
X = df[['ldr', 'motion']].astype(float)
y = df['led'].astype(float)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
print(f"\n✓ Training: {len(X_train)} samples, Test: {len(X_test)} samples")

# ========== 8. TRAIN MODEL ==========
print("\n" + "-" * 50)
print("TRAINING MODEL")
print("-" * 50)

model = RandomForestRegressor(
    n_estimators=200,
    max_depth=10,
    min_samples_split=5,
    min_samples_leaf=2,
    random_state=42,
    n_jobs=-1
)
model.fit(X_train, y_train)
print("✓ Training complete")

# ========== 9. EVALUATION ==========
y_pred_train = np.clip(model.predict(X_train), 0, 255)
y_pred_test = np.clip(model.predict(X_test), 0, 255)

train_mae = mean_absolute_error(y_train, y_pred_train)
test_mae = mean_absolute_error(y_test, y_pred_test)
train_r2 = r2_score(y_train, y_pred_train)
test_r2 = r2_score(y_test, y_pred_test)

print(f"\nTrain → MAE: {train_mae:.2f}, R²: {train_r2:.3f}")
print(f"Test  → MAE: {test_mae:.2f}, R²: {test_r2:.3f}")

print(f"\nFeature Importance:")
print(f"  LDR: {model.feature_importances_[0]:.3f}")
print(f"  Motion: {model.feature_importances_[1]:.3f}")

# ========== 10. SAVE MODEL ==========
try:
    joblib.dump(model, "led_predictor.pkl")
    print("\n" + "=" * 50)
    print("✓ MODEL SAVED: led_predictor.pkl")
    print("=" * 50)
except Exception as e:
    print(f"✗ ERROR saving model: {e}")
    sys.exit(1)

# ========== 11. SAMPLE PREDICTIONS ==========
print("\nSample Predictions:")
print("-" * 50)
samples = [
    (100, 0, "Dark + No Motion"),
    (100, 1, "Dark + Motion"),
    (3000, 0, "Bright + No Motion"),
    (3000, 1, "Bright + Motion"),
    (1500, 1, "Medium + Motion")
]
for ldr, motion, desc in samples:
    pred = int(np.clip(model.predict([[ldr, motion]])[0], 0, 255))
    print(f"{desc:20s} → PWM: {pred:3d}")

print("\n✓ Ready for deployment!")