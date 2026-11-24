
"""
Context-aware rule-based query expansion
for repository-level code retrieval.
"""

QUERY_EXPANSIONS = {
    "prediction": [
        "predict",
        "safe_predict",
        "classification",
        "inference",
        "classifier",
        "prediction pipeline",
    ],

    "probability": [
        "predict_proba",
        "class probabilities",
        "confidence scores",
        "probability output",
        "Probability Chart",
        "top predictions",
    ],

    "probabilities": [
    "predict_proba",
    "class probabilities",
    "confidence scores",
    "probability output",
    "Probability Chart",
    "top predictions",
    "st.number_input",
    "st.button",
    "pd.DataFrame",
    "safe_predict",
    "st.success",
    "st.dataframe",
    "st.pyplot",
    "patient input",
    "prediction workflow",
],

    "disease": [
        "disease prediction",
        "disease classifier",
        "classification model",
    ],

    "load": [
        "load_artifacts",
        "joblib",
        "pickle",
        "model loading",
        "pipeline loading",
    ],

    "feature": [
        "DataFrame",
        "feature columns",
        "feature_names_in_",
        "reindex",
        "input validation",
    ],

    "label": [
        "inverse_transform",
        "label encoder",
        "encoded classes",
        "class labels",
    ],

    "display": [
        "prediction result",
        "st.write",
        "st.success",
        "st.dataframe",
        "output display",
    ],

    "result": [
        "prediction output",
        "predicted class",
        "predicted disease",
        "probability scores",
    ],

    "input": [
        "user input",
        "input features",
        "form submission",
        "input validation",
    ],

    "patient": [
        "Patient Input",
        "st.number_input",
        "patient features",
        "symptom selection",
    ],

    "generate": [
        "st.button",
        "Predict",
        "safe_predict",
        "prediction workflow",
    ],

    "interface": [
        "Streamlit",
        "st.number_input",
        "st.button",
        "st.dataframe",
        "st.pyplot",
    ],

    "output": [
        "Predicted Disease",
        "st.success",
        "top predictions",
        "Probability Chart",
        "prediction result",
    ],

    "algorithm": [
        "machine learning model",
        "classification algorithm",
        "trained model",
    ],

    "workflow": [
        "application flow",
        "execution flow",
        "prediction pipeline",
    ],
    "expected": [
    "infer_expected_columns",
    "expected input columns",
    "feature_names_in_",
    "preprocessor",
    "transformers_",
    "continuous columns",
    "passthrough features",
],
"css": [
    "style.css",
    "CSS_FILE",
    "inject_css_with_background",
    "st.markdown",
    "unsafe_allow_html",
    "CSS styles",
],

"background image": [
    "BG_FILE",
    "background.png",
    "base64",
    "base64.b64encode",
    "data URI",
    "background-image",
    "os.path.exists",
],

"libraries": [
    "scikit-learn",
    "sklearn",
    "XGBoost",
    "xgboost",
    "Pandas",
    "NumPy",
    "Matplotlib",
    "Seaborn",
    "requirements.txt",
],

"technologies": [
    "Streamlit",
    "Python",
    "Scikit-Learn",
    "XGBoost",
    "Pandas",
    "NumPy",
    "Matplotlib",
    "Seaborn",
    "tech stack",
],

"machine learning": [
    "ML models",
    "scikit-learn",
    "XGBoost",
    "trained pipeline",
    "classification model",
    "machine learning dependencies",
],
}


def expand_query(query):
    """
    Expand a natural-language query using
    relevant technical terms.

    The original query is always preserved.
    """

    if not query or not query.strip():
        return query

    query_lower = query.lower()
    expanded_terms = []

    for keyword, terms in QUERY_EXPANSIONS.items():
        if keyword in query_lower:
            expanded_terms.extend(terms)

    # Remove duplicate terms while preserving order.
    expanded_terms = list(dict.fromkeys(expanded_terms))

    if not expanded_terms:
        return query

    return f"{query} {' '.join(expanded_terms)}"
