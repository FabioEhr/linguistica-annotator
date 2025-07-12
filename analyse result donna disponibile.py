import os
import tomli
import gspread
from google.oauth2.service_account import Credentials

# --- Configurazione ---------------------------------------------------------
SHEET_NAME   = "Training_data_donna_disponibile"
SECRETS_PATH = os.path.expanduser(
    "~/Documents/Programmi Utili/Collegio Superiore/Linguistica/.streamlit/secrets.toml"
)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
          "https://www.googleapis.com/auth/drive"]

# --- Autenticazione e apertura sheet ----------------------------------------
with open(SECRETS_PATH, "rb") as f:
    secrets = tomli.load(f)
creds = Credentials.from_service_account_info(secrets["gcp_service_account"], scopes=SCOPES)
gc    = gspread.authorize(creds)
ws    = gc.open(SHEET_NAME).sheet1

# --- Lettura header + dati --------------------------------------------------
header = ws.row_values(1)
rows   = ws.get_all_values()[1:]  # esclude l’header

# mappa header→indice case-insensitive
lower_header = [h.lower() for h in header]
fabio_col  = next((i for i,h in enumerate(lower_header) if h == "fabio"), None)
mod4o_col  = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4o"), None)
mod4_1_col = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4_1"), None)
id_col     = next((i for i,h in enumerate(lower_header) if h == "id"), None)
sent_col   = next((i for i,h in enumerate(lower_header) if h == "sentence"), None)

print("Rilevate le seguenti discrepanze tra Fabio e mod_gpt-4o/mod_gpt-4_1:\n")
for row_idx, r in enumerate(rows, start=2):
    # se Fabio non ha etichettato, salta
    fabio = r[fabio_col].strip() if fabio_col is not None else ""
    if not fabio:
        continue

    mod4o  = r[mod4o_col].strip()  if mod4o_col  is not None else ""
    mod4_1 = r[mod4_1_col].strip() if mod4_1_col is not None else ""

    diff_4o  = mod4o  and fabio != mod4o
    diff_4_1 = mod4_1 and fabio != mod4_1
    if diff_4o or diff_4_1:
        # id e frase fallback a row_idx o a intera riga se mancano colonne
        id_val = r[id_col].strip() if id_col is not None else str(row_idx)
        sent_val = r[sent_col].strip() if sent_col is not None else ""
        print(f"ID {id_val} (riga {row_idx}):\n  Frase: {sent_val}")
        print(f"  Fabio      → {fabio}")
        if diff_4o:  print(f"  mod_gpt-4o  → {mod4o}")
        if diff_4_1: print(f"  mod_gpt-4_1 → {mod4_1}")
        print("-" * 60)