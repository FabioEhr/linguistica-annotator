import os
import tomli
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import matplotlib.pyplot as plt
from statsmodels.stats.proportion import proportion_confint

# Toggle plotting on/off
ENABLE_PLOTS = True
ENABLE_PLOTS_CONFUSION = True
# --- Confusion matrix imports ---
from sklearn.metrics import confusion_matrix
import seaborn as sns

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
human_col  = next((i for i,h in enumerate(lower_header) if h == "best_human"), None)
mod4o_col  = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4o"), None)
mod4_1_col = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4_1"), None)
id_col     = next((i for i,h in enumerate(lower_header) if h == "id"), None)
sent_col   = next((i for i,h in enumerate(lower_header) if h == "sentence"), None)
# map additional GPT-4.1 variants and mini GPT-4o column
mod4_1_mini_col = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4_1-mini"), None)
mod4_1_nano_col = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4_1-nano"), None)
mod4o_mini_col  = next((i for i,h in enumerate(lower_header) if h == "mod_gpt-4o-mini"), None)

# Build DataFrame and extract labels/predictions for all plotting
df = pd.DataFrame(rows, columns=header)
human = df.iloc[:, human_col]
models = {
    "gpt-4.1":     df.iloc[:, mod4_1_col],
    "gpt-4.1-mini": df.iloc[:, mod4_1_mini_col],
    "gpt-4.1-nano": df.iloc[:, mod4_1_nano_col],
    "gpt-4o":      df.iloc[:, mod4o_col],
    "gpt-4o-mini":  df.iloc[:, mod4o_mini_col],
}

# --- Compute and plot agreement percentages and cost ---
if ENABLE_PLOTS:
    # --- Compute per-class agreement for each model ---
    # human labels and model predictions are strings; define class labels
    # class_labels = sorted(set(human))
    # Initialize a DataFrame to hold per-class agreement
    per_class_df = pd.DataFrame(index=sorted(set(human)), columns=list(models.keys()), dtype=float)

    # Compute agreement per class
    for cls in per_class_df.index:
        mask = human == cls
        total = mask.sum()
        for model_name in models.keys():
            correct = ((models[model_name] == human) & mask).sum()
            per_class_df.at[cls, model_name] = (correct / total * 100) if total > 0 else None

    # Print per-class agreement
    print("\nPer-class agreement (%) by model:")
    print(per_class_df)

    # ---- Per‑class 90 % Wilson lower bounds (one‑sided) ----
    lower_bounds_df = pd.DataFrame(index=per_class_df.index,
                                   columns=per_class_df.columns,
                                   dtype=float)

    for cls in per_class_df.index:
        mask = human == cls
        total = mask.sum()
        for model_name, series in models.items():
            count = ((series == human) & mask).sum()
            # Wilson one‑sided lower bound (equivalent to 95 % two‑sided lower)
            lb, _ = proportion_confint(count, total,
                                       alpha=0.10,  # 90 % one‑sided
                                       method="wilson")
            lower_bounds_df.at[cls, model_name] = lb * 100  # as %
    print("\nPer‑class 90% Wilson lower bound (%) by model:")
    print(lower_bounds_df)

    # Calculate percentage agreement for each model
    agreement = {name: (series == human).mean() * 100 for name, series in models.items()}
    # Cost per million tokens for each model
    costs = {
        "gpt-4.1":      2.00,
        "gpt-4.1-mini": 0.40,
        "gpt-4.1-nano": 0.10,
        "gpt-4o":       2.50,
        "gpt-4o-mini":  0.15,
    }

    # Prepare data for plotting
    names = list(agreement.keys())
    acc_values = [agreement[n] for n in names]
    cost_values = [costs[n] for n in names]

    # Compute Wilson lower bounds (95% one-sided) for agreement
    n = len(human)
    lower_bounds = {}
    for name, series in models.items():
        count = (series == human).sum()
        # Get only the lower bound with alternative='larger'
        lb, _ = proportion_confint(count, n, alpha=0.10, method="wilson")
        lower_bounds[name] = lb * 100  # convert to percentage

    # Plot agreement as bars
    fig, ax1 = plt.subplots(figsize=(10, 6))
    # Plot agreement bars and capture BarContainer
    bars = ax1.bar(names, acc_values, label="Agreement (%)")
    # Annotate each bar with its agreement percentage and 95% Wilson lower bound
    for bar, name in zip(bars, names):
        height = bar.get_height()
        lb = lower_bounds.get(name, 0)
        ax1.annotate(f"{height:.1f}% ({lb:.1f}%)",
                     xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3),  # 3 points vertical offset
                     textcoords="offset points",
                     ha='center', va='bottom')
    ax1.set_ylabel("Agreement (%)")
    ax1.set_xlabel("Model")
    ax1.set_title("Model Agreement and Cost per Million Tokens")
    ax1.tick_params(axis="x", rotation=45)

    # Dashed line at 100% accuracy
    ax1.axhline(100, linestyle='--', color='grey')

    # Plot cost on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(names, cost_values, marker="o", linestyle="--", color="orange", label="Cost ($/M tokens)")
    ax2.set_ylabel("Cost ($/M tokens)")

    # Annotate cost values above each point
    #for x, y in zip(names, cost_values):
        #ax2.annotate(f"${y:.2f}", xy=(x, y), xytext=(0, 6),
         #            textcoords="offset points", ha="center", va="bottom")

    # Combine legend entries from both axes into one
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    plt.tight_layout()
    plt.show()
