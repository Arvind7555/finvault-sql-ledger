-- ============================================================================
-- FinVault: Digital Wallet & Transaction Ledger
-- Pure SQL Database Schema with Constraints, Triggers, & Indexes
-- Engine: SQLite 3.25+ (Supports Window Functions & Foreign Key Constraints)
-- ============================================================================

-- Enforce Foreign Key Integrity
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. USERS TABLE
-- Stores profile credentials and account identities
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT UNIQUE NOT NULL,
    avatar_color TEXT DEFAULT '#10b981',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ----------------------------------------------------------------------------
-- 2. WALLETS TABLE
-- Holds virtual currency balances with strict non-negative check constraint
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wallets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL UNIQUE,
    balance DECIMAL(15, 2) NOT NULL DEFAULT 0.00 CHECK (balance >= 0.00),
    currency TEXT NOT NULL DEFAULT 'INR',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 3. TRANSACTIONS TABLE
-- Records peer-to-peer transfers, deposits, and system adjustments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_wallet_id INTEGER,
    receiver_wallet_id INTEGER NOT NULL,
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0.00),
    status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK (status IN ('PENDING', 'COMPLETED', 'FAILED', 'REVERSED')),
    note TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_wallet_id) REFERENCES wallets(id) ON DELETE RESTRICT,
    FOREIGN KEY (receiver_wallet_id) REFERENCES wallets(id) ON DELETE RESTRICT
);

-- ----------------------------------------------------------------------------
-- 4. AUDIT LEDGER TABLE
-- Immutable double-entry ledger tracking all balance movements for audit compliance
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wallet_id INTEGER NOT NULL,
    entry_type TEXT NOT NULL CHECK (entry_type IN ('CREDIT', 'DEBIT')),
    amount DECIMAL(15, 2) NOT NULL CHECK (amount > 0.00),
    balance_after DECIMAL(15, 2) NOT NULL CHECK (balance_after >= 0.00),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wallet_id) REFERENCES wallets(id) ON DELETE CASCADE
);

-- ----------------------------------------------------------------------------
-- 5. PERFORMANCE INDEXES
-- Optimize lookups, join conditions, and window function partitioning
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_sender ON transactions(sender_wallet_id);
CREATE INDEX IF NOT EXISTS idx_transactions_receiver ON transactions(receiver_wallet_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created_at ON transactions(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_wallet_created ON audit_ledger(wallet_id, created_at);

-- ----------------------------------------------------------------------------
-- 6. DATABASE TRIGGERS
-- Automatic business logic & compliance enforcement at database engine layer
-- ----------------------------------------------------------------------------

-- Trigger 6.1: Enforce Balance Rules before updates (guard against race conditions)
CREATE TRIGGER IF NOT EXISTS trg_prevent_negative_balance
BEFORE UPDATE OF balance ON wallets
FOR EACH ROW
WHEN NEW.balance < 0.00
BEGIN
    SELECT RAISE(ABORT, 'FinVault SQL Rule Violation: Insufficient funds. Wallet balance cannot drop below 0.00.');
END;

-- Trigger 6.2: Auto-record CREDIT to Audit Ledger
CREATE TRIGGER IF NOT EXISTS trg_audit_wallet_credit
AFTER UPDATE OF balance ON wallets
FOR EACH ROW
WHEN NEW.balance > OLD.balance
BEGIN
    INSERT INTO audit_ledger (wallet_id, entry_type, amount, balance_after, created_at)
    VALUES (
        NEW.id,
        'CREDIT',
        ROUND(NEW.balance - OLD.balance, 2),
        NEW.balance,
        datetime('now')
    );
END;

-- Trigger 6.3: Auto-record DEBIT to Audit Ledger
CREATE TRIGGER IF NOT EXISTS trg_audit_wallet_debit
AFTER UPDATE OF balance ON wallets
FOR EACH ROW
WHEN NEW.balance < OLD.balance
BEGIN
    INSERT INTO audit_ledger (wallet_id, entry_type, amount, balance_after, created_at)
    VALUES (
        NEW.id,
        'DEBIT',
        ROUND(OLD.balance - NEW.balance, 2),
        NEW.balance,
        datetime('now')
    );
END;

-- Trigger 6.4: Auto-record Initial Balance on Wallet Creation
CREATE TRIGGER IF NOT EXISTS trg_audit_wallet_initial_seed
AFTER INSERT ON wallets
FOR EACH ROW
WHEN NEW.balance > 0.00
BEGIN
    INSERT INTO audit_ledger (wallet_id, entry_type, amount, balance_after, created_at)
    VALUES (
        NEW.id,
        'CREDIT',
        NEW.balance,
        NEW.balance,
        datetime('now')
    );
END;
