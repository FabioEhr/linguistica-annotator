import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os

# --------- Config --------------------
CSV_PATH  = "train_sentences_libera.csv"
SAVE_PATH = "annotations.jsonl"

CATEGORIES = {
    1: "Libera – emancipata",
    2: "Libera – indipendente affettivamente, single",
    3: "Libera – sessualmente positiva",
    4: "Libera – sessualmente spregiativa",
    5: "Libera – disinvolta / franca",
    6: "Libera – status legale/giudiziario"
}
# -------------------------------------

def load_sentences(path, ann_path):
    df = pd.read_csv(path)
    if "id" not in df.columns:
        df.insert(0, "id", df.index)
    done_ids = set()
    if os.path.exists(ann_path):
        with open(ann_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    done_ids.add(json.loads(line)["id"])
                except:
                    pass
    df = df[~df["id"].isin(done_ids)]
    return df.sample(frac=1, random_state=42).reset_index(drop=True)

def save_annotation(sent_id, label, annotator):
    rec = {
        "row_uuid": str(uuid.uuid4()),
        "annotator": annotator,
        "timestamp": datetime.utcnow().isoformat(),
        "id": int(sent_id),
        "label": int(label)
    }
    with open(SAVE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

st.title("Annotazione: significato di «donna libera»")

annotator = st.text_input("Inserisci il tuo nome o nickname:")
if not annotator:
    st.warning("Per favore inserisci il tuo nome o nickname per cominciare.")
    st.stop()

df = load_sentences(CSV_PATH, SAVE_PATH)
if df.empty:
    st.success("Tutte le frasi sono state annotate. Grazie!")
    st.stop()

row = df.iloc[0]
st.markdown(f"### Frase #{row['id']}")
st.write(row["sentence"])

label = st.radio(
    "Seleziona la categoria corretta:",
    options=list(CATEGORIES.keys()),
    format_func=lambda x: f"{x} → {CATEGORIES[x]}",
)

# define a callback that saves and does nothing else
def on_save():
    save_annotation(row["id"], label, annotator)

st.button(
    "Salva e passa alla prossima",
    on_click=on_save,
    disabled=label is None
)
