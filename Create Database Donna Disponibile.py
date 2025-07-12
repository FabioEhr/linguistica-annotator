import re
import pandas as pd
from difflib import get_close_matches

# Utility: normalizza spazi bianchi multipli e trimma
def normalize(s: str) -> str:
    # collapse multiple whitespace into single spaces and trim
    return re.sub(r"\s+", " ", s).strip()

# --- 1. Carica e parsifica il file di concordanze --------------------------
records = []
with open("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/Disponibile_concordance_preloaded_trends_it_20250625092858.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        # ogni riga è: YYYY-MM-DD | testo...
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)$', line)
        if m:
            date_str, sentence = m.groups()
            # rimuovi eventuali tag <s> e </coll>
            sentence = re.sub(r"</?s>", " ", sentence)
            sentence = re.sub(r"</?coll>", "", sentence)
            records.append({
                "date": date_str,
                "sentence": sentence.strip()
            })

df = pd.DataFrame(records)
# df["date"] = pd.to_datetime(df["date"], errors="coerce")

# --- 2. Suddividi in training (100 esempi) e restante ------------------------
# campiona mantenendo gli indici originali
train_df = df.sample(n=100, random_state=42)
# test set = righe non campionate
test_df  = df.drop(train_df.index)

# resetta gli indici dei DataFrame per l'export
train_df = train_df.reset_index(drop=True)
test_df  = test_df.reset_index(drop=True)

# --- 3. Esporta su CSV ------------------------------------------------------
train_df.to_csv("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/train_sentences_disponibile.csv",
                index=False, encoding="utf-8")
test_df.to_csv("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/rest_sentences_disponibile.csv",
               index=False, encoding="utf-8")

print(f"Training set: {len(train_df)} frasi salvate in train_sentences_disponibile.csv")
print(f"Test set:     {len(test_df)} frasi salvate in rest_sentences_disponibile.csv")

# --- 4. Verifica presenza delle frasi da diificult_train_sentences_disponibile.csv ---
difficult_file = "/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/diificult_train_sentences_disponibile.csv"
try:
    diff_df = pd.read_csv(difficult_file, encoding="utf-8")
    if "sentence" in diff_df.columns:
        diff_sentences = diff_df["sentence"].astype(str)
    else:
        diff_sentences = diff_df.iloc[:, -1].astype(str)
    # normalize whitespace in both sets
    train_norm = [normalize(x) for x in train_df["sentence"].astype(str)]
    diff_norm  = [normalize(x) for x in diff_sentences]
    missing = set(diff_norm) - set(train_norm)
    if missing:
        print(f"Numero di frasi mancanti: {len(missing)}")
        print("Le seguenti frasi (normalize) mancanti nel training set:")
        for norm_sent in missing:
            print(f"\nMancante (normalizzata): {norm_sent}")
            # suggerimenti basati su stringhe normalizzate
            suggestions = get_close_matches(norm_sent, train_norm, n=3, cutoff=0.6)
            if suggestions:
                print("  Possibili corrispondenze normalizzate:")
                for s in suggestions:
                    print(f"    - {s}")
    else:
        print("Tutte le frasi da 'diificult_train_sentences_disponibile.csv' sono presenti nel training set.")
    # --- Verifica se le frasi difficult compaiono nel test set -------------
    test_norm = [normalize(x) for x in test_df["sentence"].astype(str)]
    present_in_test = set(diff_norm) & set(test_norm)
    if present_in_test:
        print("\nLe seguenti frasi difficult sono presenti nel test set (normalized):")
        for norm_sent in present_in_test:
            print(f"\nTrovata (normalizzata): {norm_sent}")
            # suggerimenti per corrispondenti nel test set
            suggestions = get_close_matches(norm_sent, test_norm, n=3, cutoff=0.6)
            if suggestions:
                print("  Possibili corrispondenze nel test set (normalized):")
                for s in suggestions:
                    print(f"    - {s}")
    else:
        print("\nNessuna frase difficult trovata nel test set.")
except FileNotFoundError:
    print(f"File non trovato: {difficult_file}")