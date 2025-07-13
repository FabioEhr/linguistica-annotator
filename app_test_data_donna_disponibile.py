import streamlit as st
import pandas as pd
from datetime import datetime
import uuid
import json
import os
import gspread
from google.oauth2.service_account import Credentials

# --------- Config --------------------
SHEET_NAME = "test data donna disponibile"


CATEGORIES = {
    1: "Neutro/lavorativo/Pratico",
    2: "Sessuale/dispregiativo",
    3: "Figurato/positivo",
    4: "Aggettivo non riferito a donna"
}

# Show instructions in the sidebar
st.sidebar.title("Spiegazioni delle categorie")
st.sidebar.subheader("Definizioni")
st.sidebar.markdown("""
**1 → Neutro/lavorativo/Pratico**: 'disponibile' in senso pratico o lavorativo, per indicare che una donna è libera da impegni o pronta a collaborare (es. lavorativamente, logisticamente). Include anche la disponibilità di un oggetto o servizio. La gestazione per altri è inclusa in questa categoria.  
    es. "La dottoressa sarà disponibile per ricevervi mercoledì mattina."  

**2 → Sessuale/dispregiativo**: uso generalmente con connotazione negativa o sessista, implicando che la donna si concede facilmente ai rapporti amorosi/sessuali o è percepita come tale. Include i servizi di escort, il sex work e una generica disponibilità verso rapporti amorosi/sessuali.
    es. "Era una donna molto disponibile, con chiunque volesse farle un po' di compagnia..."  

**3 → Figurato/positivo**: uso figurato in senso positivo, per indicare apertura mentale, flessibilità, accoglienza, disponibilità all'ascolto o al confronto.  
    es. "Maria è una persona disponibile al dialogo, sempre pronta ad ascoltare senza giudicare."

**4 → Aggettivo non riferito a donna**: uso di "disponibile" non riferito alla donna, per indicare disponibilità generica di oggetti o servizi.  
    es. "Ecco il nuovo maglione per donne disponibile dal 4 marzo"
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
        annotator = lower_input
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

st.title("Annotazione: significato di «donna disponibile» (categorie 1-4)")

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
    st.success("Annotazione terminata. Grazie!")
    st.stop()

 # display progress of all annotators
st.markdown(f"**Annotazioni già effettuate da tutti gli annotatori**: {done_count} / {total_count}")
# display progress of current annotator in this session
remaining = len(st.session_state.todo_df)
current_index = st.session_state.pointer + 1
st.markdown(f"**Frase corrente da annotare**: {current_index} / {remaining}")

if df.empty:
    st.success("Tutte le frasi sono state annotate. Grazie!")
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
