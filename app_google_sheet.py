import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# --------- Config --------------------
SHEET_NAME = "train_sentences_libera"

CATEGORIES = {
    1: "Libera – emancipata",
    2: "Libera – indipendente affettivamente, single",
    3: "Libera – sessualmente positiva",
    4: "Libera – sessualmente spregiativa",
    5: "Libera – disinvolta / franca",
    6: "Libera – status legale/giudiziario"
}
# -------------------------------------


def load_sentences(annotator):
    # connect to Google Sheet
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    ws = client.open(SHEET_NAME).sheet1

    # fetch all data
    all_values = ws.get_all_values()
    header = all_values[0]
    rows = all_values[1:]
    total_count = len(rows)

    # track original sheet row numbers
    sheet_rows = list(range(2, len(rows) + 2))

    df = pd.DataFrame(rows, columns=header)
    # record sheet row for each DataFrame row
    df["__sheet_row"] = sheet_rows

    # ensure an 'id' column exists
    if "id" in df.columns:
        df["id"] = df["id"].astype(int)
    else:
        df.insert(0, "id", df.index)  # fallback to DataFrame index

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    if annotator not in df.columns:
        # add column in DataFrame
        df[annotator] = ""
        # update the sheet header
        ws.update_cell(1, len(header) + 1, annotator)
        header.append(annotator)

    done = df[df[annotator] != ""]["id"].tolist()
    done_count = len(done)
    todo = df[~df["id"].isin(done)].sample(frac=1, random_state=42)
    return todo.reset_index(drop=True), ws, header, done_count, total_count

def save_annotation(ws, header, sheet_row, label, annotator):
    # update the cell at the known sheet row
    col_number = header.index(annotator) + 1
    ws.update_cell(sheet_row, col_number, str(label))

st.title("Annotazione: significato di «donna libera»")

annotator = st.text_input("Inserisci il tuo nome o nickname:")
if not annotator:
    st.warning("Per favore inserisci il tuo nome o nickname per cominciare.")
    st.stop()

# Initialize session state for this annotator
if st.session_state.get("annotator") != annotator:
    st.session_state.annotator = annotator
    df_loaded, ws, header, done_count, total_count = load_sentences(annotator)
    st.session_state.todo_df = df_loaded
    st.session_state.ws = ws
    st.session_state.header = header
    st.session_state.done_count = done_count
    st.session_state.total_count = total_count
    st.session_state.pointer = 0
    st.session_state.history = []
    st.session_state.finished = False

df = st.session_state.todo_df
ws = st.session_state.ws
header = st.session_state.header
done_count = st.session_state.done_count
total_count = st.session_state.total_count

if st.session_state.finished:
    st.success("Annotazione terminata. Grazie!")
    st.stop()

st.write(f"Progresso: {done_count} / {total_count} frasi annotate")
st.progress(done_count / total_count)
if df.empty:
    st.success("Tutte le frasi sono state annotate. Grazie!")
    st.stop()

pointer = st.session_state.pointer
row = df.iloc[pointer]
st.markdown(f"### Frase #{row['id']} ({row['date']})")
st.write(row["sentence"])

label = st.radio(
    "Seleziona la categoria corretta:",
    options=list(CATEGORIES.keys()),
    format_func=lambda x: f"{x} → {CATEGORIES[x]}",
    key="label"
)

# define callbacks for saving and navigation
def on_save():
    # save current annotation
    save_annotation(st.session_state.ws, st.session_state.header,
                    row["__sheet_row"], st.session_state.label,
                    st.session_state.annotator)
    # advance pointer
    st.session_state.history.append(st.session_state.pointer)
    st.session_state.pointer += 1

def on_save_and_quit():
    on_save()
    st.session_state.finished = True

col1, col2, col3 = st.columns([1,1,1])
with col1:
    st.button("Indietro", on_click=lambda: setattr(st.session_state, "pointer", st.session_state.history.pop()), disabled=st.session_state.pointer==0)
with col2:
    st.button("Salva e termina", on_click=on_save_and_quit, disabled=label is None)
with col3:
    st.button("Salva e passa alla prossima", on_click=on_save, disabled=label is None)
