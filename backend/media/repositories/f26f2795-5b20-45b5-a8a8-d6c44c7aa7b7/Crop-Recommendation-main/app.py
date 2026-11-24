from flask import Flask, render_template, request
import numpy as np
import joblib

app = Flask(__name__)

# Load ML model and label encoder
model = joblib.load("Best_Crop_Recommendation_Model.pkl")
label_encoder = joblib.load("Crop_Label_Encoder.pkl")


@app.route('/')
def welcome():
    return render_template("welcome.html")


@app.route('/index')
def index():
    return render_template("index.html")


@app.route('/predict', methods=['POST'])
def predict():
    # --- Parse inputs
    N = float(request.form['N'])
    P = float(request.form['P'])
    K = float(request.form['K'])
    temperature = float(request.form['temperature'])
    humidity = float(request.form['humidity'])
    ph = float(request.form['ph'])
    rainfall = float(request.form['rainfall'])

    # --- Realistic validation based on dataset ranges
    limits = {
        "N": (0, 140),
        "P": (5, 145),
        "K": (5, 205),
        "temperature": (-5, 55),   # Celsius realistic farming range
        "humidity": (0, 100),
        "ph": (3.0, 10.0),
        "rainfall": (0, 350)       # dataset max = 298
    }

    inputs = {
        "N": N,
        "P": P,
        "K": K,
        "temperature": temperature,
        "humidity": humidity,
        "ph": ph,
        "rainfall": rainfall
    }

    errors = []

    # Validate all inputs
    for key, val in inputs.items():
        lo, hi = limits[key]
        if not (lo <= val <= hi):
            errors.append(f"{key}: {val} (Allowed: {lo} → {hi})")

    if errors:
        return render_template(
            "index.html",
            error="Invalid input(s): " + "; ".join(errors)
        )

    # --- Prediction (unchanged)
    features = np.array([[N, P, K, temperature, humidity, ph, rainfall]])
    prediction = model.predict(features)[0]
    crop = label_encoder.inverse_transform([prediction])[0]

    image_file = crop.lower() + ".jpg"

    return render_template("result.html", crop=crop, image_file=image_file)


if __name__ == "__main__":
    app.run(debug=True)
