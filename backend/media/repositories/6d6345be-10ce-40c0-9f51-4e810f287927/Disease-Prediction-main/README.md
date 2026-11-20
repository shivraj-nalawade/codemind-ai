# 🌡️🩺 Smart Health Predictor Using Weather Conditions & Symptoms  
*A Machine Learning Web Application built with Streamlit*

---

## 🚀 Overview

This project predicts **likely diseases** based on a combination of:

- 🌦️ Weather conditions (Temperature, Humidity, Wind Speed)  
- 🧍 Patient demographics (Gender, Age)  
- 🤒 User-selected symptoms  

A trained machine-learning pipeline produces:  
- 🎯 Most probable disease  
- 📊 Top 5 predictions with probabilities  
- 📈 Visual probability bar chart  

This app is developed using **Streamlit** with a modern, responsive UI.

---

## 👥 Team Members
- **Shivraj Nalawade** – PRN: 202301060008  
- **Pritesh Purkar** – PRN: 202301060010  

---

## 📂 GitHub Repository

🔗 **https://github.com/shivraj-nalawade/Disease-Prediction**

---

## 🧠 Machine Learning Models Used

The following ML algorithms were trained and evaluated:

- Random Forest  
- Logistic Regression  
- Support Vector Machine (SVM)  
- XGBoost  
- Decision Tree  
- Naïve Bayes  
- K-Nearest Neighbors (KNN)

The best-performing model was exported as a `.pkl` pipeline for deployment.

---

## 🏗️ Project Architecture

### **1️⃣ Data Preparation**
- Cleaning and preprocessing dataset  
- Encoding categorical variables  
- Performing train-test split  

### **2️⃣ Model Training**
- Training multiple ML algorithms  
- Evaluating metrics (accuracy, precision, recall)  
- Selecting best model  
- Saving pipeline (`disease_prediction_pipeline.pkl`)

### **3️⃣ Streamlit Interface**
- Weather & patient input fields  
- Dynamic symptom selection  
- Interactive probability chart  
- Custom UI with background theme  

### **4️⃣ Deployment**
- Packaged app for Streamlit Cloud / Render  
- Includes:
  - `app.py`
  - `requirements.txt`
  - Model `.pkl` files
  - `style.css`
  - `background.png`

---

## 🖥️ Tech Stack

| Component | Technology |
|----------|------------|
| Frontend | Streamlit |
| Backend | Python |
| ML Models | Scikit-Learn, XGBoost |
| Data Handling | Pandas, NumPy |
| Visualization | Matplotlib, Seaborn |

---
