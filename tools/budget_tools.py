import json
import uuid
from datetime import datetime, date as date_cls
from langchain.tools import tool
from tools.obsidian_tools import mirror_to_obsidian

BUDGET_FILE = "data/budget.json"

EXPENSE_CATEGORIES = ["food", "transport", "shopping", "entertainment", "bills", "health", "education", "subscriptions", "savings", "other"]
INCOME_CATEGORIES  = ["salary", "freelance", "business", "investment", "gift", "other"]
ACCOUNT_TYPES      = ["checking", "savings", "e_wallet", "credit_card", "investment_account", "loan", "property", "other"]
LIABILITY_TYPES    = {"credit_card", "loan"}
ASSET_TYPES        = {"checking", "savings", "e_wallet", "investment_account", "property", "other"}
INVESTMENT_TYPES   = ["stock", "crypto", "bond", "reksadana", "etf", "other"]
FREQUENCY_TYPES    = ["daily", "weekly", "monthly", "quarterly", "yearly"]


# ── Storage helpers ─────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        with open(BUDGET_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, list):
            # Migrate old flat-list format to new schema
            raw = {
                "accounts": [],
                "transactions": raw,
                "budget_goals": [],
                "investments": [],
                "net_worth_history": [],
                "recurring": [],
            }
            _save_raw(raw)
        return raw
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "accounts": [],
            "transactions": [],
            "budget_goals": [],
            "investments": [],
            "net_worth_history": [],
            "recurring": [],
        }


def _save_raw(data: dict):
    import os
    os.makedirs(os.path.dirname(BUDGET_FILE), exist_ok=True)
    with open(BUDGET_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _save(data: dict):
    _save_raw(data)
    try:
        _mirror(data)
    except Exception:
        pass


def _calc_net_worth(data: dict) -> float:
    accounts    = data.get("accounts", [])
    investments = data.get("investments", [])
    assets      = sum(a["balance"] for a in accounts if a["account_type"] in ASSET_TYPES)
    liabilities = sum(a["balance"] for a in accounts if a["account_type"] in LIABILITY_TYPES)
    inv_value   = sum(i["quantity"] * i.get("current_price", i["buy_price"]) for i in investments)
    return assets + inv_value - liabilities


def _mirror(data: dict) -> None:
    transactions = data.get("transactions", [])
    months: dict[str, list] = {}
    for t in transactions:
        month = t.get("date", "")[:7]
        if month:
            months.setdefault(month, []).append(t)

    nw = _calc_net_worth(data)
    accounts = data.get("accounts", [])

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
            f"net_worth: {nw:.0f}",
            f"updated: {updated}",
            "tags: [budget, mansa, finance]",
            "agent: Mansa",
            "---",
            "",
            f"# Budget — {month}",
            "",
        ]
        if accounts:
            lines += ["## Rekening", "| Nama | Tipe | Saldo |", "|------|------|-------|"]
            for a in accounts:
                sign = "-" if a["account_type"] in LIABILITY_TYPES else "+"
                lines.append(f"| {a['name']} | {a['account_type']} | {sign}Rp {a['balance']:,.0f} |")
            lines += ["", f"**Net Worth: Rp {nw:,.0f}**", ""]

        lines += [
            "## Pemasukan",
            "| Tanggal | Rekening | Kategori | Deskripsi | Jumlah |",
            "|---------|----------|----------|-----------|--------|",
        ]
        for t in sorted(income_txs, key=lambda x: x.get("date", "")):
            acc = t.get("account", "-")
            lines.append(f"| {t['date']} | {acc} | {t['category']} | {t.get('description','-')} | +Rp {t['amount']:,.0f} |")
        lines += [f"| **TOTAL** | | | | **+Rp {total_in:,.0f}** |", ""]

        lines += [
            "## Pengeluaran",
            "| Tanggal | Rekening | Kategori | Deskripsi | Jumlah |",
            "|---------|----------|----------|-----------|--------|",
        ]
        for t in sorted(expense_txs, key=lambda x: x.get("date", "")):
            acc = t.get("account", "-")
            lines.append(f"| {t['date']} | {acc} | {t['category']} | {t.get('description','-')} | -Rp {t['amount']:,.0f} |")
        lines += [
            f"| **TOTAL** | | | | **-Rp {total_ex:,.0f}** |",
            "",
            "## Ringkasan",
            "| Pemasukan | Pengeluaran | Net |",
            "|-----------|-------------|-----|",
            f"| +Rp {total_in:,.0f} | -Rp {total_ex:,.0f} | {'🟢' if net >= 0 else '🔴'} Rp {net:+,.0f} |",
            "",
            "---",
            "[[Home]] | [[Mansa Agent]]",
        ]
        mirror_to_obsidian("Mansa Agent", f"Budget_{month}.md", "\n".join(lines))


