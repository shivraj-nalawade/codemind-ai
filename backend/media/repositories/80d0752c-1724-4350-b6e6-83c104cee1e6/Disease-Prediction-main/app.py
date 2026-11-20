# app.py — Clean Streamlit UI (Gender added, no drag-drop upload) + restored probability chart
# Now with improved CSS & background embedding (more robust selectors + debug)
import streamlit as st
import joblib
import pandas as pd
import numpy as np
import os
import base64
import matplotlib.pyplot as plt

try:
    import joblib
except Exception:
    import streamlit as st
    st.error("Required package 'joblib' not installed. Add it to requirements.txt and redeploy.")
    st.stop()

# ---------- Page config ----------
st.set_page_config(page_title="Disease Predictor", layout="wide", initial_sidebar_state="expanded")
# --- FIX CROPPED LABELS GLOBALLY WITHOUT EXTERNAL CSS ---
st.markdown("""
<style>
/* Expand label height for all selectboxes, number inputs, multiselects */
div[data-baseweb="select"] label,
div[data-baseweb="input"] label,
div[data-baseweb="textarea"] label,
.stSelectbox label,
.stNumberInput label,
.stMultiSelect label {
    white-space: normal !important;
    height: auto !important;
    line-height: 1.3 !important;
    overflow: visible !important;
    padding-bottom: 6px !important;
    display: block !important;
}

/* Fix parent container clipping */
div[data-baseweb="select"],
div[data-baseweb="input"],
div[data-baseweb="textarea"],
.stSelectbox, .stNumberInput, .stMultiSelect {
    overflow: visible !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- FILE NAMES ----------
PIPELINE_FILES = ["disease_prediction_pipeline.pkl"]
ENCODER_FILES = ["le_prognosis.pkl"]
CSS_FILE = "styles.css"
BG_FILE = "background.png"   

# ---------- Load external CSS and background (embed image as data-uri) ----------
def inject_css_with_background(css_path=CSS_FILE, bg_path=BG_FILE):
    """
    Inject CSS into the page and embed background image as base64 data URI.
    This function writes styles for both body::before and Streamlit app container to
    maximize compatibility across Streamlit versions and deployments.
    """
    default_css = r"""
    :root{
      --card-bg: rgba(18,20,22,0.6);
      --card-elev: 0 6px 20px rgba(2,6,23,0.6);
      --accent: #2b8cbe;
      --muted: #98a3ab;
    }

    /* body fallback - blurred background image */
    body::before {
      content: "";
      position: fixed;
      inset: 0;
      z-index: -2;
      background-image: url("{BG_DATA_URI}");
      background-size: cover;
      background-position: center;
      filter: blur(2px) saturate(0.95);
      transform: scale(1.02);
      opacity: 0.65;
    }
    /* dark overlay for readability */
    body::after {
      content: "";
      position: fixed;
      inset: 0;
      z-index: -1;
      background: linear-gradient(180deg, rgba(6,10,13,0.65), rgba(6,10,13,0.65));
    }

    /* also set background on Streamlit app container for compatibility */
    [data-testid="stAppViewContainer"] {
      background-image: url("{BG_DATA_URI}") !important;
      background-size: cover !important;
      background-position: center !important;
      background-repeat: no-repeat !important;
      background-attachment: fixed !important;
    }
    [data-testid="stAppViewContainer"]::before {
      content: "";
      position: absolute;
      inset: 0;
      z-index: -1;
      background: linear-gradient(180deg, rgba(6,10,13,0.45), rgba(6,10,13,0.45));
    }

    .block-container { padding: 1.25rem 2rem; color: #e8eef5; font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; }
    .center-header { text-align: center; margin-bottom: 0.6rem; }
    .center-header h1 { font-size: 2.4rem; margin: 0; letter-spacing: -0.5px; }
    .center-header p { color: var(--muted); margin-top: 6px; }
    .card { background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01)); border-radius: 12px; padding: 18px; box-shadow: var(--card-elev); border: 1px solid rgba(255,255,255,0.03); margin-bottom: 12px; }
    .stButton>button { border-radius: 10px; padding: 8px 14px; background: linear-gradient(180deg, var(--accent), #1f6c95); color: white; border: none; }
    .stTable td, .stTable th, .stDataFrame td, .stDataFrame th { padding: 8px 10px; border-color: rgba(255,255,255,0.04); }
    .small-muted { color: var(--muted); font-size: 0.95rem; }
    @media (max-width: 800px) { .center-header h1 { font-size: 1.8rem; } .block-container { padding: 1rem; } }
    """

   
    bg_uri = ""
    bg_found = False
    if os.path.exists(bg_path):
        try:
            with open(bg_path, "rb") as f:
                im_bytes = f.read()
            # detect mime
            if bg_path.lower().endswith(".png"):
                mime = "image/png"
            elif bg_path.lower().endswith(".webp"):
                mime = "image/webp"
            else:
                mime = "image/jpeg"
            bg_b64 = base64.b64encode(im_bytes).decode("utf-8")
            bg_uri = f"data:{mime};base64,{bg_b64}"
            bg_found = True
        except Exception as e:
            st.sidebar.warning(f"Could not embed background image: {e}")
            bg_uri = ""
            bg_found = False
    else:
        # file not found
        bg_uri = ""
        bg_found = False

    # Read user-provided CSS if exists; otherwise use default_css
    css_text = default_css
    css_found = False
    if os.path.exists(css_path):
        try:
            with open(css_path, "r", encoding="utf-8") as f:
                css_text = f.read()
            css_found = True
        except Exception as e:
            st.sidebar.warning(f"Failed to read {css_path}. Using built-in styles. Error: {e}")
            css_found = False

    # Replace placeholder
    css_text = css_text.replace("{BG_DATA_URI}", bg_uri)

    # Inject CSS
    st.markdown(f"<style>{css_text}</style>", unsafe_allow_html=True)

    # Provide debug info in sidebar
    st.sidebar.markdown("### Theme / assets")
    st.sidebar.write(f"styles.css present: {'Yes' if css_found else 'No'}")
    st.sidebar.write(f"{bg_path} present: {'Yes' if bg_found else 'No'}")
    if not bg_found:
        st.sidebar.info("To show background place an image named 'background.png' (or change BG_FILE) in the app folder and restart the app.")

# Load Google font and inject CSS/background early
st.markdown("""<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;700&display=swap" rel="stylesheet">""", unsafe_allow_html=True)
inject_css_with_background()

# ---------- Helper functions & ML loading (unchanged logic) ----------
@st.cache_resource
def load_artifacts():
    pipeline_path = None
    for p in PIPELINE_FILES:
        if os.path.exists(p):
            pipeline_path = p
            break
    if pipeline_path is None:
        raise FileNotFoundError("Pipeline file not found.")

    encoder_path = None
    for e in ENCODER_FILES:
        if os.path.exists(e):
            encoder_path = e
            break
    if encoder_path is None:
        raise FileNotFoundError("Label encoder not found.")

    pipe = joblib.load(pipeline_path)
    le = joblib.load(encoder_path)
    return pipe, le, pipeline_path, encoder_path

def infer_expected_columns(pipe):
    try:
        pre = pipe.named_steps.get("preprocessor", None)
        if pre is not None:
            cont = list(pre.transformers_[0][2])
            passthrough = list(pre.transformers_[1][2])
            return cont + passthrough
    except:
        pass

    if hasattr(pipe, "feature_names_in_"):
        return list(pipe.feature_names_in_)

    return None

def safe_predict(pipe, le, df):
    try:
        preds = pipe.predict(df)
        probs = pipe.predict_proba(df) if hasattr(pipe, "predict_proba") else None
    except:
        # attempt to reindex using pipeline feature names and retry
        if hasattr(pipe, "feature_names_in_"):
            df = df.reindex(columns=pipe.feature_names_in_, fill_value=0)
            preds = pipe.predict(df)
            probs = pipe.predict_proba(df) if hasattr(pipe, "predict_proba") else None
        else:
            raise

    return preds, le.inverse_transform(preds), probs

# ---------- Load model ----------
try:
    pipeline, le_prognosis, pipeline_path, encoder_path = load_artifacts()
    st.sidebar.success("Loaded pipeline & encoder")
except Exception as e:
    st.sidebar.error(str(e))
    st.stop()

# ---------- Get columns ----------
expected_cols = infer_expected_columns(pipeline)
if expected_cols is None:
    st.error("Unable to detect feature columns.")
    st.stop()

# Separate continuous, gender, symptoms
cont_keys = ["age", "temp", "humidity", "wind"]
cont_cols = [c for c in expected_cols if any(k in c.lower() for k in cont_keys)]

gender_col = None
if "Gender" in expected_cols:
    gender_col = "Gender"

symptom_cols = [c for c in expected_cols if c not in cont_cols and c != gender_col]

# Track symptom selections
if "selected_symptoms" not in st.session_state:
    st.session_state.selected_symptoms = []

# ---------- CENTERED HEADER ----------
st.markdown("<div class='center-header'><h1>Disease Prediction</h1><p style='color:var(--muted)'>Predict disease from weather and symptoms</p></div>", unsafe_allow_html=True)

# ---------- Layout ----------
left, right = st.columns([1, 2])

# ---------- LEFT PANE (final robust version: multiselect top, callbacks to update state) ----------
with left:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("Controls")

    # Gender selection
    if gender_col:
        gender_value = st.selectbox("Gender", ["Female (0)", "Male (1)"])
        gender_numeric = 0 if "Female" in gender_value else 1
    else:
        gender_numeric = 0

    st.markdown("### Symptom Selection")

    # --- Helper callbacks (must be defined before widgets that reference them) ---
    def select_all_cb():
        # set the multiselect state to all symptoms (allowed inside callback)
        st.session_state["multi_symp"] = symptom_cols.copy()
        # ensure checkboxes reflect the selection (they will be created with these keys)
        for s in symptom_cols:
            st.session_state[f"chk_{s}"] = True

    def clear_all_cb():
        st.session_state["multi_symp"] = []
        for s in symptom_cols:
            st.session_state[f"chk_{s}"] = False

    def checkbox_changed(symptom):
        """Called when any symptom checkbox changes. Update multiselect state accordingly."""
        ms = list(st.session_state.get("multi_symp", []))  # current multiselect list
        chk_key = f"chk_{symptom}"
        checked = bool(st.session_state.get(chk_key, False))
        if checked and (symptom not in ms):
            ms.append(symptom)
        if (not checked) and (symptom in ms):
            ms.remove(symptom)
        st.session_state["multi_symp"] = ms

    # Ensure session_state keys exist with sensible defaults to avoid KeyError
    if "multi_symp" not in st.session_state:
        st.session_state["multi_symp"] = st.session_state.get("selected_symptoms", [])

    # --- 1) Searchable multiselect (TOP) ---
    # Note: we DO NOT programmatically set st.session_state["multi_symp"] after this widget in main flow.
    selected = st.multiselect(
        "Symptoms (searchable)",
        options=symptom_cols,
        default=st.session_state.get("multi_symp", []),
        key="multi_symp"
    )
    # Keep canonical list synced from the multiselect (user interaction writes into "multi_symp")
    st.session_state["selected_symptoms"] = list(selected)

    st.write("")  # spacing

    # --- 2) Select All / Clear All buttons (use on_click callbacks) ---
    c1, c2 = st.columns([1, 1])
    c1.button("Select all", on_click=select_all_cb)
    c2.button("Clear all", on_click=clear_all_cb)

    st.write("")  # spacing

    # --- 3) Show Checkbox Grid toggle ---
    show_grid = st.checkbox(
        "Show checkbox grid (tick to select)",
        value=False,
        help="Tick symptoms in the grid — selections sync with the searchable list."
    )

    # --- 4) Checkbox grid (if enabled) ---
    if show_grid:
        cols = st.columns(3)
        # Render checkboxes. Each checkbox uses on_change to call checkbox_changed(symptom).
        for i, s in enumerate(symptom_cols):
            chk_key = f"chk_{s}"
            # checkbox default: prefer explicit stored checkbox value, otherwise check if in multiselect
            default_val = st.session_state.get(chk_key, (s in st.session_state.get("multi_symp", [])))
            # create checkbox with on_change pointing to checkbox_changed
            cols[i % 3].checkbox(
                s,
                value=default_val,
                key=chk_key,
                on_change=checkbox_changed,
                args=(s,)
            )
        # Note: checkbox_changed updates st.session_state["multi_symp"], which in turn updates the multiselect on rerun.
        # Also keep canonical list explicit:
        st.session_state["selected_symptoms"] = list(st.session_state.get("multi_symp", []))

    st.markdown("</div>", unsafe_allow_html=True)


# ---------- RIGHT PANE ----------
with right:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.header("Patient Input")

    # Continuous inputs
    vals = {}
    if len(cont_cols) == 0:
        cont_cols = []

    # realistic ranges (tweak if your data uses different units)
    RANGES = {
        # key (lowercased) : (min, max, default, step, format)
        "age": (0.0, 120.0, 30.0, 1.0, "%.0f"),
        "temperature (c)": (-50.0, 60.0, 37.0, 0.1, "%.2f"),
        "temp": (-50.0, 60.0, 37.0, 0.1, "%.2f"),
        "humidity": (0.0, 100.0, 50.0, 0.1, "%.2f"),
        "wind speed (km/h)": (0.0, 300.0, 10.0, 0.1, "%.2f"),
        "wind": (0.0, 300.0, 10.0, 0.1, "%.2f"),
    }

    # Create number inputs (one column per continuous feature)
    cols_ui = st.columns(max(1, len(cont_cols)))
    for i, c in enumerate(cont_cols):
        lookup = c.lower()
        # use defined range if present, else fallback
        if lookup in RANGES:
            lo, hi, default, step, fmt = RANGES[lookup]
        else:
            lo, hi, default, step, fmt = (0.0, 1e6, 0.0, 0.1, "%.2f")

        with cols_ui[i]:
            vals[c] = st.number_input(
                label=c,
                min_value=lo,
                max_value=hi,
                value=default if default is not None else 0.0,
                step=step,
                format=fmt,
                key=f"cont_{c}"
            )

    # Create input row
    if st.button("Predict", type="primary"):
        # build row
        row = {c: 0 for c in expected_cols}
        for k, v in vals.items():
            # defensive clamp (server side) to same ranges
            lk = k.lower()
            if lk in RANGES:
                lo, hi, *_ = RANGES[lk]
                clamped = float(max(min(v, hi), lo))
            else:
                # fallback generic clamp (very wide)
                clamped = float(v)

            row[k] = clamped

        if gender_col:
            row[gender_col] = gender_numeric
        for s in symptom_cols:
            row[s] = 1 if s in st.session_state.selected_symptoms else 0

        # warn user if input(s) were adjusted
        clamped_msgs = []
        for k, orig in vals.items():
            if float(row[k]) != float(orig):
                clamped_msgs.append(f"{k}: entered {orig} → used {row[k]}")
        if clamped_msgs:
            st.warning("Some inputs were adjusted to realistic ranges:\n" + "\n".join(clamped_msgs))

        df = pd.DataFrame([row])
        preds, labels, probs = safe_predict(pipeline, le_prognosis, df)
        st.success(f"Predicted Disease: **{labels[0]}**")

        if probs is not None:
            top = np.argsort(probs[0])[::-1][:5]
            df_top = pd.DataFrame({
                "Disease": le_prognosis.inverse_transform(top),
                "Probability": probs[0][top]
            })

            # ---- Side-by-side table + chart with matched heights ----
            df_top = df_top.sort_values("Probability", ascending=False).reset_index(drop=True)
            chart_height_px = 160 + 40 * len(df_top)

            col_table, col_chart = st.columns([1,1])
            with col_table:
                st.subheader("Top predictions")
                st.dataframe(df_top.style.format({"Probability":"{:.4f}"}), height=chart_height_px)

            with col_chart:
                st.subheader("Probability Chart")
                chart_df = df_top.copy().iloc[::-1]
                fig, ax = plt.subplots(figsize=(7, 0.4 * len(chart_df) + 1.2))
                bars = ax.barh(chart_df["Disease"], chart_df["Probability"], color="#2b8cbe")
                ax.set_xlabel("Probability")
                ax.set_xlim(0, 1)
                ax.set_ylabel("")
                ax.invert_yaxis()
                for bar in bars:
                    width = bar.get_width()
                    ax.text(width + 0.02, bar.get_y() + bar.get_height()/2, f"{width:.2f}", va='center', fontsize=10)
                plt.tight_layout()
                st.pyplot(fig)


    st.markdown("</div>", unsafe_allow_html=True)
