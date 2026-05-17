"""
Data analysis tools shared across the 3 DataAnalyst subagents.
Requires: pip install pandas numpy scipy openpyxl
"""
import os
import io
import re
from pathlib import Path
from langchain_core.tools import tool

try:
    import pandas as pd
    import numpy as np
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

try:
    from scipy import stats as scipy_stats
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

# ── Session state (single DataFrame per server process) ───────────────────────
_session: dict = {
    "df": None,
    "file_path": None,
    "clean_log": [],
    "autosave_path": None,
    # ML engine state
    "mode":       None,   # 'eda' | 'classification' | 'clustering' | 'regression'
    "target":     None,   # target column name
    "encoders":   {},
    "scaler":     None,
    "ml_results": {},
}

_SUPPORTED_EXTS = {".csv", ".xlsx", ".xls", ".json"}

def _data_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    # OBSIDIAN_VAULT_PATH already points to the "AI Data" folder — only append the subfolder
    base = (Path(vault) / "DataAnalyst Agent") if vault \
           else (Path(__file__).parent.parent / "AI Data" / "DataAnalyst Agent")
    base.mkdir(parents=True, exist_ok=True)
    return base

def _reset_session() -> None:
    """Clear all session state — call before each new DataAnalyst crew run."""
    _session["df"] = None
    _session["file_path"] = None
    _session["clean_log"] = []
    _session["autosave_path"] = None
    _session["mode"] = None
    _session["target"] = None
    _session["encoders"] = {}
    _session["scaler"] = None
    _session["ml_results"] = {}


def _need_df() -> str | None:
    if _session["df"] is None:
        return "No dataset loaded. Call load_dataset(file_path) first."
    return None

def _autosave() -> None:
    """Silently save the current DataFrame as a cleaned CSV after every mutation."""
    try:
        if _session["df"] is None:
            return
        src = Path(_session["file_path"] or "dataset.csv")
        out_name = src.stem + "_cleaned.csv"
        out_path = _data_dir() / out_name
        _session["df"].to_csv(out_path, index=False)
        _session["autosave_path"] = str(out_path)
    except Exception:
        pass  # never let autosave break the main operation


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 1 — CLEANER TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def load_dataset(file_path: str) -> str:
    """Load a CSV, Excel (.xlsx/.xls), or JSON file into the analysis session.
    Accepts absolute paths or filenames relative to the DataAnalyst Agent folder."""
    if not PANDAS_OK:
        return "Error: pandas not installed. Run: pip install pandas openpyxl"
    path = Path(file_path)
    if not path.exists():
        path = _data_dir() / file_path
    if not path.exists():
        return f"File not found: {file_path}\nPlace the file in: {_data_dir()}"
    try:
        ext = path.suffix.lower()
        if ext == ".csv":
            df = pd.read_csv(path)
        elif ext in (".xlsx", ".xls"):
            df = pd.read_excel(path)
        elif ext == ".json":
            df = pd.read_json(path)
        else:
            df = pd.read_csv(path)
        _session["df"] = df.copy()
        _session["file_path"] = str(path)
        _session["clean_log"] = [f"Loaded: {path.name}"]
        num_cols = df.select_dtypes(include="number").columns.tolist()
        cat_cols = df.select_dtypes(include="object").columns.tolist()
        missing = int(df.isnull().sum().sum())
        dups = int(df.duplicated().sum())
        return (
            f"✅ Loaded: {path.name}\n"
            f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns\n"
            f"Numeric  ({len(num_cols)}): {', '.join(num_cols[:8])}{'…' if len(num_cols)>8 else ''}\n"
            f"Categorical ({len(cat_cols)}): {', '.join(cat_cols[:8])}{'…' if len(cat_cols)>8 else ''}\n"
            f"Missing values: {missing} ({missing/(df.shape[0]*df.shape[1])*100:.1f}%)\n"
            f"Duplicate rows: {dups}"
        )
    except Exception as e:
        return f"Error loading file: {e}"


@tool
def inspect_data(sample_rows: int = 5) -> str:
    """Show schema (columns, dtypes, null counts) and a sample of rows."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    header = f"{'Column':<32} {'DType':<14} {'Non-Null':>8}  {'Null%':>6}  {'Unique':>7}"
    sep = "─" * 72
    rows = []
    for col in df.columns:
        null_n = int(df[col].isnull().sum())
        null_pct = null_n / len(df) * 100
        unique = int(df[col].nunique())
        rows.append(f"{col:<32} {str(df[col].dtype):<14} {len(df)-null_n:>8}  {null_pct:>6.1f}  {unique:>7}")
    sample = f"\n── Sample ({sample_rows} rows) ──\n{df.head(sample_rows).to_string()}"
    return f"── Schema ({df.shape[0]:,}×{df.shape[1]}) ──\n{header}\n{sep}\n" + "\n".join(rows) + sample


@tool
def fix_column_names() -> str:
    """Standardize all column names: lowercase, spaces → underscores, strip special chars."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    old = df.columns.tolist()
    new = [re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "_", c.lower().strip())).strip("_") for c in old]
    df.columns = new
    _session["df"] = df
    changed = [(o, n) for o, n in zip(old, new) if o != n]
    msg = f"Renamed {len(changed)} columns:\n" + "\n".join(f"  '{o}' → '{n}'" for o, n in changed) if changed else "Column names already clean."
    _session["clean_log"].append(msg)
    _autosave()
    return msg