# end of agreement & cost plotting

# --- Agreement of other models relative to GPT-4.1 ---
if ENABLE_PLOTS:
    # Convert GPT-4.1 outputs to numeric
    ref_series = pd.to_numeric(models["gpt-4.1"], errors="coerce")
    agreement_vs_ref = {}
    for name, series in models.items():
        # convert and align
        series_int = pd.to_numeric(series, errors="coerce")
        valid = series_int.notna() & ref_series.notna()
        agreement_vs_ref[name] = (series_int[valid] == ref_series[valid]).mean() * 100

    # Plot agreement vs GPT-4.1
    plt.figure(figsize=(8, 4))
    plt.bar(agreement_vs_ref.keys(), agreement_vs_ref.values())
    plt.ylabel("Agreement with GPT-4.1 (%)")
    plt.title("Model Agreement Relative to GPT-4.1")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.show()
# end of agreement vs GPT-4.1 plotting

# --- Plot confusion matrices per model ---
if ENABLE_PLOTS:
    for model_name, series in models.items():
        # Safely convert to numeric, dropping invalid entries
        human_int = pd.to_numeric(human, errors='coerce')
        series_int = pd.to_numeric(series, errors='coerce')
        valid = human_int.notna() & series_int.notna()
        y_true = human_int[valid].astype(int)
        y_pred = series_int[valid].astype(int)
        # Determine numeric class labels present in this valid subset
        labels_int = sorted(y_true.unique())
        # Compute raw confusion counts
        cm_counts = confusion_matrix(y_true, y_pred, labels=labels_int)
        # Normalize by row sums to get percentages
        cm = cm_counts.astype(float)
        row_sums = cm.sum(axis=1, keepdims=True)
        cm = (cm / row_sums) * 100
        # Plot normalized heatmap
        plt.figure(figsize=(6, 5))
        sns.heatmap(
            cm,
            annot=True,
            fmt=".1f",
            xticklabels=labels_int,
            yticklabels=labels_int,
            cmap="Reds",
            vmin=0, vmax=100
        )
        plt.ylabel("Gold label")
        plt.xlabel("Model prediction")
        plt.title(f"Confusion Matrix: {model_name}")
        plt.tight_layout()
        plt.show()
# end of confusion matrices per model

# --- Plot confusion matrices relative to GPT-4.1 ---
if ENABLE_PLOTS:
    # Reference series for GPT-4.1
    ref_series = pd.to_numeric(models["gpt-4.1"], errors="coerce")
    for model_name, series in models.items():
        if model_name == "gpt-4.1":
            continue
        # Convert both to numeric
        series_int = pd.to_numeric(series, errors="coerce")
        # Align valid entries
        valid = ref_series.notna() & series_int.notna()
        y_ref = ref_series[valid].astype(int)
        y_pred = series_int[valid].astype(int)
        # Determine all labels present
        labels_int = sorted(set(y_ref.unique()) | set(y_pred.unique()))
        # Compute raw confusion counts
        cm_counts = confusion_matrix(y_ref, y_pred, labels=labels_int)
        # Normalize rows to percentages
        cm = cm_counts.astype(float)
        row_sums = cm.sum(axis=1, keepdims=True)
        cm = (cm / row_sums) * 100
        # Plot normalized heatmap
        plt.figure(figsize=(6, 5))
        sns.heatmap(
            cm,
            annot=True,
            fmt=".1f",
            xticklabels=labels_int,
            yticklabels=labels_int,
            cmap="Blues",
            vmin=0,
            vmax=100
        )
        plt.ylabel("GPT-4.1 label")
        plt.xlabel("Model prediction")
        plt.title(f"Confusion Matrix: {model_name} vs GPT-4.1")
        plt.tight_layout()
        plt.show()
# end of confusion matrices vs GPT-4.1

# --- Sentences where GPT-4.1, GPT-4o, and Human do not all agree ---
# Create a boolean mask for disagreement among the three
mask = (
    (models["gpt-4.1"] != models["gpt-4o"]) |
    (models["gpt-4.1"] != human) |
    (models["gpt-4o"] != human)
)
disagree_df = df[mask]

# print("\nSentences where GPT-4.1, GPT-4o, and human disagree:")
# for idx, row in disagree_df.iterrows():
#     sent = row[df.columns[sent_col]]
#     gid = row[df.columns[id_col]] if id_col is not None else idx
#     print(f"[{gid}] {sent}")
#     print(f" - GPT-4.1: {row[df.columns[mod4_1_col]]}")
#     print(f" - GPT-4o:   {row[df.columns[mod4o_col]]}")
#     print(f" - Human:    {row[df.columns[human_col]]}")
#     print("-" * 50)

