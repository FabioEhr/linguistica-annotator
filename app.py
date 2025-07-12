import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os

# --------- Config --------------------
CSV_PATH = "train_sentences_libera.csv"           # frasi da etichettare
SAVE_PATH = "annotations.jsonl"      # file dove salvo le risposte
CATEGORIES = {
    1: "Libera – emancipata",
    2: "Libera – indipendente affettivamente, single",
    3: "Libera – sessualmente positiva",
    4: "Libera – sessualmente spregiativa",
    5: "Libera – disinvolta / franca",
    6: "Libera – status legale/giudiziario"
}
# -------------------------------------

@st.cache_data
def load_sentences(path):
    df = pd.read_csv(path)
    # frasi non ancora annotate
    done_ids = {json.loads(l)["id"] for l in open(SAVE_PATH)} if os.path.exists(SAVE_PATH) else set()
    df = df[~df["id"].isin(done_ids)]
    return df.sample(frac=1, random_state=42).reset_index(drop=True)

def save_annotation(row_id, sent_id, label, annotator):
    record = {
        "row_uuid": str(uuid.uuid4()),
        "annotator": annotator,
        "timestamp": datetime.utcnow().isoformat(),
        "id": int(sent_id),
        "label": int(label)
    }
    with open(SAVE_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

# --------- UI ------------------------
st.title("Annotazione: significato di «donna libera»")

annotator = st.text_input("Inserisci il tuo nome o nickname:")
if not annotator:
    st.stop()

df = load_sentences(CSV_PATH)
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
    index=None
)

if st.button("Salva e passa alla prossima", disabled=label is None):
    save_annotation(row.name, row["id"], label, annotator)
    st.rerun()
