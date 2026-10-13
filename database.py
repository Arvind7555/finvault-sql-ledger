"""
FinVault - Digital Wallet & Transaction Ledger
Database Engine & Raw SQL Data Access Layer

This module strictly utilizes Python's built-in `sqlite3` driver with 100% RAW SQL QUERIES.
No ORMs (SQLAlchemy, Peewee, etc.) are used to ensure complete visibility of:
- ACID Transactions (BEGIN IMMEDIATE, COMMIT, ROLLBACK)
- SQLite Foreign Key Constraints & Check Constraints
- Triggers (Balance boundary validation & automated audit logging)
- Window Functions (SUM() OVER (PARTITION BY wallet_id ORDER BY created_at))
- High-Concurrency Double-Spend Prevention via Write Locks
- Real-time SQL Query Tracing & Profiling
"""

import os
import sqlite3
import time
import threading
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

# Default database filename
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "finvault.db")
SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")

# In-memory query tracer for the Live SQL Query Inspector
_QUERY_LOGS_LOCK = threading.Lock()
_RECENT_QUERY_LOGS = deque(maxlen=200)


# ============================================================================
# QUERY TRACER & LOGGER
# ============================================================================

def log_query(
    query: str,
    params: Any = None,
    duration_ms: float = 0.0,
    rows_affected: int = 0,
    status: str = "SUCCESS",
    operation: str = "QUERY",
    error: Optional[str] = None,
) -> None:
    """Thread-safe recording of SQL execution traces for the live inspector."""
    with _QUERY_LOGS_LOCK:
        _RECENT_QUERY_LOGS.append({
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "operation": operation,
            "query": query.strip(),
            "params": str(params) if params else None,
            "duration_ms": round(duration_ms, 3),
            "rows_affected": rows_affected,
            "status": status,
            "error": error,
        })


def get_recent_query_logs(limit: int = 40) -> List[Dict[str, Any]]:
    """Retrieve the most recent SQL execution logs."""
    with _QUERY_LOGS_LOCK:
        return list(_RECENT_QUERY_LOGS)[-limit:]


def clear_query_logs() -> None:
    """Clear all recorded SQL query logs."""
    with _QUERY_LOGS_LOCK:
        _RECENT_QUERY_LOGS.clear()


def logged_execute(
    cursor: sqlite3.Cursor,
    sql: str,
    params: Any = None,
    operation: str = "EXECUTE",
) -> sqlite3.Cursor:
    """Helper to execute SQL statements while recording execution time and trace."""
    t0 = time.perf_counter()
    try:
        if params is not None:
            res = cursor.execute(sql, params)
        else:
            res = cursor.execute(sql)
        duration_ms = (time.perf_counter() - t0) * 1000
        rows = cursor.rowcount if cursor.rowcount >= 0 else 0
        log_query(
            query=sql,
            params=params,
            duration_ms=duration_ms,
            rows_affected=rows,
            status="SUCCESS",
            operation=operation,
        )
        return res
    except Exception as exc:
        duration_ms = (time.perf_counter() - t0) * 1000
        log_query(
            query=sql,
            params=params,
            duration_ms=duration_ms,
            rows_affected=0,
            status="ERROR",
            operation=operation,
            error=str(exc),
        )
        raise exc


# ============================================================================
# CUSTOM DATABASE EXCEPTIONS
# ============================================================================

class FinVaultDBError(Exception):
    """Base exception for FinVault database operations."""
    pass


class InsufficientFundsError(FinVaultDBError):
    """Raised when wallet balance is lower than the transfer amount."""
    pass


class WalletNotFoundError(FinVaultDBError):
    """Raised when a specified wallet ID does not exist."""
    pass


class InvalidTransferError(FinVaultDBError):
    """Raised when transfer constraints are violated (e.g. self-transfer, zero amount)."""
    pass


# ============================================================================
# CONNECTION MANAGEMENT
# ============================================================================

