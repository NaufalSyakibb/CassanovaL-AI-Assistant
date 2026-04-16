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
    "autosave_path": None,   # path of the last auto-saved cleaned CSV
}

_SUPPORTED_EXTS = {".csv", ".xlsx", ".xls", ".json"}

def _data_dir() -> Path:
    vault = os.getenv("OBSIDIAN_VAULT_PATH", "").strip()
    base = (Path(vault) / "AI Data" / "DataAnalyst Agent") if vault \
           else (Path(__file__).parent.parent / "AI Data" / "DataAnalyst Agent")
    base.mkdir(parents=True, exist_ok=True)
    return base

def _reset_session() -> None:
    """Clear all session state — call before each new DataAnalyst crew run."""
    _session["df"] = None
    _session["file_path"] = None
    _session["clean_log"] = []
    _session["autosave_path"] = None


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
