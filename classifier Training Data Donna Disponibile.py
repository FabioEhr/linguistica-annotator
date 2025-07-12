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
SHEET_NAME           = "Training_data_donna_disponibile"
MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "gpt-4o",
    "gpt-4o-mini",
]
SYSTEM_PROMPT = """
Sei un classificatore che assegna ogni frase a una di queste categorie:
1 → Neutro/lavorativo/Pratico: 'disponibile' in senso pratico o lavorativo, per indicare che una donna è libera da impegni o pronta a collaborare (es. lavorativamente, logisticamente). Include anche la disponibilità di un oggetto o servizio.
2 → Sessuale/dispregiativo: uso generalmente con connotazione negativa o sessista, implicando che la donna si concede facilmente ai rapporti amorosi/sessuali o è percepita come tale.
3 → Figurato/positivo: uso figurato in senso positivo, per indicare apertura mentale, flessibilità, accoglienza, disponibilità all'ascolto o al confronto.

Rispondi **ESCLUSIVAMENTE** con un JSON UTF-8 valido:
{
  "class": <numero intero tra 1 e 3>
}
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
    m = re.search(r'"?class"?\s*[:=]\s*([1-3])', txt)
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