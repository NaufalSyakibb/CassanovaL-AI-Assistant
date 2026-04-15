import json
import uuid
from datetime import datetime
from langchain.tools import tool
from tools.obsidian_tools import mirror_to_obsidian

BUDGET_FILE = "data/budget.json"

EXPENSE_CATEGORIES = ["food", "transport", "shopping", "entertainment", "bills", "health", "education", "other"]
INCOME_CATEGORIES = ["salary", "freelance", "business", "investment", "gift", "other"]


def _load() -> list:
    try:
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(data: list):
    import os
    os.makedirs(os.path.dirname(BUDGET_FILE), exist_ok=True)
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    try:
        _mirror(data)
    except Exception:
        pass


def _mirror(transactions: list) -> None:
    """Mirror monthly budget to Obsidian AI Data/Mansa Agent/Budget_YYYY-MM.md"""
    # Group by month
    months: dict[str, list] = {}
    for t in transactions:
        month = t.get("date", "")[:7]
        if month:
            months.setdefault(month, []).append(t)

    for month, txs in months.items():
        income_txs  = [t for t in txs if t["type"] == "income"]
        expense_txs = [t for t in txs if t["type"] == "expense"]
        total_in    = sum(t["amount"] for t in income_txs)
        total_ex    = sum(t["amount"] for t in expense_txs)
        net         = total_in - total_ex
        updated     = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = [
            "---",
            f"month: {month}",
            f"income: {total_in:.0f}",
            f"expenses: {total_ex:.0f}",
            f"net: {net:.0f}",
            f"updated: {updated}",
            "tags: [budget, mansa, finance]",
            "agent: Mansa",
            "---",
            "",
            f"# Budget — {month}",
            "",
            "## Pemasukan",
            "| Tanggal | Kategori | Deskripsi | Jumlah |",
            "|---------|----------|-----------|--------|",
        ]
        for t in sorted(income_txs, key=lambda x: x.get("date", "")):
            lines.append(f"| {t['date']} | {t['category']} | {t.get('description','-')} | +Rp {t['amount']:,.0f} |")
        lines += [
            f"| **TOTAL** | | | **+Rp {total_in:,.0f}** |",
            "",
            "## Pengeluaran",
            "| Tanggal | Kategori | Deskripsi | Jumlah |",
            "|---------|----------|-----------|--------|",
        ]
        for t in sorted(expense_txs, key=lambda x: x.get("date", "")):
            lines.append(f"| {t['date']} | {t['category']} | {t.get('description','-')} | -Rp {t['amount']:,.0f} |")
        lines += [
            f"| **TOTAL** | | | **-Rp {total_ex:,.0f}** |",
            "",
            "## Ringkasan",
            f"| Pemasukan | Pengeluaran | Net |",
            f"|-----------|-------------|-----|",
            f"| +Rp {total_in:,.0f} | -Rp {total_ex:,.0f} | {'🟢' if net >= 0 else '🔴'} Rp {net:+,.0f} |",
        ]
        lines.append("\n\n---\n[[Home]] | [[Mansa Agent]]")
        mirror_to_obsidian("Mansa Agent", f"Budget_{month}.md", "\n".join(lines))


