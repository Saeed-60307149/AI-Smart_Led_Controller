# ============================================================
# app.py  — Flask AI inference server for ESP32 + ThingsBoard
# ============================================================

from flask import Flask, request, jsonify
import joblib
import pandas as pd
import os
from flask_cors import CORS  # Install with: pip install flask-cors

app = Flask(__name__)
CORS(app)

MODEL_PATH = "led_predictor.pkl"
model = None

# ============================================================
# 1️⃣ Load model if available
# ============================================================
def load_model():
    global model
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
            print("✅ Model loaded successfully:", MODEL_PATH)
            return True
        except Exception as e:
            print("⚠️ Error loading model:", e)
            model = None
            return False
    else:
        print("❌ Model file not found yet.")
        return False


# ============================================================
# 2️⃣ Endpoint: Check if model exists
# ============================================================
@app.route("/status", methods=["GET"])
def status():
    """ESP32 uses this to check if model is ready."""
    if os.path.exists(MODEL_PATH):
        if model is None:
            load_model()
        return "ready", 200
    else:
        return "not_ready", 404


# ============================================================
# 3️⃣ Endpoint: Predict LED brightness
# ============================================================
@app.route("/predict", methods=["POST"])
def predict():
    """ESP32 sends LDR + motion readings here for prediction."""
    global model

    if model is None:
        if not load_model():
            return jsonify({"error": "Model not available"}), 404

    try:
        data = request.get_json()
        ldr = float(data.get("ldr", 0))
        motion = float(data.get("motion", 0))

        df = pd.DataFrame([[ldr, motion]], columns=["ldr", "motion"])
        pred = model.predict(df)[0]
        pred = max(0, min(255, int(pred)))  # Clamp 0–255

        print(f"📥 Input: LDR={ldr}, Motion={motion} → Predicted LED={pred}")

        return jsonify({"led": pred}), 200

    except Exception as e:
        print("⚠️ Prediction error:", e)
        return jsonify({"error": str(e)}), 500


# ============================================================
# 4️⃣ Root Endpoint (for quick check)
# ============================================================
@app.route("/", methods=["GET"])
def root():
    return jsonify({
        "service": "ESP32 AI LED Controller",
        "status": "running",
        "model_loaded": model is not None
    })


# ============================================================
# 5️⃣ Run server
# ============================================================
if __name__ == "__main__":
    print("🚀 Starting Flask AI Server...")
    app.run(host="0.0.0.0", port=5000, debug=False)