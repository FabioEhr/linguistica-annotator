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
2 → Sessuale/dispregiativo: uso generalmente con connotazione negativa o sessista, implicando che la donna si concede facilmente ai rapporti amorosi/sessuali o è percepita come tale. Include i servizi di escort, il sex work e una generica disponibilità verso rapporti amorosi/sessuali.
3 → Figurato/positivo: uso figurato in senso positivo, per indicare apertura mentale, flessibilità, accoglienza, disponibilità all'ascolto o al confronto.

Rispondi **ESCLUSIVAMENTE** con un JSON UTF-8 valido:
{
  "class": <numero intero tra 1 e 3>
}

Esempi:
Input: "La dottoressa sarà disponibile per ricevervi mercoledì mattina."
Output: {"class": 1}

Input: "Era una donna molto disponibile, con chiunque volesse farle un po' di compagnia..."
Output: {"class": 2}

Input: "Maria è una persona disponibile al dialogo, sempre pronta ad ascoltare senza giudicare."
Output: {"class": 3}
"""
SYSTEM_PROMPT3 = """
Sei un classificatore che assegna ogni frase a una di queste categorie:
1 → Neutro/lavorativo/Pratico: 'disponibile' in senso pratico o lavorativo, per indicare che una donna è libera da impegni o pronta a collaborare (es. lavorativamente, logisticamente). Include anche la disponibilità di un oggetto o servizio. Include la gestazione per altri.
2 → Sessuale/dispregiativo: uso generalmente con connotazione negativa o sessista, implicando che la donna si concede facilmente ai rapporti amorosi/sessuali o è percepita come tale. Include i servizi di escort, il sex work e una generica disponibilità verso rapporti amorosi/sessuali.
3 → Figurato/positivo: uso figurato in senso positivo, per indicare apertura mentale, flessibilità, accoglienza, disponibilità all'ascolto o al confronto.

Rispondi **ESCLUSIVAMENTE** con un JSON UTF-8 valido:
{
  "class": <numero intero tra 1 e 3>
}
"""

SYSTEM_PROMPT4 = """
Sei un classificatore che assegna ogni frase a una di queste categorie:
1 → Neutro/lavorativo/Pratico: 'disponibile' in senso pratico o lavorativo, per indicare che una donna è libera da impegni o pronta a collaborare (es. lavorativamente, logisticamente). Include la gestazione per altri.
2 → Sessuale/dispregiativo: uso generalmente con connotazione negativa o sessista, implicando che la donna si concede facilmente ai rapporti amorosi/sessuali o è percepita come tale. Include i servizi di escort, il sex work e una generica disponibilità verso rapporti amorosi/sessuali.
3 → Figurato/positivo: uso figurato in senso positivo, per indicare apertura mentale, flessibilità, accoglienza, disponibilità all'ascolto o al confronto.
4 → Aggettivo non riferito a “donna”: uso di “disponibile” riferito a oggetti o servizi

Rispondi **ESCLUSIVAMENTE** con un JSON UTF-8 valido:
{
  "class": <numero intero tra 1 e 4>
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
    base = mdl.replace(".", "_")
    new_col = f"mod3_{base}"
    if new_col not in header:
        header.append(new_col)
        ws.update_cell(1, len(header), new_col)

# --- Prepara le colonne per la quarta classificazione (mod4) ---
header = ws.row_values(1)
for mdl in MODELS:
    base = mdl.replace(".", "_")
    new_col4 = f"mod4_{base}"
    if new_col4 not in header:
        header.append(new_col4)
        ws.update_cell(1, len(header), new_col4)


# ricava nuovamente colonne e mappa nome→indice
header = ws.row_values(1)
col_index = {name: idx+1 for idx, name in enumerate(header)}

# --- Funzione di classificazione -------------------------------------------
def classify_with_model(sentence: str, model_name: str) -> int:
    resp = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system",  "content": SYSTEM_PROMPT3},
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
    first_model_col = f"mod3_{MODELS[0].replace('.', '_')}"
    if row[col_index[first_model_col]-1].strip():
        continue

    # per ciascun modello
    for mdl in MODELS:
        base = mdl.replace(".", "_")
        col_name = f"mod3_{base}"
        cls = classify_with_model(sentence, mdl)
        # scrivi subito in cella (puoi anche accumulare e batch-aggiornare)
        ws.update_cell(row_idx, col_index[col_name], str(cls))
        time.sleep(0.3)  # per non superare rate limit


# --- Quarta classificazione: usa SYSTEM_PROMPT4 e popola mod4 col ---
print("Starting fourth classification run (mod4)...")
for row_idx, row in enumerate(tqdm(all_rows, desc="Classifying mod4"), start=2):
    sentence = row[header.index("sentence")]
    first_mod4 = f"mod4_{MODELS[0].replace('.', '_')}"
    if row[col_index[first_mod4]-1].strip():
        continue
    for mdl in MODELS:
        base = mdl.replace(".", "_")
        col4 = f"mod4_{base}"
        resp = client.chat.completions.create(
            model=mdl,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT4},
                {"role": "user",   "content": sentence}
            ],
            temperature=0,
            max_tokens=10,
            top_p=1,
            response_format={"type": "json_object"}
        )
        txt4 = resp.choices[0].message.content.strip()
        # estrai classe (1-4)
        m4 = re.search(r'"?class"?\s*[:=]\s*([1-4])', txt4)
        cls4 = int(m4.group(1)) if m4 else None
        if cls4 is None:
            try:
                cls4 = int(json.loads(txt4)["class"])
            except:
                cls4 = None
        ws.update_cell(row_idx, col_index[col4], str(cls4))
        time.sleep(0.3)

