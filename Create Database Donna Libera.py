import re
import pandas as pd

# --- 1. Carica e parsifica il file di concordanze --------------------------
records = []
with open("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/concordance_preloaded_trends_it_20250625112515.txt", "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        # ogni riga è: YYYY-MM-DD | testo...
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\s*\|\s*(.+)$', line)
        if m:
            date_str, sentence = m.groups()
            # rimuovi eventuali tag <coll> e </s>
            sentence = re.sub(r"</?s>", " ", sentence)
            sentence = re.sub(r"</?coll>", "", sentence)
            records.append({
                "date": date_str,
                "sentence": sentence.strip()
            })

df = pd.DataFrame(records)
# opzionale: ordina cronologicamente
df["date"] = pd.to_datetime(df["date"], errors="coerce")
df = df.sort_values("date").reset_index(drop=True)

# --- 2. Suddividi in training (200 esempi) e test (800 esempi) -------------
train_df = df.sample(n=200, random_state=42).reset_index(drop=True)
# estrai i rimanenti e poi campiona 800 frasi per il test set
remaining_df = df.drop(train_df.index).reset_index(drop=True)
test_df = remaining_df.sample(n=800, random_state=42).reset_index(drop=True)

# --- 3. Esporta su CSV ------------------------------------------------------
train_df.to_csv("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/train_sentences_libera.csv", index=False, encoding="utf-8")
test_df.to_csv("/Users/Fabio/Documents/Programmi Utili/Collegio Superiore/Linguistica/rest_sentences_libera.csv",  index=False, encoding="utf-8")

print(f"Training set: {len(train_df)} frasi salvate in train_sentences_libera.csv")
print(f"Test set:     {len(test_df)} frasi salvate in rest_sentences_libera.csv")