@tool
def add_income(amount: float, category: str = "salary", description: str = "", date: str = "") -> str:
    """
    Record an income transaction.
    Args:
        amount: Amount in your local currency (e.g. 5000000).
        category: Income category — 'salary', 'freelance', 'business', 'investment', 'gift', 'other'.
        description: Optional description.
        date: Date in YYYY-MM-DD format (defaults to today).
    """
    transactions = _load()
    tx = {
        "id": str(uuid.uuid4())[:8],
        "type": "income",
        "amount": float(amount),
        "category": category.lower(),
        "description": description,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    transactions.append(tx)
    _save(transactions)
    return f"Income recorded! +{amount:,.0f} | {category} | {description or 'no description'} | {tx['date']}"


@tool
def add_expense(amount: float, category: str = "other", description: str = "", date: str = "") -> str:
    """
    Record an expense transaction.
    Args:
        amount: Amount spent (e.g. 50000).
        category: Expense category — 'food', 'transport', 'shopping', 'entertainment', 'bills', 'health', 'education', 'other'.
        description: Optional description (e.g. 'lunch at warung').
        date: Date in YYYY-MM-DD format (defaults to today).
    """
    transactions = _load()
    tx = {
        "id": str(uuid.uuid4())[:8],
        "type": "expense",
        "amount": float(amount),
        "category": category.lower(),
        "description": description,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    transactions.append(tx)
    _save(transactions)
    return f"Expense recorded! -{amount:,.0f} | {category} | {description or 'no description'} | {tx['date']}"


@tool
def get_balance() -> str:
    """Get current total balance (total income minus total expenses)."""
    transactions = _load()
    total_income = sum(t["amount"] for t in transactions if t["type"] == "income")
    total_expense = sum(t["amount"] for t in transactions if t["type"] == "expense")
    balance = total_income - total_expense
    return (
        f"Balance Summary:\n"
        f"  Total Income  : +{total_income:,.0f}\n"
        f"  Total Expense : -{total_expense:,.0f}\n"
        f"  Net Balance   : {balance:+,.0f}"
    )


@tool
def list_transactions(month: str = "", tx_type: str = "all") -> str:
    """
    List transactions, optionally filtered by month and type.
    Args:
        month: Month filter in YYYY-MM format (e.g. '2025-01'). Leave empty for all.
        tx_type: Filter by type — 'all', 'income', or 'expense'.
    """
    transactions = _load()
    if month:
        transactions = [t for t in transactions if t["date"].startswith(month)]
    if tx_type != "all":
        transactions = [t for t in transactions if t["type"] == tx_type]
    if not transactions:
        return "No transactions found."
    lines = []
    for t in transactions:
        sign = "+" if t["type"] == "income" else "-"
        lines.append(
            f"{t['date']} | {sign}{t['amount']:,.0f} | {t['category']} | {t['description'] or '-'} (ID:{t['id']})"
        )
    return "\n".join(lines)


@tool
def get_monthly_summary(month: str = "") -> str:
    """
    Get a spending summary by category for a given month.
    Args:
        month: Month in YYYY-MM format (defaults to current month).
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")
    transactions = _load()
    monthly = [t for t in transactions if t["date"].startswith(month)]
    if not monthly:
        return f"No transactions for {month}."

    income_by_cat: dict = {}
    expense_by_cat: dict = {}
    for t in monthly:
        if t["type"] == "income":
            income_by_cat[t["category"]] = income_by_cat.get(t["category"], 0) + t["amount"]
        else:
            expense_by_cat[t["category"]] = expense_by_cat.get(t["category"], 0) + t["amount"]

    total_income = sum(income_by_cat.values())
    total_expense = sum(expense_by_cat.values())

    lines = [f"Monthly Summary — {month}"]
    lines.append("\nINCOME:")
    for cat, amt in sorted(income_by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat:15} : +{amt:,.0f}")
    lines.append(f"  {'TOTAL':15} : +{total_income:,.0f}")

    lines.append("\nEXPENSES:")
    for cat, amt in sorted(expense_by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat:15} : -{amt:,.0f}")
    lines.append(f"  {'TOTAL':15} : -{total_expense:,.0f}")

    balance = total_income - total_expense
    lines.append(f"\nNet Balance: {balance:+,.0f}")
    return "\n".join(lines)


@tool
def delete_transaction(transaction_id: str) -> str:
    """Delete a transaction by its ID."""
    transactions = _load()
    new = [t for t in transactions if t["id"] != transaction_id]
    if len(new) == len(transactions):
        return f"Transaction ID {transaction_id} not found."
    _save(new)
    return f"Transaction {transaction_id} deleted."


BUDGET_TOOLS = [add_income, add_expense, get_balance, list_transactions, get_monthly_summary, delete_transaction]
