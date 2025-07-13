import os
import tomli
import gspread
from google.oauth2.service_account import Credentials

# --- Configurazione ---------------------------------------------------------
SHEET_NAME   = "test data donna disponibile"
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
# map third classification columns (match any header with mod3 and model)
mod3_4o_col  = next((i for i,h in enumerate(lower_header) if "mod3" in h and "gpt-4o" in h), None)
mod3_4_1_col = next((i for i,h in enumerate(lower_header) if "mod3" in h and "gpt-4_1" in h), None)

# map additional annotator and mod4 columns
fabio2_col   = next((i for i,h in enumerate(lower_header) if h == "fabio2"), None)
monica_col   = next((i for i,h in enumerate(lower_header) if h == "monica"), None)
mod4_4o_col  = next((i for i,h in enumerate(lower_header) if h == "mod4_gpt-4o"), None)
mod4_4_1_col = next((i for i,h in enumerate(lower_header) if h == "mod4_gpt-4_1"), None)

print("Rilevate le seguenti discrepanze tra Fabio e mod_gpt-4o/mod_gpt-4_1/mod3_chat_gpt-4o/mod3_chat_gpt-4_1:\n")
for row_idx, r in enumerate(rows, start=2):
    # se Fabio non ha etichettato, salta
    fabio = r[fabio_col].strip() if fabio_col is not None else ""
    if not fabio:
        continue

    mod4o  = r[mod4o_col].strip()  if mod4o_col  is not None else ""
    mod4_1 = r[mod4_1_col].strip() if mod4_1_col is not None else ""
    mod3_4o  = r[mod3_4o_col].strip()  if mod3_4o_col  is not None else ""
    mod3_4_1 = r[mod3_4_1_col].strip() if mod3_4_1_col is not None else ""

    diff_4o  = mod4o  and fabio != mod4o
    diff_4_1 = mod4_1 and fabio != mod4_1
    diff_3_4o  = mod3_4o  and fabio != mod3_4o
    diff_3_4_1 = mod3_4_1 and fabio != mod3_4_1
    if diff_4o or diff_4_1 or diff_3_4o or diff_3_4_1:
        # id e frase fallback a row_idx o a intera riga se mancano colonne
        id_val = r[id_col].strip() if id_col is not None else str(row_idx)
        sent_val = r[sent_col].strip() if sent_col is not None else ""
        print(f"ID {id_val} (riga {row_idx}):\n  Frase: {sent_val}")
        print(f"  Fabio      → {fabio}")
        if diff_4o:  print(f"  mod_gpt-4o  → {mod4o}")
        if diff_4_1: print(f"  mod_gpt-4_1 → {mod4_1}")
        if diff_3_4o:  print(f"  mod3_chat_gpt-4o → {mod3_4o}")
        if diff_3_4_1: print(f"  mod3_chat_gpt-4_1 → {mod3_4_1}")
        print("-" * 60)

# --- Confronto multi-annotator mod4 vs Fabio2 & Monica --------------------
print("\nDiscrepanze tra Fabio2, Monica, mod4_gpt-4o, mod4_gpt-4_1:\n")
for row_idx, r in enumerate(rows, start=2):
    # raccogli valori
    fabio2  = r[fabio2_col].strip()   if fabio2_col   is not None else ""
    monica  = r[monica_col].strip()   if monica_col   is not None else ""
    m4o_val = r[mod4_4o_col].strip()  if mod4_4o_col  is not None else ""
    m4_1_val= r[mod4_4_1_col].strip() if mod4_4_1_col is not None else ""
    # se nessuno ha etichettato, salta
    if not any([fabio2, monica, m4o_val, m4_1_val]):
        continue
    # controlla divergenze
    unique_vals = set(x for x in [fabio2, monica, m4o_val, m4_1_val] if x)
    if len(unique_vals) > 1:
        # ottieni id e frase
        id_val = r[id_col].strip()   if id_col   is not None else str(row_idx)
        sent_val = r[sent_col].strip() if sent_col is not None else ""
        print(f"ID {id_val} (riga {row_idx}): {sent_val}")
        # stampa ogni annotazione
        print(f"  Fabio2 → {fabio2}")
        print(f"  Monica → {monica}")
        print(f"  mod4_gpt-4o  → {m4o_val}")
        print(f"  mod4_gpt-4_1 → {m4_1_val}")
        print("-" * 60)