# --- Also write disagreement sentences to a text file ---
output_path = "disagreement_sentences.txt"
with open(output_path, "w", encoding="utf-8") as f:
    f.write("Sentences where GPT-4.1, GPT-4o, and human disagree:\n")
    for idx, row in disagree_df.iterrows():
        sent = row[df.columns[sent_col]]
        gid = row[df.columns[id_col]] if id_col is not None else idx
        f.write(f"[{gid}] {sent}\n")
        f.write(f" - GPT-4.1: {row[df.columns[mod4_1_col]]}\n")
        f.write(f" - GPT-4o:   {row[df.columns[mod4o_col]]}\n")
        f.write(f" - Human:    {row[df.columns[human_col]]}\n")
        f.write("-" * 50 + "\n")
print(f"\nDisagreement sentences also saved to {output_path}")

# --- Three confusion matrices side by side (1×3) ---
if ENABLE_PLOTS_CONFUSION:
    # Mapping numeric labels to English descriptions
    label_map = {
        1: "Practical",
        2: "Sexual \n Derogatory",
        3: "Figurative \n Positive",
        4: "Not referred \n to woman"
    }
    # Define the three pairs: (reference, prediction)
    pairs = [
        ("best_human", "gpt-4o"),
        ("gpt-4.1",    "gpt-4o"),
        ("best_human", "gpt-4.1"),
    ]
    # Create 1x3 subplot with gridspec_kw for spacing and margins
    fig, axes = plt.subplots(
        1, 3,
        figsize=(18, 6),
        gridspec_kw={'wspace': 0.6, 'left': 0.05, 'right': 0.98}
    )
    # adjust layout to accommodate title and colorbar
    fig.subplots_adjust(top=0.85, bottom=0.15)
    # Add a single title above all subplots
    fig.suptitle("Confusion Matrix", fontsize=18)
    for ax, (ref_name, pred_name) in zip(axes, pairs):
        # Select reference series
        if ref_name == "best_human":
            ref_series = pd.to_numeric(human, errors="coerce")
        else:
            ref_series = pd.to_numeric(models[ref_name], errors="coerce")
        # Select prediction series
        if pred_name == "best_human":
            pred_series = pd.to_numeric(human, errors="coerce")
        else:
            pred_series = pd.to_numeric(models[pred_name], errors="coerce")
        # Filter valid entries
        valid = ref_series.notna() & pred_series.notna()
        y_ref = ref_series[valid].astype(int)
        y_pred = pred_series[valid].astype(int)
        # Determine label set
        labels_int = sorted(set(y_ref.unique()) | set(y_pred.unique()))
        # Compute raw counts
        cm_counts = confusion_matrix(y_ref, y_pred, labels=labels_int)
        # Normalize each row to percentages
        cm = cm_counts.astype(float)
        row_sums = cm.sum(axis=1, keepdims=True)
        cm = (cm / row_sums) * 100
        # Build annotation labels showing count and percentage
        annotations = [
            [
                f"{int(cm_counts[i, j])}"
                for j in range(len(labels_int))
            ]
            for i in range(len(labels_int))
        ]
        # Plot normalized heatmap with counts and percentages
        sns.heatmap(
            cm,
            annot=annotations,
            fmt="",
            xticklabels=[label_map[i] for i in labels_int],
            yticklabels=[label_map[i] for i in labels_int],
            cmap="Blues",
            vmin=0,
            vmax=100,
            cbar=False,
            ax=ax
        )
        # Adjust tick label font sizes and increase label padding
        ax.tick_params(axis='x', labelsize=8, pad=8)
        ax.tick_params(axis='y', labelsize=8, pad=8)
        # Center-align y-axis tick labels
        for tick in ax.get_yticklabels():
            tick.set_ha('center')
        #ax.set_title(f"{ref_name} vs {pred_name}")
        if ref_name == "best_human":
            ax.set_ylabel("Human annotator", fontsize=14, labelpad=15)
        else:
            ax.set_ylabel(ref_name, fontsize=14, labelpad=15)
        ax.set_xlabel(pred_name, fontsize=14, labelpad=15)

    # increase horizontal space between subplots
    # fig.subplots_adjust(wspace=5)  # (removed, only set spacing below)

    # add a single shared colorbar below all three plots
    import matplotlib as mpl
    sm = mpl.cm.ScalarMappable(
        cmap="Blues",
        norm=mpl.colors.Normalize(vmin=0, vmax=100)
    )
    sm.set_array([])  # needed for colorbar
    cbar = fig.colorbar(
        sm,
        ax=axes.ravel().tolist(),
        orientation="horizontal",
        fraction=0.05,
        pad=0.2
    )
    cbar.set_label("Percentage (%)")
    # fig.subplots_adjust(wspace=3.0)  # removed as per instruction
    # adjust layout to make room for title and colorbar
    #plt.tight_layout(rect=[0, 0.2, 1, 1])
    plt.show()