# ── Existing 6 tools (updated with optional `account` param) ────────────────

@tool
def add_income(amount: float, category: str = "salary", description: str = "", date: str = "", account: str = "") -> str:
    """
    Record an income transaction.
    Args:
        amount: Amount in Rupiah (e.g. 5000000).
        category: 'salary', 'freelance', 'business', 'investment', 'gift', 'other'.
        description: Optional description.
        date: Date in YYYY-MM-DD format (defaults to today).
        account: Optional account name the money goes into (e.g. 'BCA Tabungan').
    """
    data = _load()
    tx = {
        "id": str(uuid.uuid4())[:8],
        "type": "income",
        "amount": float(amount),
        "category": category.lower(),
        "description": description,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "account": account,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data["transactions"].append(tx)
    if account:
        for a in data["accounts"]:
            if a["name"].lower() == account.lower():
                a["balance"] += float(amount)
                break
    _save(data)
    acc_note = f" → {account}" if account else ""
    return f"✅ Pemasukan dicatat: +Rp {amount:,.0f} | {category} | {description or '-'} | {tx['date']}{acc_note}"


@tool
def add_expense(amount: float, category: str = "other", description: str = "", date: str = "", account: str = "") -> str:
    """
    Record an expense transaction.
    Args:
        amount: Amount spent in Rupiah (e.g. 50000).
        category: 'food', 'transport', 'shopping', 'entertainment', 'bills', 'health', 'education', 'subscriptions', 'savings', 'other'.
        description: Optional description (e.g. 'lunch at warung').
        date: Date in YYYY-MM-DD format (defaults to today).
        account: Optional account name the money comes from (e.g. 'BCA Tabungan').
    """
    data = _load()
    tx = {
        "id": str(uuid.uuid4())[:8],
        "type": "expense",
        "amount": float(amount),
        "category": category.lower(),
        "description": description,
        "date": date or datetime.now().strftime("%Y-%m-%d"),
        "account": account,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data["transactions"].append(tx)
    if account:
        for a in data["accounts"]:
            if a["name"].lower() == account.lower():
                if a["account_type"] in LIABILITY_TYPES:
                    a["balance"] += float(amount)  # debt increases
                else:
                    a["balance"] -= float(amount)
                break
    _save(data)
    acc_note = f" ← {account}" if account else ""
    return f"✅ Pengeluaran dicatat: -Rp {amount:,.0f} | {category} | {description or '-'} | {tx['date']}{acc_note}"


@tool
def get_balance() -> str:
    """Get current total balance (total income minus total expenses across all transactions)."""
    data = _load()
    txs = data.get("transactions", [])
    total_income  = sum(t["amount"] for t in txs if t["type"] == "income")
    total_expense = sum(t["amount"] for t in txs if t["type"] == "expense")
    balance = total_income - total_expense
    return (
        f"Balance Summary:\n"
        f"  Total Income  : +Rp {total_income:,.0f}\n"
        f"  Total Expense : -Rp {total_expense:,.0f}\n"
        f"  Net Balance   : Rp {balance:+,.0f}"
    )


@tool
def list_transactions(month: str = "", tx_type: str = "all", account: str = "") -> str:
    """
    List transactions, optionally filtered by month, type, and account.
    Args:
        month: Month filter in YYYY-MM format (e.g. '2025-01'). Leave empty for all.
        tx_type: Filter by type — 'all', 'income', or 'expense'.
        account: Filter by account name. Leave empty for all accounts.
    """
    data = _load()
    txs = data.get("transactions", [])
    if month:
        txs = [t for t in txs if t["date"].startswith(month)]
    if tx_type != "all":
        txs = [t for t in txs if t["type"] == tx_type]
    if account:
        txs = [t for t in txs if t.get("account", "").lower() == account.lower()]
    if not txs:
        return "Tidak ada transaksi ditemukan."
    lines = []
    for t in txs:
        sign = "+" if t["type"] == "income" else "-"
        acc  = f" [{t['account']}]" if t.get("account") else ""
        lines.append(f"{t['date']} | {sign}Rp {t['amount']:,.0f} | {t['category']} | {t.get('description') or '-'}{acc} (ID:{t['id']})")
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
    data = _load()
    txs = [t for t in data.get("transactions", []) if t["date"].startswith(month)]
    if not txs:
        return f"Tidak ada transaksi untuk {month}."

    income_by_cat: dict  = {}
    expense_by_cat: dict = {}
    for t in txs:
        if t["type"] == "income":
            income_by_cat[t["category"]] = income_by_cat.get(t["category"], 0) + t["amount"]
        else:
            expense_by_cat[t["category"]] = expense_by_cat.get(t["category"], 0) + t["amount"]

    total_income  = sum(income_by_cat.values())
    total_expense = sum(expense_by_cat.values())
    balance       = total_income - total_expense

    lines = [f"Monthly Summary — {month}", "\nINCOME:"]
    for cat, amt in sorted(income_by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat:15} : +Rp {amt:,.0f}")
    lines.append(f"  {'TOTAL':15} : +Rp {total_income:,.0f}")

    lines.append("\nEXPENSES:")
    for cat, amt in sorted(expense_by_cat.items(), key=lambda x: -x[1]):
        lines.append(f"  {cat:15} : -Rp {amt:,.0f}")
    lines.append(f"  {'TOTAL':15} : -Rp {total_expense:,.0f}")
    lines.append(f"\nNet Balance : Rp {balance:+,.0f}")
    if total_income > 0:
        sr = (balance / total_income) * 100
        status = "🟢 SEHAT" if sr >= 20 else "🟡 WASPADA" if sr >= 10 else "🔴 KRITIS"
        lines.append(f"Savings Rate: {sr:.1f}%  {status}")
    return "\n".join(lines)


@tool
def delete_transaction(transaction_id: str) -> str:
    """Delete a transaction by its ID (shown in list_transactions)."""
    data = _load()
    old_len = len(data["transactions"])
    data["transactions"] = [t for t in data["transactions"] if t["id"] != transaction_id]
    if len(data["transactions"]) == old_len:
        return f"Transaksi ID {transaction_id} tidak ditemukan."
    _save(data)
    return f"✅ Transaksi {transaction_id} dihapus."


# ── 12 New tools ─────────────────────────────────────────────────────────────

@tool
def add_account(name: str, account_type: str, balance: float = 0.0, currency: str = "IDR") -> str:
    """
    Add a financial account (rekening, dompet, atau properti).
    Args:
        name: Account name (e.g. 'BCA Tabungan', 'GoPay', 'Rumah Ciputat').
        account_type: One of: checking, savings, e_wallet, credit_card, investment_account, loan, property, other.
        balance: Current balance in Rupiah (default 0). For credit_card/loan, enter what you owe.
        currency: Currency code (default 'IDR').
    """
    data = _load()
    existing = [a for a in data["accounts"] if a["name"].lower() == name.lower()]
    if existing:
        return f"Rekening '{name}' sudah ada. Gunakan update_account_balance untuk memperbarui saldo."
    account = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "account_type": account_type.lower(),
        "balance": float(balance),
        "currency": currency.upper(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data["accounts"].append(account)
    _save(data)
    is_liability = account_type.lower() in LIABILITY_TYPES
    sign = "-" if is_liability else "+"
    label = "hutang" if is_liability else "aset"
    return f"✅ Rekening ditambahkan: {name} ({account_type}) | {sign}Rp {balance:,.0f} [{label}]"


@tool
def list_accounts() -> str:
    """List all financial accounts grouped by assets vs liabilities, with net worth summary."""
    data = _load()
    accounts = data.get("accounts", [])
    if not accounts:
        return "Belum ada rekening tercatat. Gunakan add_account untuk menambahkan rekening pertama kamu."

    asset_accs = [a for a in accounts if a["account_type"] in ASSET_TYPES]
    liab_accs  = [a for a in accounts if a["account_type"] in LIABILITY_TYPES]

    lines = ["REKENING ASET"]
    total_assets = 0.0
    for a in asset_accs:
        lines.append(f"  {a['name']:25} ({a['account_type']:20}) : +Rp {a['balance']:>15,.0f}")
        total_assets += a["balance"]
    lines.append(f"  {'TOTAL ASET':25}                           : +Rp {total_assets:>15,.0f}")

    inv_value = sum(i["quantity"] * i.get("current_price", i["buy_price"]) for i in data.get("investments", []))
    if inv_value > 0:
        lines.append(f"  {'Portofolio Investasi':25}                      : +Rp {inv_value:>15,.0f}")

    lines += ["", "REKENING HUTANG"]
    total_liab = 0.0
    if liab_accs:
        for a in liab_accs:
            lines.append(f"  {a['name']:25} ({a['account_type']:20}) : -Rp {a['balance']:>15,.0f}")
            total_liab += a["balance"]
        lines.append(f"  {'TOTAL HUTANG':25}                           : -Rp {total_liab:>15,.0f}")
    else:
        lines.append("  (tidak ada)")

    nw = total_assets + inv_value - total_liab
    nw_icon = "🟢" if nw >= 0 else "🔴"
    lines += ["", "─" * 55, f"NET WORTH : {nw_icon} Rp {nw:+,.0f}"]
    return "\n".join(lines)


@tool
def update_account_balance(account_name: str, new_balance: float) -> str:
    """
    Manually sync an account's balance (e.g. after checking your bank app).
    Args:
        account_name: Name of the account to update.
        new_balance: New balance in Rupiah. For credit_card/loan, enter current outstanding debt.
    """
    data = _load()
    for a in data["accounts"]:
        if a["name"].lower() == account_name.lower():
            old_bal = a["balance"]
            a["balance"] = float(new_balance)
            _save(data)
            diff = new_balance - old_bal
            sign = "+" if diff >= 0 else ""
            return f"✅ {account_name}: Rp {old_bal:,.0f} → Rp {new_balance:,.0f} (Δ{sign}Rp {diff:,.0f})"
    return f"Rekening '{account_name}' tidak ditemukan. Cek nama dengan list_accounts."


@tool
def get_net_worth() -> str:
    """Get current net worth breakdown: assets, liabilities, investments, and net total."""
    data = _load()
    accounts    = data.get("accounts", [])
    investments = data.get("investments", [])

    asset_accs = [a for a in accounts if a["account_type"] in ASSET_TYPES]
    liab_accs  = [a for a in accounts if a["account_type"] in LIABILITY_TYPES]
    total_assets = sum(a["balance"] for a in asset_accs)
    total_liab   = sum(a["balance"] for a in liab_accs)
    inv_value    = sum(i["quantity"] * i.get("current_price", i["buy_price"]) for i in investments)
    nw = total_assets + inv_value - total_liab

    lines = ["NET WORTH BREAKDOWN", "─" * 40]
    lines.append(f"  Rekening Aset     : +Rp {total_assets:>14,.0f}")
    if inv_value > 0:
        lines.append(f"  Portofolio Inv.   : +Rp {inv_value:>14,.0f}")
    if total_liab > 0:
        lines.append(f"  Hutang            : -Rp {total_liab:>14,.0f}")
    lines.append("─" * 40)
    nw_icon = "🟢" if nw >= 0 else "🔴"
    lines.append(f"  NET WORTH         : {nw_icon} Rp {nw:+>14,.0f}")

    hist = data.get("net_worth_history", [])
    if hist:
        prev = hist[-1]
        delta = nw - prev["net_worth"]
        delta_pct = (delta / abs(prev["net_worth"]) * 100) if prev["net_worth"] != 0 else 0
        lines.append(f"\n  vs snapshot terakhir ({prev['date'][:10]}): Rp {delta:+,.0f} ({delta_pct:+.1f}%)")
    return "\n".join(lines)


@tool
def snapshot_net_worth() -> str:
    """Save a net worth snapshot to history (for tracking progress over time)."""
    data = _load()
    nw = _calc_net_worth(data)
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "net_worth": nw,
    }
    data.setdefault("net_worth_history", []).append(snapshot)
    _save(data)
    return f"✅ Snapshot disimpan: Rp {nw:+,.0f} pada {snapshot['date']}"


@tool
def set_budget_goal(category: str, monthly_limit: float, month: str = "") -> str:
    """
    Set a monthly spending limit for a category.
    Args:
        category: Expense category to cap (e.g. 'food', 'shopping', 'entertainment').
        monthly_limit: Spending limit in Rupiah.
        month: Month in YYYY-MM format (defaults to current month).
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")
    data = _load()
    goals = data.setdefault("budget_goals", [])
    # Update existing goal for same category+month, or add new
    for g in goals:
        if g["category"] == category.lower() and g["month"] == month:
            g["monthly_limit"] = float(monthly_limit)
            _save(data)
            return f"✅ Budget goal diperbarui: {category} bulan {month} → Rp {monthly_limit:,.0f}"
    goals.append({
        "id": str(uuid.uuid4())[:8],
        "category": category.lower(),
        "monthly_limit": float(monthly_limit),
        "month": month,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })
    _save(data)
    return f"✅ Budget goal ditambahkan: {category} bulan {month} | Limit Rp {monthly_limit:,.0f}"


@tool
def check_budget_goals(month: str = "") -> str:
    """
    Check actual spending vs budget goals for a month.
    Args:
        month: Month in YYYY-MM format (defaults to current month).
    """
    if not month:
        month = datetime.now().strftime("%Y-%m")
    data = _load()
    goals = [g for g in data.get("budget_goals", []) if g["month"] == month]
    if not goals:
        return f"Belum ada budget goal untuk {month}. Gunakan set_budget_goal untuk menambahkan."

    txs = [t for t in data.get("transactions", []) if t["date"].startswith(month) and t["type"] == "expense"]
    actual_by_cat: dict = {}
    for t in txs:
        actual_by_cat[t["category"]] = actual_by_cat.get(t["category"], 0) + t["amount"]

    lines = [f"BUDGET CHECK — {month}", "─" * 60]
    for g in sorted(goals, key=lambda x: x["category"]):
        cat   = g["category"]
        limit = g["monthly_limit"]
        spent = actual_by_cat.get(cat, 0)
        pct   = (spent / limit * 100) if limit > 0 else 0
        filled = min(int(pct / 10), 10)
        bar    = "▓" * filled + "░" * (10 - filled)
        if pct >= 100:
            status = "🔴 OVER"
        elif pct >= 80:
            status = "🟡 WASPADA"
        else:
            status = "🟢 AMAN"
        lines.append(f"  {cat:15} [{bar}] {pct:5.1f}%  {status}")
        lines.append(f"  {'':15}  Rp {spent:>12,.0f} / Rp {limit:>12,.0f}")
    lines.append("─" * 60)
    return "\n".join(lines)


@tool
def add_investment(ticker: str, name: str, inv_type: str, quantity: float, buy_price: float, currency: str = "IDR") -> str:
    """
    Add an investment holding (saham, crypto, reksadana, dll).
    Args:
        ticker: Ticker symbol (e.g. 'BBCA', 'BTC', 'IHSG').
        name: Full name (e.g. 'Bank Central Asia').
        inv_type: Type — 'stock', 'crypto', 'bond', 'reksadana', 'etf', 'other'.
        quantity: Number of shares/units owned.
        buy_price: Average buy price per unit in Rupiah.
        currency: Currency of the investment (default 'IDR').
    """
    data = _load()
    for inv in data.get("investments", []):
        if inv["ticker"].upper() == ticker.upper():
            return f"Investasi {ticker.upper()} sudah ada. Gunakan update_investment_price untuk memperbarui harga."
    investment = {
        "id": str(uuid.uuid4())[:8],
        "ticker": ticker.upper(),
        "name": name,
        "inv_type": inv_type.lower(),
        "quantity": float(quantity),
        "buy_price": float(buy_price),
        "current_price": float(buy_price),
        "currency": currency.upper(),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data.setdefault("investments", []).append(investment)
    _save(data)
    total = quantity * buy_price
    return f"✅ Investasi dicatat: {ticker.upper()} | {name} | {quantity:,.0f} unit × Rp {buy_price:,.0f} = Rp {total:,.0f}"


@tool
def update_investment_price(ticker: str, current_price: float) -> str:
    """
    Update the current market price of an investment.
    Args:
        ticker: Ticker symbol (e.g. 'BBCA', 'BTC').
        current_price: Current market price per unit in Rupiah.
    """
    data = _load()
    for inv in data.get("investments", []):
        if inv["ticker"].upper() == ticker.upper():
            old_price  = inv.get("current_price", inv["buy_price"])
            inv["current_price"] = float(current_price)
            qty        = inv["quantity"]
            pnl        = (current_price - inv["buy_price"]) * qty
            pnl_pct    = ((current_price - inv["buy_price"]) / inv["buy_price"] * 100) if inv["buy_price"] else 0
            pnl_icon   = "🟢" if pnl >= 0 else "🔴"
            _save(data)
            return (
                f"✅ {ticker.upper()} diperbarui: Rp {old_price:,.0f} → Rp {current_price:,.0f}\n"
                f"   P&L: {pnl_icon} Rp {pnl:+,.0f} ({pnl_pct:+.1f}%) | Nilai: Rp {current_price*qty:,.0f}"
            )
    return f"Investasi '{ticker}' tidak ditemukan. Gunakan add_investment terlebih dahulu."


@tool
def get_portfolio_summary() -> str:
    """Get a full summary of all investment holdings with P&L and total portfolio value."""
    data = _load()
    investments = data.get("investments", [])
    if not investments:
        return "Belum ada investasi tercatat. Gunakan add_investment untuk menambahkan."

    lines = ["PORTOFOLIO INVESTASI", "─" * 75,
             f"  {'Ticker':8} {'Nama':20} {'Qty':>8} {'Harga Beli':>12} {'Harga Skrg':>12} {'P&L':>14} {'Nilai':>14}",
             "─" * 75]
    total_value  = 0.0
    total_cost   = 0.0
    for inv in sorted(investments, key=lambda x: x["ticker"]):
        qty     = inv["quantity"]
        bp      = inv["buy_price"]
        cp      = inv.get("current_price", bp)
        value   = qty * cp
        cost    = qty * bp
        pnl     = value - cost
        pnl_pct = (pnl / cost * 100) if cost else 0
        icon    = "🟢" if pnl >= 0 else "🔴"
        total_value += value
        total_cost  += cost
        lines.append(
            f"  {inv['ticker']:8} {inv['name'][:20]:20} {qty:>8,.2f} "
            f"Rp{bp:>10,.0f} Rp{cp:>10,.0f} "
            f"{icon}Rp{pnl:>11,.0f} Rp{value:>12,.0f}"
        )
    total_pnl     = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost * 100) if total_cost else 0
    pnl_icon      = "🟢" if total_pnl >= 0 else "🔴"
    lines += ["─" * 75,
              f"  {'TOTAL':29} {'':12} {'':12} {pnl_icon}Rp{total_pnl:>11,.0f} Rp{total_value:>12,.0f}",
              f"  Total Return: {total_pnl_pct:+.2f}%"]
    return "\n".join(lines)


@tool
def add_recurring(description: str, amount: float, category: str, frequency: str, next_date: str, account: str = "") -> str:
    """
    Add a recurring bill or subscription.
    Args:
        description: Description (e.g. 'Spotify', 'Cicilan KPR', 'Sewa Kos').
        amount: Amount in Rupiah.
        category: Expense category (e.g. 'subscriptions', 'bills').
        frequency: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'.
        next_date: Next due date in YYYY-MM-DD format.
        account: Account to debit (optional).
    """
    data = _load()
    recurring = {
        "id": str(uuid.uuid4())[:8],
        "description": description,
        "amount": float(amount),
        "category": category.lower(),
        "frequency": frequency.lower(),
        "next_date": next_date,
        "account": account,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    data.setdefault("recurring", []).append(recurring)
    _save(data)
    return f"✅ Tagihan berulang dicatat: {description} | Rp {amount:,.0f} | {frequency} | Jatuh tempo: {next_date}"


@tool
def get_recurring() -> str:
    """List all recurring bills/subscriptions sorted by next due date, with days-until-due."""
    data = _load()
    items = data.get("recurring", [])
    if not items:
        return "Belum ada tagihan berulang. Gunakan add_recurring untuk menambahkan."

    today = date_cls.today()
    items_sorted = sorted(items, key=lambda x: x.get("next_date", "9999"))
    lines = ["TAGIHAN BERULANG", "─" * 65,
             f"  {'Deskripsi':20} {'Jumlah':>13} {'Frekuensi':10} {'Jatuh Tempo':12} {'Sisa Hari':>9}"]
    lines.append("─" * 65)
    for r in items_sorted:
        try:
            due      = date_cls.fromisoformat(r["next_date"])
            delta    = (due - today).days
            urgency  = "🔴" if delta <= 3 else "🟡" if delta <= 7 else "🟢"
            days_str = f"{urgency} {delta}h"
        except ValueError:
            days_str = "?"
        acc_note = f" [{r['account']}]" if r.get("account") else ""
        lines.append(
            f"  {(r['description']+acc_note)[:22]:22} Rp {r['amount']:>10,.0f}  {r['frequency']:10} {r['next_date']:12} {days_str:>9}"
        )
    total = sum(r["amount"] for r in items)
    lines += ["─" * 65, f"  {'Total tagihan':22} Rp {total:>10,.0f}"]
    return "\n".join(lines)


# ── Tool registry ─────────────────────────────────────────────────────────────

BUDGET_TOOLS = [
    # Existing
    add_income, add_expense, get_balance, list_transactions, get_monthly_summary, delete_transaction,
    # Account management
    add_account, list_accounts, update_account_balance,
    # Net worth
    get_net_worth, snapshot_net_worth,
    # Budget goals
    set_budget_goal, check_budget_goals,
    # Investments
    add_investment, update_investment_price, get_portfolio_summary,
    # Recurring
    add_recurring, get_recurring,
]