@tool
def drop_missing(axis: str = "rows", threshold: float = 0.5) -> str:
    """Drop rows or columns that exceed the missing-value threshold.
    axis: 'rows' or 'columns'. threshold: max allowed fraction of nulls (0–1)."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    before = df.shape
    if axis == "rows":
        min_valid = int((1 - threshold) * df.shape[1])
        df = df.dropna(thresh=min_valid)
    else:
        min_valid = int((1 - threshold) * df.shape[0])
        df = df.dropna(axis=1, thresh=min_valid)
    removed = before[0] - df.shape[0] if axis == "rows" else before[1] - df.shape[1]
    _session["df"] = df
    msg = f"Dropped {removed} {axis} with >{threshold*100:.0f}% nulls. {before} → {df.shape}"
    _session["clean_log"].append(msg)
    _autosave()
    return msg


@tool
def fill_missing(strategy: str = "auto", columns: str = "") -> str:
    """Fill missing values. strategy: 'mean','median','mode','zero','ffill','auto'.
    columns: comma-separated list (empty = all columns)."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    target = [c.strip() for c in columns.split(",") if c.strip()] if columns else df.columns.tolist()
    log, total = [], 0
    for col in target:
        if col not in df.columns: continue
        n = int(df[col].isnull().sum())
        if n == 0: continue
        s = strategy
        if s == "auto":
            s = "median" if pd.api.types.is_numeric_dtype(df[col]) else "mode"
        if s == "mean" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].mean())
        elif s == "median" and pd.api.types.is_numeric_dtype(df[col]):
            df[col] = df[col].fillna(df[col].median())
        elif s == "mode":
            mode_val = df[col].mode()
            df[col] = df[col].fillna(mode_val.iloc[0] if not mode_val.empty else "Unknown")
        elif s == "zero":
            df[col] = df[col].fillna(0)
        elif s == "ffill":
            df[col] = df[col].ffill()
        log.append(f"  {col}: {n} nulls → {s}")
        total += n
    _session["df"] = df
    msg = f"Filled {total} missing values ({len(log)} columns).\n" + "\n".join(log)
    _session["clean_log"].append(msg)
    _autosave()
    return msg


@tool
def remove_duplicates() -> str:
    """Remove duplicate rows from the dataset."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    before = len(df)
    df = df.drop_duplicates()
    removed = before - len(df)
    _session["df"] = df
    msg = f"Removed {removed} duplicate rows. Rows: {before:,} → {len(df):,}"
    _session["clean_log"].append(msg)
    _autosave()
    return msg


@tool
def remove_outliers(columns: str = "", method: str = "iqr", factor: float = 1.5) -> str:
    """Remove outlier rows from numeric columns.
    columns: comma-separated (empty = all numeric). method: 'iqr' or 'zscore'. factor: multiplier."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    num_cols = df.select_dtypes(include="number").columns.tolist()
    target = [c.strip() for c in columns.split(",") if c.strip() in num_cols] if columns else num_cols
    mask = pd.Series(True, index=df.index)
    for col in target:
        if method == "iqr":
            q1, q3 = df[col].quantile(0.25), df[col].quantile(0.75)
            iqr = q3 - q1
            mask &= df[col].between(q1 - factor * iqr, q3 + factor * iqr)
        else:
            z = (df[col] - df[col].mean()) / df[col].std()
            mask &= z.abs() <= factor
    before = len(df)
    df = df[mask]
    removed = before - len(df)
    _session["df"] = df
    msg = f"Removed {removed} outlier rows via {method.upper()} (factor={factor}). Rows: {before:,} → {len(df):,}"
    _session["clean_log"].append(msg)
    _autosave()
    return msg


@tool
def cleaning_log() -> str:
    """Show all data-cleaning operations performed in this session."""
    if not _session["clean_log"]:
        return "No operations yet."
    return "── Cleaning Log ──\n" + "\n".join(f"{i+1}. {op}" for i, op in enumerate(_session["clean_log"]))


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 2 — STATS TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def descriptive_stats() -> str:
    """Full descriptive statistics: mean, std, min/max, quartiles, skewness, kurtosis."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    num = df.select_dtypes(include="number")
    if num.empty:
        return "No numeric columns found."
    desc = num.describe(percentiles=[0.25, 0.5, 0.75]).round(3)
    skew = num.skew().rename("skewness").round(3)
    kurt = num.kurt().rename("kurtosis").round(3)
    result = f"── Descriptive Statistics ({len(num.columns)} numeric cols) ──\n{desc.to_string()}"
    result += f"\nskewness   {dict(skew)}"
    result += f"\nkurtosis   {dict(kurt)}"
    return result


@tool
def correlation_matrix(method: str = "pearson") -> str:
    """Compute full correlation matrix. method: 'pearson' | 'spearman' | 'kendall'."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    num = df.select_dtypes(include="number")
    if num.shape[1] < 2:
        return "Need ≥2 numeric columns."
    corr = num.corr(method=method).round(3)
    return f"── {method.capitalize()} Correlation Matrix ──\n{corr.to_string()}"


