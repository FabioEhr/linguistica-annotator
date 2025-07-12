import re
import json
import time
import os
import tomli
import gspread
from google.oauth2.service_account import Credentials
from openai import OpenAI
from tqdm import tqdm

# --- Configurazione ---------------------------------------------------------
# SERVICE_ACCOUNT_FILE = "/percorso/al/tuo/service_account.json"
SHEET_NAME = "Training_data_donna_libera"
MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]
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

# --- Setup OpenAI e Google Sheets ------------------------------------------
# 1) ChatGPT client
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise RuntimeError("Devi esportare OPENAI_API_KEY nell'ambiente")
client = OpenAI(api_key=openai_api_key)

# 2) Google Sheets client
scopes = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]
# Load Google service account JSON from Streamlit secrets.toml
secrets_path = os.path.expanduser("~/Documents/Programmi Utili/Collegio Superiore/Linguistica/.streamlit/secrets.toml")
with open(secrets_path, "rb") as f:
    toml_data = tomli.load(f)
service_account_info = toml_data["gcp_service_account"]
creds = Credentials.from_service_account_info(service_account_info, scopes=scopes)
gc = gspread.authorize(creds)
ws = gc.open(SHEET_NAME).sheet1

# --- Prepara la colonna per ciascun modello --------------------------------
header = ws.row_values(1)
for mdl in MODELS:
    col_name = mdl.replace(".", "_")  # es: gpt-4_1
    if col_name not in header:
        header.append(col_name)
        ws.update_cell(1, len(header), col_name)

# ricava nuovamente colonne e mappa nome→indice
header = ws.row_values(1)
col_index = {name: idx+1 for idx, name in enumerate(header)}

# determina colonne di annotazione manuale (escludi id, date, sentence e modelli)
static_cols = ["id", "date", "sentence"] + [mdl.replace(".", "_") for mdl in MODELS]
annotation_cols = [h for h in header if h not in static_cols]

# --- Funzione di classificazione -------------------------------------------
def classify_with_model(sentence: str, model_name: str) -> int:
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system",  "content": SYSTEM_PROMPT},
            {"role": "user",    "content": sentence}
        ],
        temperature=0,
        max_tokens=10,
        top_p=1,
        response_format={"type": "json_object"}
    )
    txt = resp.choices[0].message.content.strip()
    m = re.search(r'"?class"?\s*[:=]\s*([1-6])', txt)
    if m:
        return int(m.group(1))
    try:
        return int(json.loads(txt)["class"])
    except:
        return None

# --- Itera su tutte le frasi e riempi le colonne ----------------------------
all_rows = ws.get_all_values()[1:]  # esclude header
print(f"Totale frasi da processare: {len(all_rows)}")

for row_idx, row in enumerate(tqdm(all_rows, desc="Classifying"), start=2):
    # skip righe senza annotazione manuale
    if not any(row[header.index(col)].strip() for col in annotation_cols):
        continue
    sentence = row[header.index("sentence")]  # presuppone colonna "sentence"
    # salta se già classificate (ad es. first model già presente)
    first_model_col = MODELS[0].replace(".", "_")
    if row[col_index[first_model_col]-1].strip():
        continue

    # per ciascun modello
    for mdl in MODELS:
        col_name = mdl.replace(".", "_")
        cls = classify_with_model(sentence, mdl)
        # scrivi subito in cella (puoi anche accumulare e batch-aggiornare)
        ws.update_cell(row_idx, col_index[col_name], str(cls))
        time.sleep(0.3)  # per non superare rate limit