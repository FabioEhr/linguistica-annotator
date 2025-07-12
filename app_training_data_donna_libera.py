import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# --------- Config --------------------
SHEET_NAME = "Training_data_donna_libera"

SYSTEM_PROMPT = """
Sei un classificatore che assegna ogni frase a una di queste categorie sul significato dell'espressione "donna libera":

1 → Libera – emancipata: donna autonoma, consapevole, libera da vincoli culturali o sociali. Connotazione positiva legata all’indipendenza e all’autodeterminazione.

2 → Libera – indipendente affettivamente: donna non impegnata sentimentalmente o coniugalmente (es. single, nubile). Uso neutro o leggermente positivo.

3 → Libera – connotazione sessuale positiva: donna sessualmente disinibita o autodeterminata, descritta con rispetto e ammirazione. Nessuna allusione moralistica.

4 → Libera – connotazione sessuale spregiativa/insinuante: donna etichettata come "libera" con tono ironico o denigratorio, che suggerisce promiscuità o moralismo implicito.

5 → Libera – disinvolta / diretta / franca: donna schietta, spontanea o senza inibizioni nel comportamento o nel modo di esprimersi. Uso neutro o lievemente positivo.

6 → Libera – status legale o giudiziario: donna che ha ottenuto la libertà in senso giuridico (ad esempio dopo detenzione, assoluzione, o proscioglimento). Uso neutro o descrittivo.

Rispondi **ESCLUSIVAMENTE** con un JSON UTF-8 valido:
{
  "class": <numero intero tra 1 e 6>
}

Esempi:

Input: "È una donna libera, vive secondo le sue regole e non accetta imposizioni."
Output: {"class": 1}

Input: "Una donna libera, non è sposata né ha legami stabili."
Output: {"class": 2}

Input: "È una donna libera anche nella sessualità, e lo rivendica con fierezza."
Output: {"class": 3}

Input: "Fa tanto la donna libera, ma tutti sanno che è solo una facile."
Output: {"class": 4}

Input: "È una donna libera, dice sempre quello che pensa e non ha peli sulla lingua."
Output: {"class": 5}

Input: "Dopo vent'anni di carcere, Patrizia Reggiani è una donna libera."
Output: {"class": 6}
"""

CATEGORIES = {
    1: "Libera – emancipata",
    2: "Libera – indipendente affettivamente",
    3: "Libera – connotazione sessuale positiva",
    4: "Libera – connotazione sessuale spregiativa/insinuante",
    5: "Libera – disinvolta / diretta / franca",
    6: "Libera – status legale o giudiziario"
}

# Show instructions in the sidebar
st.sidebar.title("Spiegazioni delle categorie")
st.sidebar.subheader("Definizioni e esempi")
st.sidebar.markdown("""
**1 → Libera – emancipata**: donna autonoma, consapevole, libera da vincoli culturali o sociali. Connotazione positiva legata all’indipendenza e all’autodeterminazione.  
    es. "È una donna libera, vive secondo le sue regole e non accetta imposizioni."  
**2 → Libera – indipendente affettivamente**: donna non impegnata sentimentalmente o coniugalmente (es. single, nubile). Uso neutro o leggermente positivo.  
    es. "Una donna libera, non è sposata né ha legami stabili."  
**3 → Libera – connotazione sessuale positiva**: donna sessualmente disinibita o autodeterminata, descritta con rispetto e ammirazione. Nessuna allusione moralistica.  
    es. "È una donna libera anche nella sessualità, e lo rivendica con fierezza."  
**4 → Libera – connotazione sessuale spregiativa/insinuante**: donna etichettata come 'libera' con tono ironico o denigratorio, che suggerisce promiscuità o moralismo implicito.  
    es. "Fa tanto la donna libera, ma tutti sanno che è solo una facile."  
**5 → Libera – disinvolta / diretta / franca**: donna schietta, spontanea o senza inibizioni nel comportamento o nel modo di esprimersi. Uso neutro o lievemente positivo.  
    es. "È una donna libera, dice sempre quello che pensa e non ha peli sulla lingua."  
**6 → Libera – status legale o giudiziario**: donna che ha ottenuto la libertà in senso giuridico (ad esempio dopo detenzione, assoluzione, o proscioglimento). Uso neutro o descrittivo.  
    es. "Dopo vent'anni di carcere, Patrizia Reggiani è una donna libera."  
""")
# -------------------------------------


def load_sentences(annotator_input):
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

    # normalize annotator name case-insensitively
    annotator_input = annotator_input.strip()
    lower_input = annotator_input.lower()
    # map existing headers lower→original
    lower_header_map = {h.lower(): h for h in header}
    if lower_input in lower_header_map:
        annotator = lower_header_map[lower_input]
    else:
        annotator = annotator_input
        # add new column to DataFrame and sheet
        df[annotator] = ""
        ws.update_cell(1, len(header) + 1, annotator)
        header.append(annotator)

    done = df[df[annotator] != ""]["id"].tolist()
    done_count = len(done)
    todo = df[~df["id"].isin(done)].sample(frac=1, random_state=42)
    return todo.reset_index(drop=True), ws, header, done_count, total_count, annotator

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
    df_loaded, ws, header, done_count, total_count, canonical_annotator = load_sentences(annotator)
    st.session_state.annotator = canonical_annotator
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
    st.balloons()
    st.title("Grazie!")
    st.write("Annotazione terminata. Grazie per il tuo contributo!")
    st.stop()

 # display progress of all annotators
st.markdown(f"**Annotazioni già effettuate da tutti gli annotatori**: {done_count} / {total_count}")
# display progress of current annotator in this session
remaining = len(st.session_state.todo_df)
current_index = st.session_state.pointer + 1
st.markdown(f"**Frase corrente da annotare**: {current_index} / {remaining}")

if df.empty:
    st.balloons()
    st.title("Grazie!")
    st.write("Hai completato tutte le annotazioni. Grazie per il tuo contributo!")
    st.stop()

pointer = st.session_state.pointer
row = df.iloc[pointer]
st.markdown(f"### Frase #{row['id']} ({row['date'].date() if not pd.isna(row['date']) else ''})")
with st.expander("Mostra/Nascondi testo della frase", expanded=True):
    st.write(row["sentence"])

label = st.radio(
    "Seleziona la categoria corretta:",
    options=list(CATEGORIES.keys()),
    format_func=lambda x: f"{x} → {CATEGORIES[x]}",
    key="label"
)

# Session instructions above buttons
st.caption("Seleziona una categoria e poi premi un pulsante.")

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
    st.button(
        "Indietro",
        on_click=lambda: setattr(st.session_state, "pointer", st.session_state.history.pop()),
        disabled=st.session_state.pointer == 0
    )
with col2:
    if st.button("Salva e termina", disabled=label is None):
        on_save_and_quit()
        st.success("Annotazione terminata. Grazie!")
        st.stop()
with col3:
    st.button(
        "Salva e passa alla prossima",
        on_click=on_save,
        disabled=label is None
    )