@tool
def top_correlations(threshold: float = 0.4, top_n: int = 20) -> str:
    """List the strongest pairwise correlations above the threshold.
    threshold: min absolute value (0–1). top_n: max results."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    num = df.select_dtypes(include="number")
    if num.shape[1] < 2:
        return "Need ≥2 numeric columns."
    corr = num.corr(method="pearson")
    cols = corr.columns.tolist()
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if not (v != v) and abs(v) >= threshold:  # skip NaN
                pairs.append((abs(v), v, cols[i], cols[j]))
    pairs.sort(reverse=True)
    if not pairs:
        return f"No pairs found with |r| ≥ {threshold}."
    header = f"{'Variable A':<28} {'Variable B':<28} {'r':>8}  Strength"
    sep = "─" * 75
    lines = [f"── Top Correlations (|r| ≥ {threshold}) ──", header, sep]
    for _, v, a, b in pairs[:top_n]:
        strength = "STRONG" if abs(v) >= 0.7 else "MODERATE" if abs(v) >= 0.4 else "WEAK"
        direction = "▲ pos" if v > 0 else "▼ neg"
        lines.append(f"{a:<28} {b:<28} {v:>8.3f}  {strength} {direction}")
    return "\n".join(lines)


@tool
def stat_test(col_a: str, col_b: str) -> str:
    """Run statistical significance test between two columns.
    Numeric↔Numeric → Pearson + Spearman. Categorical↔Categorical → Chi-square."""
    err = _need_df()
    if err: return err
    if not SCIPY_OK:
        return "scipy not installed. Run: pip install scipy"
    df = _session["df"]
    for c in (col_a, col_b):
        if c not in df.columns:
            return f"Column '{c}' not found. Available: {', '.join(df.columns[:20])}"
    s1 = df[col_a].dropna()
    s2 = df[col_b].dropna()
    idx = s1.index.intersection(s2.index)
    s1, s2 = df.loc[idx, col_a], df.loc[idx, col_b]
    lines = [f"── Statistical Test: {col_a}  ↔  {col_b}  (N={len(s1)}) ──"]
    num1 = pd.api.types.is_numeric_dtype(df[col_a])
    num2 = pd.api.types.is_numeric_dtype(df[col_b])
    if num1 and num2:
        r_p, p_p = scipy_stats.pearsonr(s1, s2)
        r_s, p_s = scipy_stats.spearmanr(s1, s2)
        lines += [
            f"Pearson   r={r_p:.4f}  p={p_p:.2e}  {'✅ significant' if p_p<0.05 else '❌ not significant'}",
            f"Spearman  ρ={r_s:.4f}  p={p_s:.2e}  {'✅ significant' if p_s<0.05 else '❌ not significant'}",
        ]
        if len(s1) >= 8:
            _, pn1 = scipy_stats.shapiro(s1.head(5000))
            _, pn2 = scipy_stats.shapiro(s2.head(5000))
            lines += [
                f"\nNormality (Shapiro-Wilk):",
                f"  {col_a}: p={pn1:.2e} → {'normal ✅' if pn1>0.05 else 'non-normal ⚠'}",
                f"  {col_b}: p={pn2:.2e} → {'normal ✅' if pn2>0.05 else 'non-normal ⚠'}",
            ]
    else:
        ct = pd.crosstab(s1, s2)
        chi2, p, dof, _ = scipy_stats.chi2_contingency(ct)
        lines += [
            f"Chi-square  χ²={chi2:.4f}  df={dof}  p={p:.2e}  {'✅ significant' if p<0.05 else '❌ not significant'}",
            f"\nContingency table:\n{ct.to_string()}",
        ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
#  SUBAGENT 3 — VISUALIZATION TOOLS
# ═══════════════════════════════════════════════════════════════════════════════

@tool
def generate_viz_code(charts: str = "all") -> str:
    """Generate complete, runnable Python visualization code (matplotlib + seaborn).
    charts: 'all' | 'heatmap' | 'distributions' | 'pairplot' | 'bar' (comma-separated)."""
    err = _need_df()
    if err: return err
    df = _session["df"]
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    fp = _session.get("file_path", "data.csv")
    want = {c.strip() for c in charts.split(",")} | ({"heatmap","distributions","pairplot","bar"} if charts=="all" else set())

    lines = [
        "import pandas as pd",
        "import numpy as np",
        "import matplotlib.pyplot as plt",
        "import seaborn as sns",
        "",
        "# ── Style ───────────────────────────────────────────────────",
        "plt.style.use('dark_background')",
        "sns.set_context('notebook')",
        "PURPLE = '#746fff'",
        "PALETTE = sns.color_palette('husl', 10)",
        "",
        "# ── Load data ───────────────────────────────────────────────",
        f"df = pd.read_csv(r'{fp}')",
        f"NUM = {num_cols}",
        f"CAT = {cat_cols}",
        "",
    ]

    if "heatmap" in want and len(num_cols) >= 2:
        lines += [
            "# ════ Figure 1: Correlation Heatmap ════════════════════",
            "fig, ax = plt.subplots(figsize=(max(8, len(NUM)), max(6, len(NUM)-1)))",
            "corr = df[NUM].corr()",
            "mask = np.triu(np.ones_like(corr, dtype=bool))",
            "sns.heatmap(",
            "    corr, mask=mask, annot=True, fmt='.2f',",
            "    cmap='coolwarm', center=0, square=True, ax=ax,",
            "    linewidths=0.4, cbar_kws={'shrink': 0.8},",
            "    annot_kws={'size': 8},",
            ")",
            "ax.set_title('Pearson Correlation Matrix', fontsize=13, pad=12)",
            "plt.tight_layout()",
            "plt.savefig('fig1_correlation_heatmap.png', dpi=150, bbox_inches='tight')",
            "plt.show()",
            "print('Saved: fig1_correlation_heatmap.png')",
            "",
        ]

    if "distributions" in want and num_cols:
        n = min(len(num_cols), 9)
        ncols_plot = 3
        nrows_plot = (n + ncols_plot - 1) // ncols_plot
        lines += [
            "# ════ Figure 2: Distributions ══════════════════════════",
            f"fig, axes = plt.subplots({nrows_plot}, {ncols_plot}, figsize=(14, {nrows_plot*4}))",
            "axes = axes.flatten()",
            f"for i, col in enumerate(NUM[:{n}]):",
            "    ax = axes[i]",
            "    data = df[col].dropna()",
            "    ax.hist(data, bins=30, color=PURPLE, edgecolor='none', alpha=0.85)",
            "    ax.axvline(data.mean(),   color='#ff6b6b', lw=1.5, ls='--', label=f'mean={data.mean():.2f}')",
            "    ax.axvline(data.median(), color='#00ff41', lw=1.5, ls='--', label=f'median={data.median():.2f}')",
            "    ax.set_title(col, fontsize=10)",
            "    ax.legend(fontsize=7)",
            f"for j in range({n}, len(axes)): axes[j].set_visible(False)",
            "fig.suptitle('Feature Distributions', fontsize=13, y=1.01)",
            "plt.tight_layout()",
            "plt.savefig('fig2_distributions.png', dpi=150, bbox_inches='tight')",
            "plt.show()",
            "print('Saved: fig2_distributions.png')",
            "",
        ]

    if "pairplot" in want and 2 <= len(num_cols) <= 8:
        hue_arg = f"hue='{cat_cols[0]}', " if cat_cols else ""
        lines += [
            "# ════ Figure 3: Scatter Matrix (Pair Plot) ═════════════",
            f"g = sns.pairplot(",
            f"    df[NUM].dropna(), {hue_arg}",
            "    plot_kws={'alpha': 0.45, 's': 12},",
            "    diag_kind='kde',",
            "    corner=True,",
            ")",
            "g.figure.suptitle('Scatter Matrix', y=1.01, fontsize=13)",
            "g.figure.savefig('fig3_scatter_matrix.png', dpi=120, bbox_inches='tight')",
            "plt.show()",
            "print('Saved: fig3_scatter_matrix.png')",
            "",
        ]

    if "bar" in want and cat_cols and num_cols:
        lines += [
            "# ════ Figure 4: Categorical Bar Chart ══════════════════",
            f"cat_col, num_col = '{cat_cols[0]}', '{num_cols[0]}'",
            "top_cats = df[cat_col].value_counts().head(15).index",
            "grouped = (",
            "    df[df[cat_col].isin(top_cats)]",
            "    .groupby(cat_col)[num_col]",
            "    .mean()",
            "    .sort_values(ascending=False)",
            ")",
            "fig, ax = plt.subplots(figsize=(max(8, len(grouped)), 5))",
            "bars = ax.bar(range(len(grouped)), grouped.values, color=PURPLE, alpha=0.85, edgecolor='none')",
            "ax.set_xticks(range(len(grouped)))",
            "ax.set_xticklabels(grouped.index, rotation=45, ha='right', fontsize=9)",
            "ax.set_title(f'Mean {num_col} by {cat_col}', fontsize=12)",
            "ax.set_ylabel(num_col)",
            "for bar, val in zip(bars, grouped.values):",
            "    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height()*1.01,",
            "            f'{val:.1f}', ha='center', va='bottom', fontsize=8)",
            "plt.tight_layout()",
            "plt.savefig('fig4_bar_chart.png', dpi=150, bbox_inches='tight')",
            "plt.show()",
            "print('Saved: fig4_bar_chart.png')",
        ]

    code = "\n".join(lines)
    out = _data_dir() / "visualization.py"
    out.write_text(code, encoding="utf-8")
    return f"✅ Visualization code written to:\n{out}\n\n```python\n{code}\n```"


@tool
def save_report(content: str, filename: str = "analysis_report.md") -> str:
    """Save an analysis report or summary to the DataAnalyst Agent folder."""
    out = _data_dir() / filename
    out.write_text(content, encoding="utf-8")
    return f"✅ Report saved: {out}"


@tool
def list_data_files() -> str:
    """List all data files (CSV, Excel, JSON) available in the DataAnalyst Agent folder.
    Use this to discover which files the user has uploaded and can be loaded."""
    folder = _data_dir()
    files = sorted(
        [f for f in folder.iterdir() if f.suffix.lower() in _SUPPORTED_EXTS],
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    if not files:
        return (
            f"No data files found in: {folder}\n"
            "Upload a file via the web interface or place a CSV/Excel/JSON file in that folder."
        )
    lines = [f"── Data files in {folder} ──"]
    for f in files:
        size_kb = f.stat().st_size / 1024
        lines.append(f"  {f.name:<40} {size_kb:>8.1f} KB")
    lines.append(f"\nTotal: {len(files)} file(s). Use load_dataset(filename) to load one.")
    return "\n".join(lines)


@tool
def save_dataset(filename: str = "") -> str:
    """Save the current (cleaned) DataFrame to a CSV file in the DataAnalyst Agent folder.
    If filename is empty, auto-generates '<original_name>_cleaned.csv'.
    Use this to persist the cleaned data so it can be reloaded later."""
    err = _need_df()
    if err:
        return err
    if not PANDAS_OK:
        return "Error: pandas not installed."
    df = _session["df"]
    if not filename:
        src = Path(_session["file_path"] or "dataset.csv")
        filename = src.stem + "_cleaned.csv"
    if not filename.endswith(".csv"):
        filename += ".csv"
    out = _data_dir() / filename
    df.to_csv(out, index=False)
    _session["autosave_path"] = str(out)
    return (
        f"✅ Dataset saved: {out}\n"
        f"Rows: {len(df):,}  Columns: {df.shape[1]}\n"
        f"Reload later with: load_dataset('{filename}')"
    )


# ── Tool groups exported to each subagent ─────────────────────────────────────

CLEANER_TOOLS = [
    list_data_files,
    load_dataset,
    inspect_data,
    fix_column_names,
    drop_missing,
    fill_missing,
    remove_duplicates,
    remove_outliers,
    cleaning_log,
    save_dataset,
]

STATS_TOOLS = [
    inspect_data,
    descriptive_stats,
    correlation_matrix,
    top_correlations,
    stat_test,
]

VIZ_TOOLS = [
    inspect_data,
    generate_viz_code,
    save_report,
    save_dataset,
]


# ═══════════════════════════════════════════════════════════════════════════════
#  ML ENGINE — Streamline-Analyst inspired
#  Adds: mode detection, encoding, scaling, classification, clustering, regression,
#        and interactive Plotly visualization
# ═══════════════════════════════════════════════════════════════════════════════

try:
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler, RobustScaler
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression, LinearRegression, Ridge
    from sklearn.cluster import KMeans, DBSCAN
    from sklearn.metrics import (
        accuracy_score, f1_score, classification_report,
        silhouette_score, r2_score, mean_squared_error, mean_absolute_error,
    )
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


@tool
def detect_analysis_mode() -> str:
    """
    Profile the loaded dataset and recommend the best analysis mode:
    'classification', 'clustering', 'regression', or 'eda'.
    Identifies potential target column candidates based on cardinality and type.
    """
    err = _need_df()
    if err: return err
    df = _session["df"]

    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    n_rows, n_cols = df.shape

    classification_targets, regression_targets = [], []
    for col in cat_cols:
        n_u = df[col].nunique()
        if 2 <= n_u <= 20:
            classification_targets.append((col, n_u))
    for col in num_cols:
        n_u = df[col].nunique()
        if 2 <= n_u <= 15:
            classification_targets.append((col, n_u))
        elif n_u > 15:
            regression_targets.append((col, n_u))

    if classification_targets:
        mode, target_hint = "classification", classification_targets[0][0]
    elif regression_targets and len(num_cols) >= 3:
        mode, target_hint = "regression", regression_targets[-1][0]
    elif len(num_cols) >= 3:
        mode, target_hint = "clustering", None
    else:
        mode, target_hint = "eda", None

    _session["mode"] = mode
    if target_hint:
        _session["target"] = target_hint

    lines = [
        f"── Dataset Profile ──",
        f"Shape: {n_rows:,} rows × {n_cols} columns",
        f"Numeric  ({len(num_cols)}): {', '.join(num_cols[:8])}{'…' if len(num_cols)>8 else ''}",
        f"Categorical ({len(cat_cols)}): {', '.join(cat_cols[:8])}{'…' if len(cat_cols)>8 else ''}",
        f"",
        f"── Recommended Mode: {mode.upper()} ──",
    ]
    if classification_targets:
        lines.append(f"Classification target candidates: {[c for c,_ in classification_targets[:5]]}")
    if regression_targets:
        lines.append(f"Regression target candidates: {[c for c,_ in regression_targets[:3]]}")
    if target_hint:
        lines.append(f"Suggested target column: '{target_hint}'")

    lines += ["", f"{'Column':<30} {'Type':<12} {'Unique':>8} {'Null%':>7}", "─" * 60]
    for col in df.columns[:25]:
        n_u = df[col].nunique()
        null_pct = df[col].isnull().mean() * 100
        dtype = str(df[col].dtype)
        lines.append(f"{col:<30} {dtype:<12} {n_u:>8} {null_pct:>6.1f}%")
    return "\n".join(lines)


@tool
def encode_features(strategy: str = "auto", columns: str = "") -> str:
    """
    Encode categorical columns for ML.
    strategy: 'label' (LabelEncoder) | 'onehot' (pd.get_dummies) | 'auto' (binary→label, multi→onehot)
    columns: comma-separated column names (empty = all categorical)
    """
    if not SKLEARN_OK:
        return "Error: scikit-learn not installed. Run: pip install scikit-learn"
    err = _need_df()
    if err: return err
    df = _session["df"]
    cat_cols = (
        [c.strip() for c in columns.split(",") if c.strip()] if columns
        else df.select_dtypes(include="object").columns.tolist()
    )
    encoders = _session.get("encoders", {})
    log = []
    for col in cat_cols:
        if col not in df.columns:
            continue
        n_unique = df[col].nunique()
        s = strategy
        if s == "auto":
            s = "label" if n_unique <= 2 else "onehot"
        if s == "label":
            le = LabelEncoder()
            df[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
            log.append(f"  {col}: label-encoded ({n_unique} classes)")
        else:
            dummies = pd.get_dummies(df[col], prefix=col, drop_first=True)
            df = df.drop(columns=[col]).join(dummies)
            log.append(f"  {col}: one-hot ({n_unique} classes → {len(dummies.columns)} dummies)")
    _session["df"] = df
    _session["encoders"] = encoders
    _autosave()
    return f"Encoded {len(log)} categorical columns:\n" + ("\n".join(log) if log else "  (none needed)")


@tool
def scale_features(method: str = "standard", columns: str = "") -> str:
    """
    Scale numeric features.
    method: 'standard' (Z-score) | 'minmax' (0–1) | 'robust' (IQR-based)
    columns: comma-separated (empty = all numeric except target)
    """
    if not SKLEARN_OK:
        return "Error: scikit-learn not installed. Run: pip install scikit-learn"
    err = _need_df()
    if err: return err
    df = _session["df"]
    num_cols = (
        [c.strip() for c in columns.split(",") if c.strip()] if columns
        else df.select_dtypes(include="number").columns.tolist()
    )
    target = _session.get("target")
    if target and target in num_cols:
        num_cols.remove(target)
    if not num_cols:
        return "No numeric columns to scale."
    scaler = {"standard": StandardScaler(), "minmax": MinMaxScaler()}.get(method, RobustScaler())
    df[num_cols] = scaler.fit_transform(df[num_cols])
    _session["df"] = df
    _session["scaler"] = scaler
    _autosave()
    return f"Scaled {len(num_cols)} numeric columns using {method} scaler:\n  {', '.join(num_cols[:12])}"


@tool
def run_classification(target_column: str, test_size: float = 0.2) -> str:
    """
    Train and evaluate 3 classifiers (Random Forest, Logistic Regression, Gradient Boosting).
    Reports accuracy, F1 (weighted), feature importances.
    target_column: name of the label/class column.
    """
    if not SKLEARN_OK:
        return "Error: scikit-learn not installed. Run: pip install scikit-learn"
    err = _need_df()
    if err: return err
    df = _session["df"]
    if target_column not in df.columns:
        return f"Column '{target_column}' not found. Available: {', '.join(df.columns[:20])}"
    X = df.drop(columns=[target_column]).select_dtypes(include="number").fillna(0)
    y = df[target_column]
    if X.empty or y.nunique() < 2:
        return "Need numeric features and ≥2 classes to run classification."

    stratify = y if y.nunique() < 50 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=42, stratify=stratify
    )
    _session.update({"X_train": X_train, "X_test": X_test,
                     "y_train": y_train, "y_test": y_test, "target": target_column})

    models = {
        "Random Forest":       RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1),
        "Logistic Regression": LogisticRegression(max_iter=1000, random_state=42),
        "Gradient Boosting":   GradientBoostingClassifier(n_estimators=100, random_state=42),
    }
    lines = [f"── Classification: target='{target_column}' | train={len(X_train):,} | test={len(X_test):,} ──\n"]
    lines.append(f"{'Model':<28} {'Accuracy':>10}  {'F1 (weighted)':>14}")
    lines.append("─" * 58)

    best_name, best_model, best_acc = None, None, 0
    results = {}
    for name, model in models.items():
        try:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            acc = accuracy_score(y_test, preds)
            f1  = f1_score(y_test, preds, average="weighted", zero_division=0)
            results[name] = {"accuracy": acc, "f1": f1}
            marker = "  ← BEST" if acc > best_acc else ""
            if acc > best_acc:
                best_acc, best_name, best_model = acc, name, model
            lines.append(f"{name:<28} {acc:>10.4f}  {f1:>14.4f}{marker}")
        except Exception as e:
            lines.append(f"{name:<28} ERROR: {e}")

    if best_model and hasattr(best_model, "feature_importances_"):
        imps = sorted(zip(X.columns, best_model.feature_importances_), key=lambda x: -x[1])
        lines.append(f"\n── Top Feature Importances ({best_name}) ──")
        for feat, imp in imps[:10]:
            lines.append(f"  {feat:<32} {imp:.4f}  {'█' * int(imp * 40)}")
    if best_model:
        preds = best_model.predict(X_test)
        lines.append(f"\n── Detailed Report: {best_name} ──\n{classification_report(y_test, preds, zero_division=0)}")

    _session["ml_results"] = {"mode": "classification", "results": results,
                               "best_model": best_name, "target": target_column}
    result_text = "\n".join(lines)
    save_report.invoke({"content": result_text, "filename": "classification_report.md"})
    return result_text


@tool
def run_clustering(n_clusters: int = 0, algorithm: str = "kmeans") -> str:
    """
    Run unsupervised clustering on numeric features.
    n_clusters: 0 = auto-select via silhouette score (KMeans only).
    algorithm: 'kmeans' | 'dbscan'
    """
    if not SKLEARN_OK:
        return "Error: scikit-learn not installed. Run: pip install scikit-learn"
    err = _need_df()
    if err: return err
    df = _session["df"]
    X = df.select_dtypes(include="number").fillna(0)
    if X.shape[1] < 2:
        return "Need ≥2 numeric columns for clustering."

    lines = [f"── Clustering: {X.shape[0]:,} rows × {X.shape[1]} features ──\n"]
    if algorithm == "dbscan":
        model = DBSCAN(eps=0.5, min_samples=5)
        labels = model.fit_predict(X)
        n_actual = len(set(labels)) - (1 if -1 in labels else 0)
        lines.append(f"DBSCAN: {n_actual} clusters | {(labels==-1).sum()} noise points")
    else:
        if n_clusters == 0:
            best_k, best_sil = 3, -1
            k_range = range(2, min(9, len(X) // 10 + 2))
            for k in k_range:
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                lbls = km.fit_predict(X)
                sil = silhouette_score(X, lbls) if len(set(lbls)) > 1 else -1
                lines.append(f"  k={k}: silhouette={sil:.4f}")
                if sil > best_sil:
                    best_sil, best_k = sil, k
            n_clusters = best_k
            lines.append(f"\nBest k={n_clusters} (silhouette={best_sil:.4f})")
        model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = model.fit_predict(X)
        sil = silhouette_score(X, labels) if len(set(labels)) > 1 else -1
        lines.append(f"\nKMeans (k={n_clusters}) — Silhouette: {sil:.4f}\n")
        lines.append("── Cluster Sizes ──")
        for k in range(n_clusters):
            cnt = int((labels == k).sum())
            pct = cnt / len(labels) * 100
            lines.append(f"  Cluster {k}: {cnt:>5,} rows ({pct:.1f}%)  {'█' * int(pct / 2)}")
        centroids = pd.DataFrame(model.cluster_centers_, columns=X.columns)
        lines.append(f"\n── Cluster Centroids (first {min(5, X.shape[1])} features) ──")
        lines.append(centroids[X.columns[:5]].round(3).to_string())

    df_copy = df.copy()
    df_copy["cluster"] = labels
    _session["df"] = df_copy
    _session["ml_results"] = {"mode": "clustering", "n_clusters": n_clusters, "algorithm": algorithm}

    result_text = "\n".join(lines)
    save_report.invoke({"content": result_text, "filename": "clustering_report.md"})
    return result_text


@tool
def run_regression(target_column: str, test_size: float = 0.2) -> str:
    """
    Train and evaluate 3 regression models (Linear Regression, Ridge, Random Forest Regressor).
    Reports R², RMSE, MAE, and feature importances.
    target_column: name of the continuous numeric target column.
    """
    if not SKLEARN_OK:
        return "Error: scikit-learn not installed. Run: pip install scikit-learn"
    err = _need_df()
    if err: return err
    df = _session["df"]
    if target_column not in df.columns:
        return f"Column '{target_column}' not found. Available: {', '.join(df.columns[:20])}"
    X = df.drop(columns=[target_column]).select_dtypes(include="number").fillna(0)
    y = df[target_column].fillna(df[target_column].median())
    if X.empty:
        return "No numeric feature columns for regression."

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)
    _session.update({"X_train": X_train, "X_test": X_test,
                     "y_train": y_train, "y_test": y_test, "target": target_column})

    models = {
        "Linear Regression": LinearRegression(),
        "Ridge Regression":  Ridge(alpha=1.0),
        "Random Forest":     RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
    }
    lines = [f"── Regression: target='{target_column}' | train={len(X_train):,} | test={len(X_test):,} ──\n"]
    lines.append(f"{'Model':<25} {'R²':>8}  {'RMSE':>12}  {'MAE':>12}")
    lines.append("─" * 65)

    best_name, best_model, best_r2 = None, None, -999
    results = {}
    for name, model in models.items():
        try:
            model.fit(X_train, y_train)
            preds = model.predict(X_test)
            r2   = r2_score(y_test, preds)
            rmse = mean_squared_error(y_test, preds) ** 0.5
            mae  = mean_absolute_error(y_test, preds)
            results[name] = {"r2": r2, "rmse": rmse, "mae": mae}
            marker = "  ← BEST" if r2 > best_r2 else ""
            if r2 > best_r2:
                best_r2, best_name, best_model = r2, name, model
            lines.append(f"{name:<25} {r2:>8.4f}  {rmse:>12.4f}  {mae:>12.4f}{marker}")
        except Exception as e:
            lines.append(f"{name:<25} ERROR: {e}")

    if best_model and hasattr(best_model, "feature_importances_"):
        imps = sorted(zip(X.columns, best_model.feature_importances_), key=lambda x: -x[1])
        lines.append(f"\n── Feature Importances ({best_name}) ──")
        for feat, imp in imps[:10]:
            lines.append(f"  {feat:<32} {imp:.4f}  {'█' * int(imp * 40)}")

    _session["ml_results"] = {"mode": "regression", "results": results,
                               "best_model": best_name, "target": target_column}
    result_text = "\n".join(lines)
    save_report.invoke({"content": result_text, "filename": "regression_report.md"})
    return result_text


@tool
def generate_plotly_viz(mode: str = "auto") -> str:
    """
    Generate interactive Plotly visualization code tailored to the analysis mode.
    mode: 'auto' | 'eda' | 'classification' | 'clustering' | 'regression'
    Saves visualization.py to the DataAnalyst Agent folder.
    """
    err = _need_df()
    if err: return err
    df = _session["df"]
    num_cols = df.select_dtypes(include="number").columns.tolist()
    cat_cols = df.select_dtypes(include="object").columns.tolist()
    ml = _session.get("ml_results", {})
    target = _session.get("target", "")
    fp = _session.get("file_path", "data.csv")
    actual_mode = (ml.get("mode") or _session.get("mode") or mode) if mode == "auto" else mode

    lines = [
        "import pandas as pd",
        "import numpy as np",
        "import plotly.graph_objects as go",
        "import plotly.express as px",
        "from plotly.subplots import make_subplots",
        "",
        f"df = pd.read_csv(r'{fp}')",
        f"NUM = {num_cols}",
        f"CAT = {cat_cols}",
        "",
    ]

    if actual_mode == "classification" and target:
        lines += [
            f"# Fig 1 — Feature distributions by class",
            f"fig = px.box(df, x='{target}', y=NUM[0] if NUM else df.columns[0],",
            f"             color='{target}', title='Feature Distribution by Class', template='plotly_dark')",
            "fig.write_html('fig1_class_distribution.html'); fig.show()",
            "",
            "# Fig 2 — Correlation heatmap",
            "corr = df[NUM].corr().round(2)",
            "fig2 = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r',",
            "                 title='Correlation Matrix', template='plotly_dark')",
            "fig2.write_html('fig2_correlation.html'); fig2.show()",
            "",
            "# Fig 3 — Scatter matrix (first 4 numeric features)",
            f"fig3 = px.scatter_matrix(df, dimensions=NUM[:4], color='{target}',",
            "                          title='Scatter Matrix', template='plotly_dark', opacity=0.5)",
            "fig3.write_html('fig3_scatter_matrix.html'); fig3.show()",
        ]
    elif actual_mode == "clustering":
        lines += [
            "# Fig 1 — Cluster scatter via PCA",
            "from sklearn.decomposition import PCA",
            "pca = PCA(n_components=2)",
            "coords = pca.fit_transform(df[NUM].fillna(0))",
            "df_plot = pd.DataFrame(coords, columns=['PC1','PC2'])",
            "cluster_col = 'cluster' if 'cluster' in df.columns else df.columns[-1]",
            "df_plot['cluster'] = df[cluster_col].astype(str)",
            "fig = px.scatter(df_plot, x='PC1', y='PC2', color='cluster',",
            "                 title='Cluster Visualization (PCA)', template='plotly_dark', opacity=0.7)",
            "fig.write_html('fig1_clusters.html'); fig.show()",
            "",
            "# Fig 2 — Cluster sizes",
            "sizes = df[cluster_col].value_counts().reset_index()",
            "sizes.columns = ['Cluster','Count']",
            "fig2 = px.pie(sizes, names='Cluster', values='Count',",
            "              title='Cluster Size Distribution', template='plotly_dark')",
            "fig2.write_html('fig2_cluster_sizes.html'); fig2.show()",
        ]
    elif actual_mode == "regression" and target:
        lines += [
            f"# Fig 1 — Target distribution",
            f"fig = px.histogram(df, x='{target}', nbins=40,",
            f"                   title='Distribution of {target}', template='plotly_dark')",
            "fig.write_html('fig1_target_dist.html'); fig.show()",
            "",
            "# Fig 2 — Feature correlation with target",
            f"corr_t = df[NUM].corr()['{target}'].drop('{target}').sort_values()",
            "fig2 = px.bar(x=corr_t.values, y=corr_t.index, orientation='h',",
            f"             title='Feature Correlation with {target}', template='plotly_dark')",
            "fig2.write_html('fig2_corr_target.html'); fig2.show()",
            "",
            "# Fig 3 — Top features scatter matrix",
            f"top_feats = corr_t.abs().sort_values(ascending=False).index[:4].tolist()",
            f"fig3 = px.scatter_matrix(df, dimensions=top_feats + ['{target}'],",
            "                          title='Feature vs Target', template='plotly_dark', opacity=0.5)",
            "fig3.write_html('fig3_feature_scatter.html'); fig3.show()",
        ]
    else:
        lines += [
            "# Fig 1 — Correlation heatmap",
            "corr = df[NUM].corr().round(2)",
            "fig = px.imshow(corr, text_auto=True, color_continuous_scale='RdBu_r',",
            "                title='Correlation Heatmap', template='plotly_dark')",
            "fig.write_html('fig1_heatmap.html'); fig.show()",
            "",
            "# Fig 2 — Feature distributions",
            "fig2 = make_subplots(rows=2, cols=3, subplot_titles=NUM[:6])",
            "for i, col in enumerate(NUM[:6]):",
            "    r, c = i // 3 + 1, i % 3 + 1",
            "    fig2.add_trace(go.Histogram(x=df[col].dropna(), name=col, showlegend=False), row=r, col=c)",
            "fig2.update_layout(title='Feature Distributions', template='plotly_dark')",
            "fig2.write_html('fig2_distributions.html'); fig2.show()",
            "",
            "# Fig 3 — Box plots",
            "fig3 = go.Figure([go.Box(y=df[col].dropna(), name=col) for col in NUM[:8]])",
            "fig3.update_layout(title='Box Plots — Outlier Overview', template='plotly_dark')",
            "fig3.write_html('fig3_boxplots.html'); fig3.show()",
        ]

    code = "\n".join(lines)
    out = _data_dir() / "visualization.py"
    out.write_text(code, encoding="utf-8")
    return (
        f"Plotly visualization code written ({actual_mode} mode):\n  {out}\n\n"
        f"Run: python visualization.py\n"
        f"Requires: pip install plotly scikit-learn pandas\n\n"
        f"```python\n{code}\n```"
    )


# ── New tool groups ────────────────────────────────────────────────────────────

PROFILER_TOOLS = [list_data_files, load_dataset, inspect_data, detect_analysis_mode]

FEATURE_TOOLS  = [
    fix_column_names, drop_missing, fill_missing, remove_duplicates,
    remove_outliers, encode_features, scale_features, save_dataset, cleaning_log,
]

ML_TOOLS = [run_classification, run_clustering, run_regression,
            descriptive_stats, correlation_matrix, top_correlations, save_report]

PLOTLY_VIZ_TOOLS = [generate_plotly_viz, save_report]
