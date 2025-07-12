import re
import pandas as pd

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
train_df = df.sample(n=100, random_state=42).reset_index(drop=True)
# usa gli indici rimanenti per il test set
test_df  = df.drop(train_df.index).reset_index(drop=True)

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
    missing = set(diff_sentences) - set(train_df["sentence"].astype(str))
    if missing:
        print("Le seguenti frasi mancanti nel training set:")
        for sent in missing:
            print(sent)
    else:
        print("Tutte le frasi da 'diificult_train_sentences_disponibile.csv' sono presenti nel training set.")
except FileNotFoundError:
    print(f"File non trovato: {difficult_file}")