def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """
    Establish a connection to the SQLite database with:
    - Foreign keys explicitly enabled
    - Row factory configured to sqlite3.Row for dictionary-like access
    - WAL (Write-Ahead Logging) mode enabled for high concurrency
    - isolation_level=None to support explicit raw SQL transaction control
    - timeout=10.0 to handle concurrent locks cleanly
    """
    conn = sqlite3.connect(db_path, timeout=10.0, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # Enforce SQLite foreign keys and concurrency
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db(schema_file: str = SCHEMA_PATH, db_path: str = DB_PATH) -> None:
    """
    Execute raw DDL statements from schema.sql to initialize tables,
    triggers, constraints, and indexes.
    """
    if not os.path.exists(schema_file):
        raise FileNotFoundError(f"Schema file not found at: {schema_file}")
    
    with open(schema_file, "r", encoding="utf-8") as f:
        schema_sql = f.read()

    conn = get_connection(db_path)
    try:
        conn.executescript(schema_sql)
        log_query(query="-- Executed Schema DDL script (tables, triggers, indexes)", operation="INIT_SCHEMA")
    finally:
        conn.close()


# ============================================================================
# DATABASE SEEDING
# ============================================================================

def seed_demo_data(db_path: str = DB_PATH, force_reset: bool = False) -> None:
    """
    Populate the database with demo accounts (Alice, Bob, Charlie),
    initial balances, and a rich transaction history to test SQL features.
    """
    if force_reset and os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass

    init_db(schema_file=SCHEMA_PATH, db_path=db_path)
    conn = get_connection(db_path)

    try:
        cursor = conn.cursor()

        # Check if users already exist
        cursor.execute("SELECT COUNT(*) AS count FROM users;")
        if cursor.fetchone()["count"] > 0 and not force_reset:
            return  # Already seeded

        cursor.execute("BEGIN IMMEDIATE;")

        # 1. Insert Initial Users (Indian Mock Data)
        demo_users = [
            ("Arvind Kumar", "arvind@finvault.in", "+91-98765-43210", "#10b981"),
            ("Priya Patel", "priya@finvault.in", "+91-98123-45678", "#3b82f6"),
            ("Amit Verma", "amit@finvault.in", "+91-99887-76655", "#8b5cf6"),
        ]
        
        user_ids = []
        for name, email, phone, color in demo_users:
            cursor.execute(
                """
                INSERT INTO users (name, email, phone, avatar_color)
                VALUES (?, ?, ?, ?);
                """,
                (name, email, phone, color),
            )
            user_ids.append(cursor.lastrowid)

        # 2. Insert Wallets with 0 balance, then fund via deposit_funds (INR)
        wallet_ids = []
        for uid in user_ids:
            cursor.execute(
                """
                INSERT INTO wallets (user_id, balance, currency)
                VALUES (?, 0.00, 'INR');
                """,
                (uid,),
            )
            wallet_ids.append(cursor.lastrowid)

        cursor.execute("COMMIT;")

        # 3. Fund Wallets with initial opening deposits (INR Context)
        initial_deposits = [
            (wallet_ids[0], 25000.00, "Initial Account Opening Deposit - SBI IMPS"),
            (wallet_ids[1], 12000.00, "Initial Account Opening Deposit - HDFC NetBanking"),
            (wallet_ids[2], 8500.00,  "Initial Account Opening Deposit - ICICI UPI"),
        ]
        for wid, amt, note in initial_deposits:
            deposit_funds(wallet_id=wid, amount=amt, note=note, db_path=db_path)

        # 4. Perform Initial Seed Transactions using ACID Transfer Function
        # Arvind -> Priya (₹1,500.00)
        transfer_funds(
            sender_wallet_id=wallet_ids[0],
            receiver_wallet_id=wallet_ids[1],
            amount=1500.00,
            note="UPI / Freelance Web Design invoice",
            db_path=db_path,
        )

        # Priya -> Amit (₹750.00)
        transfer_funds(
            sender_wallet_id=wallet_ids[1],
            receiver_wallet_id=wallet_ids[2],
            amount=750.00,
            note="Chai, Snacks & Swiggy Dinner Split",
            db_path=db_path,
        )

        # Amit -> Arvind (₹500.00)
        transfer_funds(
            sender_wallet_id=wallet_ids[2],
            receiver_wallet_id=wallet_ids[0],
            amount=500.00,
            note="Book repayment & Metro Recharge",
            db_path=db_path,
        )

        # Arvind -> Amit (₹1,200.00)
        transfer_funds(
            sender_wallet_id=wallet_ids[0],
            receiver_wallet_id=wallet_ids[2],
            amount=1200.00,
            note="Broadband & Society Maintenance Share",
            db_path=db_path,
        )

        # Priya -> Arvind (₹2,000.00)
        transfer_funds(
            sender_wallet_id=wallet_ids[1],
            receiver_wallet_id=wallet_ids[0],
            amount=200.00,
            note="Monthly Consulting Retainer - UPI",
            db_path=db_path,
        )

    except Exception:
        cursor.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


# ============================================================================
# ACID TRANSACTION: MONEY TRANSFER
# ============================================================================

def transfer_funds(
    sender_wallet_id: int,
    receiver_wallet_id: int,
    amount: float,
    note: str = "",
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Executes an atomic money transfer between two wallets.
    
    ACID Guarantees:
    - Atomicity: Wrapped in explicit raw SQL 'BEGIN IMMEDIATE' and 'COMMIT'.
      Any failure immediately invokes 'ROLLBACK', leaving data untouched.
    - Consistency: Enforced via SQL check constraints and SQLite Triggers
      (trg_prevent_negative_balance).
    - Isolation: 'BEGIN IMMEDIATE' acquires an exclusive write-lock right away,
      preventing concurrent race conditions / double-spending.
    - Durability: Changes committed to SQLite WAL journal.
    """
    amount = round(float(amount), 2)
    if amount <= 0:
        raise InvalidTransferError(f"Transfer amount must be strictly greater than 0.00. (Received: ₹{amount:.2f})")

    if sender_wallet_id == receiver_wallet_id:
        raise InvalidTransferError("Self-transfer prohibited: Sender and receiver wallets cannot be the same.")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        # 1. Acquire immediate write lock to prevent race conditions
        logged_execute(cursor, "BEGIN IMMEDIATE;", operation="BEGIN_TRANSACTION")

        # 2. Fetch & Verify Sender Wallet
        logged_execute(
            cursor,
            """
            SELECT w.id, w.user_id, w.balance, u.name, w.currency
            FROM wallets w
            JOIN users u ON w.user_id = u.id
            WHERE w.id = ?;
            """,
            (sender_wallet_id,),
            operation="VERIFY_SENDER",
        )
        sender = cursor.fetchone()
        if not sender:
            raise WalletNotFoundError(f"Sender wallet ID #{sender_wallet_id} does not exist.")

        # 3. Fetch & Verify Receiver Wallet
        logged_execute(
            cursor,
            """
            SELECT w.id, w.user_id, w.balance, u.name, w.currency
            FROM wallets w
            JOIN users u ON w.user_id = u.id
            WHERE w.id = ?;
            """,
            (receiver_wallet_id,),
            operation="VERIFY_RECEIVER",
        )
        receiver = cursor.fetchone()
        if not receiver:
            raise WalletNotFoundError(f"Receiver wallet ID #{receiver_wallet_id} does not exist.")

        # 4. Check for Insufficient Balance
        current_sender_balance = float(sender["balance"])
        if current_sender_balance < amount:
            raise InsufficientFundsError(
                f"Insufficient funds: Wallet #{sender_wallet_id} ({sender['name']}) has "
                f"₹{current_sender_balance:,.2f}, cannot transfer ₹{amount:,.2f}."
            )

        # 5. Deduct from Sender
        # Triggers automatically intercept and verify balance >= 0, logging to audit_ledger
        logged_execute(
            cursor,
            """
            UPDATE wallets
            SET balance = ROUND(balance - ?, 2),
                updated_at = datetime('now')
            WHERE id = ?;
            """,
            (amount, sender_wallet_id),
            operation="DEBIT_SENDER",
        )

        # 6. Credit to Receiver
        # Trigger automatically records CREDIT entry in audit_ledger
        logged_execute(
            cursor,
            """
            UPDATE wallets
            SET balance = ROUND(balance + ?, 2),
                updated_at = datetime('now')
            WHERE id = ?;
            """,
            (amount, receiver_wallet_id),
            operation="CREDIT_RECEIVER",
        )

        # 7. Record in Transactions Table
        logged_execute(
            cursor,
            """
            INSERT INTO transactions (sender_wallet_id, receiver_wallet_id, amount, status, note, created_at)
            VALUES (?, ?, ?, 'COMPLETED', ?, datetime('now'));
            """,
            (sender_wallet_id, receiver_wallet_id, amount, note.strip()),
            operation="RECORD_TX",
        )
        transaction_id = cursor.lastrowid

        # 8. Commit Transaction
        logged_execute(cursor, "COMMIT;", operation="COMMIT_TRANSACTION")

        # Fetch updated balances
        cursor.execute("SELECT balance FROM wallets WHERE id = ?;", (sender_wallet_id,))
        new_sender_balance = cursor.fetchone()["balance"]

        cursor.execute("SELECT balance FROM wallets WHERE id = ?;", (receiver_wallet_id,))
        new_receiver_balance = cursor.fetchone()["balance"]

        return {
            "success": True,
            "transaction_id": transaction_id,
            "sender_name": sender["name"],
            "receiver_name": receiver["name"],
            "amount": amount,
            "sender_new_balance": float(new_sender_balance),
            "receiver_new_balance": float(new_receiver_balance),
            "note": note,
        }

    except Exception as e:
        # Atomic Rollback on any failure
        try:
            logged_execute(cursor, "ROLLBACK;", operation="ROLLBACK_TRANSACTION")
        except Exception:
            pass
        raise e
    finally:
        conn.close()


def deposit_funds(
    wallet_id: int,
    amount: float,
    note: str = "Direct UPI / IMPS Top-up",
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Atomic top-up/deposit to a user's wallet.
    Trigger automatically logs CREDIT to audit_ledger.
    """
    amount = round(float(amount), 2)
    if amount <= 0:
        raise InvalidTransferError(f"Deposit amount must be greater than 0.00. (Received: ₹{amount:.2f})")

    conn = get_connection(db_path)
    cursor = conn.cursor()

    try:
        logged_execute(cursor, "BEGIN IMMEDIATE;", operation="BEGIN_DEPOSIT")
        
        logged_execute(
            cursor,
            "SELECT id, balance FROM wallets WHERE id = ?;",
            (wallet_id,),
            operation="FETCH_WALLET_BALANCE",
        )
        wallet = cursor.fetchone()
        if not wallet:
            raise WalletNotFoundError(f"Wallet ID #{wallet_id} not found.")

        logged_execute(
            cursor,
            """
            UPDATE wallets
            SET balance = ROUND(balance + ?, 2),
                updated_at = datetime('now')
            WHERE id = ?;
            """,
            (amount, wallet_id),
            operation="UPDATE_WALLET_BALANCE",
        )

        logged_execute(
            cursor,
            """
            INSERT INTO transactions (sender_wallet_id, receiver_wallet_id, amount, status, note, created_at)
            VALUES (NULL, ?, ?, 'COMPLETED', ?, datetime('now'));
            """,
            (wallet_id, amount, note),
            operation="RECORD_DEPOSIT_TX",
        )
        tx_id = cursor.lastrowid
        logged_execute(cursor, "COMMIT;", operation="COMMIT_DEPOSIT")

        cursor.execute("SELECT balance FROM wallets WHERE id = ?;", (wallet_id,))
        new_balance = cursor.fetchone()["balance"]

        return {
            "success": True,
            "transaction_id": tx_id,
            "new_balance": float(new_balance),
        }
    except Exception as e:
        try:
            logged_execute(cursor, "ROLLBACK;", operation="ROLLBACK_DEPOSIT")
        except Exception:
            pass
        raise e
    finally:
        conn.close()


# ============================================================================
# PURE SQL WINDOW FUNCTION QUERIES (PASSBOOK & RUNNING BALANCE)
# ============================================================================

def get_wallet_passbook(wallet_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Retrieves the complete transaction passbook statement for a specific wallet.
    
    PURE SQL WINDOW FUNCTION IMPLEMENTATION:
    Calculates the real-time running balance over chronological order using:
    SUM(net_amount) OVER (
        PARTITION BY wallet_ref 
        ORDER BY created_at ASC, id ASC
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    )
    """
    query = """
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
            CASE 
                WHEN t.receiver_wallet_id = :wallet_id THEN 'CREDIT'
                ELSE 'DEBIT'
            END AS flow_type,
            CASE 
                WHEN t.receiver_wallet_id = :wallet_id THEN t.amount
                ELSE -t.amount
            END AS net_amount,
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
        -- SQL Window Function: Running balance calculated strictly in SQLite
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
    """

    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        logged_execute(cursor, query, {"wallet_id": wallet_id}, operation="QUERY_PASSBOOK_WINDOW_FUNC")
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    finally:
        conn.close()


def get_audit_ledger_with_window_function(wallet_id: int, db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """
    Pure SQL Window Function over the audit_ledger table:
    SUM(CASE WHEN entry_type = 'CREDIT' THEN amount ELSE -amount END)
        OVER (PARTITION BY wallet_id ORDER BY created_at ASC, id ASC)
    
    Demonstrates pure SQL verification of the immutable double-entry ledger.
    """
    query = """
    SELECT 
        id,
        wallet_id,
        entry_type,
        amount,
        balance_after,
        created_at,
        ROUND(
            SUM(CASE WHEN entry_type = 'CREDIT' THEN amount ELSE -amount END) 
                OVER (PARTITION BY wallet_id ORDER BY created_at ASC, id ASC),
            2
        ) AS calculated_running_balance
    FROM audit_ledger
    WHERE wallet_id = :wallet_id
    ORDER BY created_at DESC, id DESC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        logged_execute(cursor, query, {"wallet_id": wallet_id}, operation="QUERY_AUDIT_WINDOW_FUNC")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


# ============================================================================
# CONCURRENCY & DOUBLE-SPEND STRESS TESTING
# ============================================================================

def run_concurrency_stress_test(
    sender_wallet_id: int,
    recipient_1_id: int,
    recipient_2_id: int,
    transfer_amount: float,
    db_path: str = DB_PATH,
) -> Dict[str, Any]:
    """
    Simulates a race condition / double-spending attack under high concurrency.
    Two worker threads are synchronized with threading.Barrier(2) and attempt
    to drain the sender's wallet at the EXACT same microsecond.
    
    Demonstrates:
    - How SQLite's BEGIN IMMEDIATE write-lock serializes concurrent operations
    - How the balance CHECK constraint & triggers block double-spending
    - Exactly one transfer commits while the other safely rolls back
    """
    # 1. Fetch initial balance
    sender_before = get_wallet_by_id(sender_wallet_id, db_path=db_path)
    if not sender_before:
        raise WalletNotFoundError(f"Sender wallet #{sender_wallet_id} not found.")

    initial_balance = float(sender_before["balance"])
    transfer_amount = round(float(transfer_amount), 2)

    barrier = threading.Barrier(2)
    thread_results: Dict[str, Any] = {}

    def worker_thread(thread_name: str, recipient_id: int) -> None:
        # Wait for both threads to hit the barrier at the exact same moment
        barrier.wait()
        start_time_iso = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        t0 = time.perf_counter()

        try:
            res = transfer_funds(
                sender_wallet_id=sender_wallet_id,
                receiver_wallet_id=recipient_id,
                amount=transfer_amount,
                note=f"Stress Test Race Condition [{thread_name}]",
                db_path=db_path,
            )
            duration_ms = (time.perf_counter() - t0) * 1000
            thread_results[thread_name] = {
                "thread_name": thread_name,
                "recipient_id": recipient_id,
                "recipient_name": res["receiver_name"],
                "amount": transfer_amount,
                "status": "COMMITTED",
                "success": True,
                "start_time": start_time_iso,
                "duration_ms": round(duration_ms, 2),
                "transaction_id": res["transaction_id"],
                "new_sender_balance": res["sender_new_balance"],
                "details": f"Transaction #{res['transaction_id']} committed successfully.",
                "error": None,
            }
        except Exception as exc:
            duration_ms = (time.perf_counter() - t0) * 1000
            thread_results[thread_name] = {
                "thread_name": thread_name,
                "recipient_id": recipient_id,
                "recipient_name": f"Wallet #{recipient_id}",
                "amount": transfer_amount,
                "status": "ROLLED BACK",
                "success": False,
                "start_time": start_time_iso,
                "duration_ms": round(duration_ms, 2),
                "transaction_id": None,
                "new_sender_balance": None,
                "details": "Rolled back safely by SQLite lock & balance verification rules.",
                "error": str(exc),
            }

    # Launch threads
    t1 = threading.Thread(target=worker_thread, args=("Thread-Alpha (Transfer 1)", recipient_1_id))
    t2 = threading.Thread(target=worker_thread, args=("Thread-Beta (Transfer 2)", recipient_2_id))

    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # 2. Fetch final balance
    sender_after = get_wallet_by_id(sender_wallet_id, db_path=db_path)
    final_balance = float(sender_after["balance"])

    # Analyze invariants
    successful_threads = [t for t in thread_results.values() if t["success"]]
    failed_threads = [t for t in thread_results.values() if not t["success"]]

    total_attempted = transfer_amount * 2
    total_deducted = round(initial_balance - final_balance, 2)
    double_spend_prevented = (final_balance >= 0) and (len(successful_threads) <= 1 or initial_balance >= total_attempted)

    return {
        "initial_balance": initial_balance,
        "final_balance": final_balance,
        "transfer_amount": transfer_amount,
        "total_attempted": total_attempted,
        "total_deducted": total_deducted,
        "double_spend_prevented": double_spend_prevented,
        "thread_results": thread_results,
        "successful_count": len(successful_threads),
        "failed_count": len(failed_threads),
    }


def create_test_sandbox_wallet(initial_balance: float = 1000.0, db_path: str = DB_PATH) -> Dict[str, Any]:
    """Create a temporary sandbox wallet for non-destructive concurrency testing."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE;")
        ts = int(time.time() * 1000) % 100000
        test_email = f"sandbox_{ts}@finvault.in"
        cursor.execute(
            """
            INSERT INTO users (name, email, phone, avatar_color)
            VALUES (?, ?, ?, '#f59e0b');
            """,
            (f"Sandbox Wallet #{ts}", test_email, f"+91-98765-{ts:05d}"),
        )
        user_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO wallets (user_id, balance, currency)
            VALUES (?, 0.00, 'INR');
            """,
            (user_id,),
        )
        wallet_id = cursor.lastrowid
        cursor.execute("COMMIT;")
        
        deposit_funds(wallet_id=wallet_id, amount=initial_balance, note=f"Sandbox Initial UPI Balance (₹{initial_balance:,.2f})", db_path=db_path)
        return {"user_id": user_id, "wallet_id": wallet_id, "initial_balance": initial_balance}
    except Exception:
        cursor.execute("ROLLBACK;")
        raise
    finally:
        conn.close()


def execute_readonly_query(sql: str, db_path: str = DB_PATH) -> Tuple[List[str], List[Dict[str, Any]], float]:
    """Executes an arbitrary read-only SQL query for the inspector playground."""
    sql_clean = sql.strip()
    allowed_prefixes = ("SELECT", "PRAGMA", "EXPLAIN", "WITH")
    if not any(sql_clean.upper().startswith(p) for p in allowed_prefixes):
        raise ValueError("Only read-only queries (SELECT, WITH, PRAGMA, EXPLAIN) are permitted in the inspector playground.")
    
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        t0 = time.perf_counter()
        cursor.execute(sql_clean)
        duration_ms = (time.perf_counter() - t0) * 1000
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = [dict(r) for r in cursor.fetchall()]
        log_query(query=sql_clean, duration_ms=duration_ms, rows_affected=len(rows), operation="PLAYGROUND_SELECT")
        return cols, rows, duration_ms
    finally:
        conn.close()


# ============================================================================
# USER & WALLET QUERY HELPERS (RAW SQL)
# ============================================================================

def get_all_users(db_path: str = DB_PATH) -> List[Dict[str, Any]]:
    """Fetch all users joined with their wallet details."""
    query = """
    SELECT 
        u.id AS user_id,
        u.name,
        u.email,
        u.phone,
        u.avatar_color,
        w.id AS wallet_id,
        w.balance,
        w.currency,
        w.updated_at
    FROM users u
    JOIN wallets w ON u.id = w.user_id
    ORDER BY u.id ASC;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        logged_execute(cursor, query, operation="GET_ALL_USERS")
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_user_by_id(user_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch a single user by user ID."""
    query = """
    SELECT 
        u.id AS user_id,
        u.name,
        u.email,
        u.phone,
        u.avatar_color,
        w.id AS wallet_id,
        w.balance,
        w.currency,
        w.updated_at
    FROM users u
    JOIN wallets w ON u.id = w.user_id
    WHERE u.id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        logged_execute(cursor, query, (user_id,), operation="GET_USER_BY_ID")
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_wallet_by_id(wallet_id: int, db_path: str = DB_PATH) -> Optional[Dict[str, Any]]:
    """Fetch a single wallet by wallet ID."""
    query = """
    SELECT 
        w.id AS wallet_id,
        w.user_id,
        w.balance,
        w.currency,
        u.name AS owner_name,
        u.email AS owner_email
    FROM wallets w
    JOIN users u ON w.user_id = u.id
    WHERE w.id = ?;
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()
        logged_execute(cursor, query, (wallet_id,), operation="GET_WALLET_BY_ID")
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ============================================================================
# ANALYTICS QUERIES (RAW SQL AGGREGATIONS)
# ============================================================================

def get_wallet_analytics(wallet_id: int, db_path: str = DB_PATH) -> Dict[str, Any]:
    """
    Compute aggregate financial statistics strictly via Raw SQL:
    - Total Credits (Income)
    - Total Debits (Expenses)
    - Monthly breakdown
    - Top counterparty breakdown
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.cursor()

        # 1. Total Income & Total Expenses
        totals_query = """
        SELECT 
            COALESCE(SUM(CASE WHEN receiver_wallet_id = ? THEN amount ELSE 0 END), 0) AS total_income,
            COALESCE(SUM(CASE WHEN sender_wallet_id = ? THEN amount ELSE 0 END), 0) AS total_expenses,
            COUNT(id) AS total_tx_count
        FROM transactions
        WHERE (sender_wallet_id = ? OR receiver_wallet_id = ?)
          AND status = 'COMPLETED';
        """
        logged_execute(cursor, totals_query, (wallet_id, wallet_id, wallet_id, wallet_id), operation="ANALYTICS_TOTALS")
        totals = dict(cursor.fetchone())

        # 2. Monthly Summary (Year-Month breakdown)
        monthly_query = """
        SELECT 
            strftime('%Y-%m', created_at) AS period,
            ROUND(COALESCE(SUM(CASE WHEN receiver_wallet_id = ? THEN amount ELSE 0 END), 0), 2) AS income,
            ROUND(COALESCE(SUM(CASE WHEN sender_wallet_id = ? THEN amount ELSE 0 END), 0), 2) AS expenses
        FROM transactions
        WHERE (sender_wallet_id = ? OR receiver_wallet_id = ?)
          AND status = 'COMPLETED'
        GROUP BY strftime('%Y-%m', created_at)
        ORDER BY period ASC;
        """
        logged_execute(cursor, monthly_query, (wallet_id, wallet_id, wallet_id, wallet_id), operation="ANALYTICS_MONTHLY")
        monthly_breakdown = [dict(r) for r in cursor.fetchall()]

        # 3. Counterparty Breakdown
        counterparty_query = """
        SELECT 
            CASE 
                WHEN sender_wallet_id = :wid THEN u_rec.name
                ELSE u_snd.name
            END AS counterparty,
            ROUND(SUM(amount), 2) AS total_volume,
            COUNT(t.id) AS tx_count
        FROM transactions t
        LEFT JOIN wallets w_snd ON t.sender_wallet_id = w_snd.id
        LEFT JOIN users u_snd ON w_snd.user_id = u_snd.id
        LEFT JOIN wallets w_rec ON t.receiver_wallet_id = w_rec.id
        LEFT JOIN users u_rec ON w_rec.user_id = u_rec.id
        WHERE (t.sender_wallet_id = :wid OR t.receiver_wallet_id = :wid)
          AND t.status = 'COMPLETED'
        GROUP BY counterparty
        ORDER BY total_volume DESC;
        """
        logged_execute(cursor, counterparty_query, {"wid": wallet_id}, operation="ANALYTICS_COUNTERPARTY")
        counterparties = [dict(r) for r in cursor.fetchall()]

        return {
            "total_income": float(totals["total_income"]),
            "total_expenses": float(totals["total_expenses"]),
            "net_flow": float(totals["total_income"]) - float(totals["total_expenses"]),
            "total_transactions": totals["total_tx_count"],
            "monthly_breakdown": monthly_breakdown,
            "counterparties": counterparties,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Testing FinVault database module (India / INR Localization)...")
    seed_demo_data(force_reset=True)
    users = get_all_users()
    print(f"Successfully seeded {len(users)} users:")
    for u in users:
        print(f" - [{u['user_id']}] {u['name']} (Wallet #{u['wallet_id']}): ₹{u['balance']:,.2f} {u['currency']}")
    
    print("\nTesting Concurrency Stress Test:")
    test_res = run_concurrency_stress_test(
        sender_wallet_id=1,
        recipient_1_id=2,
        recipient_2_id=3,
        transfer_amount=15000.0,
    )
    print(f"Initial: ₹{test_res['initial_balance']} | Final: ₹{test_res['final_balance']}")
    print(f"Double-spend prevented: {test_res['double_spend_prevented']}")
    for name, r in test_res["thread_results"].items():
        print(f" - {name}: {r['status']} in {r['duration_ms']}ms | Success: {r['success']}")
    
    logs = get_recent_query_logs(5)
    print(f"\nRecent query logs captured: {len(logs)}")
    for l in logs:
        print(f" [{l['timestamp']}] {l['operation']}: {l['duration_ms']}ms -> {l['status']}")
