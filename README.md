# 🏦 FinVault - Digital Wallet & Transaction Ledger (India / INR Edition)

A production-grade FinTech application demonstrating **Database Engineering** using **Pure Python** and **Raw SQL** (strictly no ORMs), localized for the Indian banking & UPI ecosystem (INR / ₹, RuPay Virtual Debit, and Domestic UPI/IMPS Ledger).

Built with SQLite and Streamlit, FinVault provides an emerald-green/slate dark-themed virtual banking dashboard with real-time ACID transactions, automated triggers, pure SQL window functions, high-concurrency double-spend prevention, live query profiling, and CSV export.

---

## ⚡ Tech Stack & Architecture Highlights

- **Currency**: Indian Rupee (`INR / ₹`)
- **Domestic Banking Context**: RuPay Platinum Virtual Card, UPI 2.0 & IMPS settlement architecture
- **Database Engine**: SQLite 3.25+ with Write-Ahead Logging (`WAL`) & Foreign Key enforcement (`PRAGMA foreign_keys = ON;`)
- **Language**: **100% Pure Python** (No JavaScript, No HTML/CSS frameworks)
- **Driver**: Python's native `sqlite3` executing **100% RAW SQL QUERIES** (zero ORMs like SQLAlchemy)
- **Frontend / Dashboard**: Streamlit with custom Emerald Green & Deep Slate dark FinTech aesthetic

---

## 👥 Indian Mock Accounts (Pre-Seeded)

- **Arvind Kumar** (`arvind@finvault.in` | `+91-98765-43210` | VPA: `VAULT-001@finvault` | Initial: ₹25,000.00)
- **Priya Patel** (`priya@finvault.in` | `+91-98123-45678` | VPA: `VAULT-002@finvault` | Initial: ₹12,000.00)
- **Amit Verma** (`amit@finvault.in` | `+91-99887-76655` | VPA: `VAULT-003@finvault` | Initial: ₹8,500.00)

*Transactions include authentic Indian contexts: UPI payments, Chai & Snacks, Swiggy dinner splits, society maintenance, and consulting retainers.*

---

## 🏛️ Core SQL Concepts & Features Implemented

### 1. ACID Transactions (`BEGIN IMMEDIATE ... COMMIT ... ROLLBACK`)
P2P UPI transfers are executed in an atomic transaction block:
- **Atomicity**: Either both wallets update and the transaction record is written, or all operations are rolled back completely.
- **Consistency**: Balance non-negative rules (`CHECK (balance >= 0.00)`) and referential integrity are enforced at the database layer.
- **Isolation**: SQLite's `BEGIN IMMEDIATE` acquires an immediate write-lock, preventing race conditions and double-spending across concurrent threads.
- **Durability**: Changes are committed to the SQLite WAL journal.

```sql
BEGIN IMMEDIATE;

-- Check and debit sender
UPDATE wallets 
SET balance = ROUND(balance - :amount, 2), updated_at = datetime('now')
WHERE id = :sender_wallet_id;

-- Credit receiver
UPDATE wallets 
SET balance = ROUND(balance + :amount, 2), updated_at = datetime('now')
WHERE id = :receiver_wallet_id;

-- Record transaction log
INSERT INTO transactions (sender_wallet_id, receiver_wallet_id, amount, status, note, created_at)
VALUES (:sender_wallet_id, :receiver_wallet_id, :amount, 'COMPLETED', :note, datetime('now'));

COMMIT;
```

### 2. Database Triggers (Double-Entry Audit & Rule Guard)
- **`trg_prevent_negative_balance`**: Intercepts any `UPDATE` on `wallets.balance`. If `NEW.balance < 0.00`, SQLite invokes `RAISE(ABORT, 'FinVault SQL Rule Violation: Insufficient funds')`.
- **`trg_audit_wallet_credit`**: Automatically logs every credit to `audit_ledger` with the exact delta and `balance_after`.
- **`trg_audit_wallet_debit`**: Automatically logs every debit to `audit_ledger` with the exact delta and `balance_after`.
- **`trg_audit_wallet_initial_seed`**: Captures initial balances upon wallet creation into `audit_ledger`.

### 3. Pure SQL Window Functions (Real-Time Running Balance)
The account passbook calculates running balances in the SQLite engine using window functions:

```sql
WITH wallet_events AS (
    SELECT 
        t.id,
        t.created_at,
        t.sender_wallet_id,
        t.receiver_wallet_id,
        t.amount,
        t.status,
        t.note,
        u_sender.name AS sender_name,
        u_receiver.name AS receiver_name,
        CASE WHEN t.receiver_wallet_id = :wallet_id THEN 'CREDIT' ELSE 'DEBIT' END AS flow_type,
        CASE WHEN t.receiver_wallet_id = :wallet_id THEN t.amount ELSE -t.amount END AS net_amount,
        1 AS wallet_ref
    FROM transactions t
    LEFT JOIN wallets w_sender ON t.sender_wallet_id = w_sender.id
    LEFT JOIN users u_sender ON w_sender.user_id = u_sender.id
    JOIN wallets w_receiver ON t.receiver_wallet_id = w_receiver.id
    JOIN users u_receiver ON w_receiver.user_id = u_receiver.id
    WHERE (t.sender_wallet_id = :wallet_id OR t.receiver_wallet_id = :wallet_id)
      AND t.status = 'COMPLETED'
)
SELECT 
    id,
    created_at,
    flow_type,
    amount,
    net_amount,
    sender_name,
    receiver_name,
    note,
    status,
    -- Real-Time Running Balance calculated via SQLite Window Function
    ROUND(
        SUM(net_amount) OVER (
            PARTITION BY wallet_ref 
            ORDER BY created_at ASC, id ASC
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ),
        2
    ) AS running_balance
FROM wallet_events
ORDER BY created_at DESC, id DESC;
```

### 4. ⚡ Concurrency & Double-Spend Stress Testing
- Uses Python `threading.Barrier(2)` to release two worker threads at the exact same microsecond.
- Demonstrates how SQLite's `BEGIN IMMEDIATE` write-lock serializes concurrent operations: **one thread commits, while the other is safely rolled back** to prevent negative balances.

### 5. 🔍 Live SQL Query Inspector & Profiler
- Real-time telemetric logging of all queries executed by the application.
- Displays exact SQL statements, bound parameters, execution duration in milliseconds (`0.02ms - 1.2ms`), and rows affected.
- Includes an **Interactive Read-Only SQL Playground** allowing direct execution of `SELECT`, `WITH`, `PRAGMA`, and `EXPLAIN` queries.

### 6. 📥 Export Passbook Statement as CSV
- Instant one-click CSV export in the "Passbook & Ledger" tab for both the transaction statement (with window-function-calculated running balance) and the audit ledger.

---

## 🚀 2-Step Run Instructions

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Launch FinVault
```bash
streamlit run app.py
```
*Open your browser at `http://localhost:8501`.*
