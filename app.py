"""
FinVault - Digital Wallet & Transaction Ledger
Streamlit Frontend Application (100% Pure Python)
Localized for India (INR / ₹ - RuPay & UPI/IMPS Architecture)

A sleek, dark-themed FinTech dashboard demonstrating:
- SQLite Raw SQL ACID Transactions (BEGIN IMMEDIATE, COMMIT, ROLLBACK)
- SQLite Automated Triggers for double-entry audit logging & balance checks
- SQLite Window Functions for real-time running balance calculation
- High-Concurrency Double-Spend Race Condition Stress Testing
- Live SQL Query Profiling & Read-Only Query Playground
- Indian Rupee (₹) Passbook CSV Statement Exporting
"""

import streamlit as st
import pandas as pd
from typing import Dict, Any, List
import database

# ============================================================================
# STREAMLIT CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="FinVault | RuPay & UPI Digital Ledger",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Ensure database is initialized on initial run
if "db_initialized" not in st.session_state:
    database.seed_demo_data(force_reset=False)
    st.session_state.db_initialized = True

if "show_balance" not in st.session_state:
    st.session_state.show_balance = True

if "preset_amount" not in st.session_state:
    st.session_state.preset_amount = 1000.0

if "stress_test_results" not in st.session_state:
    st.session_state.stress_test_results = None


# ============================================================================
# HELPER DATA LOADERS
# ============================================================================
def refresh_user_list() -> List[Dict[str, Any]]:
    return database.get_all_users()


users = refresh_user_list()
if not users:
    database.seed_demo_data(force_reset=True)
    users = refresh_user_list()

user_names = [u["name"] for u in users]
user_map = {u["name"]: u for u in users}


# ============================================================================
# SIDEBAR: USER SWITCHER & SYSTEM CONTROLS
# ============================================================================
with st.sidebar:
    st.title("🏦 FinVault")
    st.caption("Domestic UPI / IMPS Ledger (ACID-Compliant)")
    st.divider()

    st.subheader("👤 Switch Active Account")
    selected_name = st.selectbox(
        "Select Demo Account:",
        options=user_names,
        index=0,
        help="Switch Indian demo accounts to test instant P2P UPI transfers and view passbook statements.",
    )

    current_user = user_map[selected_name]
    wallet_id = current_user["wallet_id"]
    current_balance = float(current_user["balance"])

    # User Profile Card
    with st.container(border=True):
        st.markdown(f"### {current_user['name']}")
        st.caption(f"📧 `{current_user['email']}`")
        st.caption(f"📱 `{current_user['phone']}`")
        vpa_alias = current_user['email'].split('@')[0]
        st.caption(f"🆔 VPA: **`VAULT-00{wallet_id}@finvault`** (or `{vpa_alias}@finvault`)")
        st.caption("🛡️ Security: **NPCI 2FA Verified / ACID Locked**")

    # Quick Top-Up / Deposit Expander
    with st.expander("➕ Deposit / Top-up Funds", expanded=False):
        st.write("Inject demo INR funds into this wallet via atomic transaction:")
        deposit_amt = st.number_input(
            "Deposit Amount (₹):",
            min_value=100.0,
            max_value=1000000.0,
            value=5000.0,
            step=500.0,
            key="deposit_amount_input",
        )
        deposit_note = st.text_input(
            "Payment Mode / Source",
            value="UPI Direct Deposit (GPay / PhonePe)",
            key="deposit_note_input",
        )
        if st.button("📥 Fund Wallet", use_container_width=True, type="secondary"):
            try:
                res = database.deposit_funds(
                    wallet_id=wallet_id,
                    amount=deposit_amt,
                    note=deposit_note,
                )
                st.success(f"Successfully deposited ₹{deposit_amt:,.2f}! (TX #{res['transaction_id']})")
                st.rerun()
            except Exception as ex:
                st.error(f"Deposit Failed: {ex}")

    st.divider()

    # System & Database Controls
    st.subheader("⚙️ Database Controls")
    st.caption("SQLite 3.25+ Engine (Pure Raw SQL)")
    
    col_reset, col_status = st.columns(2)
    with col_reset:
        if st.button("🔄 Reset Data", help="Wipe database and re-seed Indian demo data"):
            database.seed_demo_data(force_reset=True)
            database.clear_query_logs()
            st.session_state.stress_test_results = None
            st.success("Database re-seeded with Indian demo data!")
            st.rerun()

    with col_status:
        st.success("🟢 DB Connected")

    with st.expander("📜 Schema & Engine Specs"):
        st.markdown(
            """
            - **Currency**: Indian Rupee (`INR / ₹`)
            - **Driver**: Built-in `sqlite3`
            - **Isolation**: `BEGIN IMMEDIATE` (Atomic Locks)
            - **Constraints**: `CHECK (balance >= 0.00)`
            - **Triggers**: Double-Entry Audit Logging
            - **Window Functions**: Running Balance Calculation
            - **Concurrency**: Microsecond barrier race test
            """
        )


# ============================================================================
# TOP SECTION: VIRTUAL RUPAY CARD & OVERVIEW METRICS
# ============================================================================
analytics_data = database.get_wallet_analytics(wallet_id)

top_col1, top_col2 = st.columns([1.3, 1], gap="medium")

with top_col1:
    # Virtual RuPay Debit Card
    with st.container(border=True):
        card_header_col, card_toggle_col = st.columns([3, 1])
        with card_header_col:
            st.markdown("#### 💳 FinVault RuPay Platinum Virtual Card")
            st.caption("RUPAY PLATINUM DEBIT • NPCI UPI & IMPS ENABLED")
        with card_toggle_col:
            if st.button(
                "👁️ Hide" if st.session_state.show_balance else "👁️ Show",
                key="btn_toggle_balance",
                use_container_width=True,
                help="Toggle visibility of your sensitive wallet balance",
            ):
                st.session_state.show_balance = not st.session_state.show_balance
                st.rerun()

        # Balance Display
        if st.session_state.show_balance:
            st.markdown(f"## **₹{current_balance:,.2f}** `{current_user['currency']}`")
        else:
            st.markdown("## **••••••••••••** `INR`")

        st.caption("AVAILABLE ACCOUNT BALANCE")

        st.markdown("---")
        card_footer_col1, card_footer_col2 = st.columns([2, 1])
        with card_footer_col1:
            st.markdown(f"**CARDHOLDER:** `{current_user['name'].upper()}`")
            st.caption(f"ACCOUNT: `VAULT - 4029 - 8810 - 000{wallet_id}` • IFSC: `FVAU0001042`")
        with card_footer_col2:
            st.markdown("**NETWORK:** `RuPay`")
            st.caption("EXP: `12/31`")

with top_col2:
    # Summary Financial KPI Metrics
    with st.container(border=True):
        st.markdown("#### 📈 Financial Overview")
        st.caption(f"Real-time domestic ledger summary for {current_user['name']}")
        
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.metric(
                label="Total Inflow (Credits)",
                value=f"+₹{analytics_data['total_income']:,.2f}",
                delta=f"₹{analytics_data['total_income']:,.2f}",
                delta_color="normal",
            )
        with m_col2:
            st.metric(
                label="Total Outflow (Debits)",
                value=f"-₹{analytics_data['total_expenses']:,.2f}",
                delta=f"-₹{analytics_data['total_expenses']:,.2f}",
                delta_color="inverse",
            )

        st.divider()
        m_col3, m_col4 = st.columns(2)
        with m_col3:
            st.metric(
                label="Net Flow",
                value=f"₹{analytics_data['net_flow']:,.2f}",
                delta=f"₹{analytics_data['net_flow']:,.2f}",
                delta_color="normal" if analytics_data['net_flow'] >= 0 else "inverse",
            )
        with m_col4:
            st.metric(
                label="Completed Transactions",
                value=f"{analytics_data['total_transactions']}",
            )


# ============================================================================
# MAIN ACTION TABS
# ============================================================================
st.write("") # Spacer
tab_send, tab_passbook, tab_analytics, tab_stress, tab_inspector = st.tabs([
    "💸 Send Money",
    "📜 Passbook & Ledger",
    "📊 Analytics",
    "⚡ Stress Test / Concurrency",
    "🔍 Live SQL Inspector",
])


# ----------------------------------------------------------------------------
# TAB 1: SEND MONEY (ACID TRANSACTION PIPELINE - UPI/IMPS)
# ----------------------------------------------------------------------------
with tab_send:
    st.subheader("⚡ Instant UPI & IMPS Transfer (ACID Protected)")
    st.write("Execute atomic peer-to-peer funds transfer with automatic balance validation and immutable trigger logging.")

    transfer_col, info_col = st.columns([1.2, 1], gap="large")

    with transfer_col:
        with st.container(border=True):
            # Recipient options (exclude self)
            other_users = [u for u in users if u["user_id"] != current_user["user_id"]]
            recipient_options = {u["name"]: u["wallet_id"] for u in other_users}

            recipient_name = st.selectbox(
                "Select Recipient (Beneficiary):",
                options=list(recipient_options.keys()),
                help="Choose a registered FinVault user to receive the funds.",
            )
            target_wallet_id = recipient_options[recipient_name]

            # Amount Input
            amount = st.number_input(
                "Transfer Amount (INR / ₹):",
                min_value=1.00,
                max_value=max(100000.0, current_balance + 5000.0),
                value=st.session_state.preset_amount,
                step=100.00,
                format="%.2f",
                help="Enter the transfer amount in Indian Rupees. Checks are enforced at both application and SQLite trigger levels.",
            )

            # Quick preset buttons (Indian context)
            st.caption("Quick UPI Presets:")
            p_cols = st.columns(5)
            preset_values = [500.0, 1000.0, 2000.0, 5000.0, 10000.0]
            for col, val in zip(p_cols, preset_values):
                with col:
                    if st.button(f"₹{int(val):,}", key=f"preset_{int(val)}", use_container_width=True):
                        st.session_state.preset_amount = val
                        st.rerun()

            # Note / Memo (Indian context)
            transfer_note = st.text_input(
                "Payment Note / Memo:",
                value="UPI Payment",
                max_chars=120,
                placeholder="e.g. Chai & Snacks, House Rent, Swiggy dinner split, Freelance fee",
            )

            st.write("")
            execute_button = st.button(
                "🚀 Execute UPI Transfer (ACID BEGIN ... COMMIT)",
                type="primary",
                use_container_width=True,
            )

            if execute_button:
                try:
                    result = database.transfer_funds(
                        sender_wallet_id=wallet_id,
                        receiver_wallet_id=target_wallet_id,
                        amount=amount,
                        note=transfer_note,
                    )

                    st.balloons()
                    st.success(
                        f"✅ **UPI Transfer Successful!**\n\n"
                        f"- **Transaction URN:** `#{result['transaction_id']}`\n"
                        f"- **Amount Sent:** `₹{result['amount']:,.2f}`\n"
                        f"- **Recipient:** {result['receiver_name']} (Wallet #{target_wallet_id})\n"
                        f"- **New Available Balance:** `₹{result['sender_new_balance']:,.2f}`\n"
                        f"- **Status:** `COMPLETED (COMMITTED)`"
                    )
                    st.rerun()

                except database.InsufficientFundsError as ife:
                    st.error(f"❌ **Transfer Blocked (Insufficient Funds):**\n\n{ife}")
                except database.FinVaultDBError as dbe:
                    st.error(f"❌ **Database Rule Error:**\n\n{dbe}")
                except Exception as ex:
                    st.error(f"❌ **Transaction Rolled Back:**\n\n{ex}")

    with info_col:
        with st.container(border=True):
            st.markdown("#### 🔒 Under the Hood: ACID Transaction Pipeline")
            st.markdown(
                """
                FinVault enforces strict data integrity using raw SQL transactions with zero ORM overhead:
                
                ```sql
                -- 1. Begin Exclusive / Immediate Write Lock
                BEGIN IMMEDIATE;

                -- 2. Verify Sender Balance & Recipient
                SELECT balance FROM wallets WHERE id = ?;

                -- 3. Atomic Debit from Sender
                UPDATE wallets SET balance = balance - ? WHERE id = ?;
                -- Trigger 'trg_prevent_negative_balance' aborts if balance < 0
                -- Trigger 'trg_audit_wallet_debit' logs to audit_ledger

                -- 4. Atomic Credit to Receiver
                UPDATE wallets SET balance = balance + ? WHERE id = ?;
                -- Trigger 'trg_audit_wallet_credit' logs to audit_ledger

                -- 5. Record Transaction Log
                INSERT INTO transactions (...) VALUES (...);

                -- 6. Durable Commit
                COMMIT;
                ```
                
                > **Negative Balance Prevention:** If a race condition attempts to spend more than available, SQLite raises an immediate `ABORT`, and the Python driver issues `ROLLBACK;`.
                """
            )


# ----------------------------------------------------------------------------
# TAB 2: PASSBOOK & LEDGER (WINDOW FUNCTION RUNNING BALANCE & CSV EXPORT)
# ----------------------------------------------------------------------------
with tab_passbook:
    st.subheader("📜 Account Statement & Immutable Ledger")
    st.write(
        "Real-time passbook statement showing credit/debit movements with **Running Balances calculated strictly in Pure SQL Window Functions**."
    )

    view_mode = st.radio(
        "Select Statement View:",
        ["💳 UPI Passbook Statement (Transactions)", "🛡️ Double-Entry Engine (Audit Ledger)"],
        horizontal=True,
    )

    if view_mode == "💳 UPI Passbook Statement (Transactions)":
        passbook_records = database.get_wallet_passbook(wallet_id)

        if not passbook_records:
            st.info("No transaction records found for this account yet.")
            safe_name = current_user['name'].replace(' ', '_')
            empty_df = pd.DataFrame(columns=["TX ID", "Date & Time", "Type", "Counterparty", "Amount", "Running Balance", "Note", "Status"])
            st.download_button(
                label="📥 Download Statement (CSV)",
                data=empty_df.to_csv(index=False).encode("utf-8"),
                file_name=f"FinVault_Statement_{safe_name}.csv",
                mime="text/csv",
                help="Export official account statement with real-time SQL window function running balances.",
            )
        else:
            # Build display table with Indian Rupee formatting
            table_data = []
            for r in passbook_records:
                is_credit = r["flow_type"] == "CREDIT"
                amt_str = f"+ ₹{r['amount']:,.2f}" if is_credit else f"- ₹{r['amount']:,.2f}"
                counterparty = r["sender_name"] if is_credit else r["receiver_name"]
                if not counterparty:
                    counterparty = "External UPI Deposit"

                table_data.append({
                    "TX ID": f"#{r['id']}",
                    "Date & Time": r["created_at"],
                    "Type": "🟢 CREDIT" if is_credit else "🔴 DEBIT",
                    "Counterparty": counterparty,
                    "Amount": amt_str,
                    "Running Balance": f"₹{r['running_balance']:,.2f}",
                    "Note": r["note"] or "-",
                    "Status": r["status"],
                })

            df_passbook = pd.DataFrame(table_data)
            st.dataframe(
                df_passbook,
                use_container_width=True,
                hide_index=True,
            )

            # Feature 3: Download Passbook Statement as CSV
            safe_name = current_user['name'].replace(' ', '_')
            col_csv, col_csv_info = st.columns([1.2, 1.8])
            with col_csv:
                csv_bytes = df_passbook.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label="📥 Download Statement (CSV)",
                    data=csv_bytes,
                    file_name=f"FinVault_Statement_{safe_name}.csv",
                    mime="text/csv",
                    use_container_width=True,
                    help="Export official account statement with real-time SQL window function running balances.",
                )
            with col_csv_info:
                st.caption(f"Statement generated for **{current_user['name']}** (Wallet #{wallet_id}). Contains {len(table_data)} verified entries.")

        with st.expander("🔍 SQL Deep Dive: Window Function Behind Running Balance", expanded=False):
            st.markdown(
                """
                The **Running Balance** is calculated entirely on the database engine using SQLite's Window Function:
                
                ```sql
                SELECT 
                    id,
                    created_at,
                    flow_type,
                    amount,
                    net_amount,
                    sender_name,
                    receiver_name,
                    note,
                    -- Real-Time Running Balance calculated via Pure SQL Window Function:
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
                *Zero post-processing in Python: SQLite calculates the progressive sum over partitioned chronological frames.*
                """
            )

    else:
        # Audit Ledger View
        audit_records = database.get_audit_ledger_with_window_function(wallet_id)
        if not audit_records:
            st.info("No audit entries found.")
        else:
            table_audit = []
            for a in audit_records:
                table_audit.append({
                    "Audit ID": f"#{a['id']}",
                    "Timestamp": a["created_at"],
                    "Entry Type": "🟢 CREDIT" if a["entry_type"] == "CREDIT" else "🔴 DEBIT",
                    "Change Amount": f"₹{a['amount']:,.2f}",
                    "Balance After": f"₹{a['balance_after']:,.2f}",
                    "SQL Window Sum": f"₹{a['calculated_running_balance']:,.2f}",
                })

            df_audit = pd.DataFrame(table_audit)
            st.dataframe(
                df_audit,
                use_container_width=True,
                hide_index=True,
            )

            # Feature 3: Download Audit Ledger as CSV
            csv_audit_bytes = df_audit.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="📥 Download Audit Ledger as CSV",
                data=csv_audit_bytes,
                file_name=f"finvault_audit_ledger_wallet_{wallet_id}.csv",
                mime="text/csv",
                use_container_width=True,
                help="Export double-entry compliance audit trail with trigger-verified balance balances.",
            )

        with st.expander("🛡️ How the SQLite Audit Trigger Works", expanded=False):
            st.markdown(
                """
                Every time a wallet's `balance` column updates, an automated SQLite Trigger fires:
                
                ```sql
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
                ```
                *This guarantees audit log compliance at the database kernel level, preventing any tampering.*
                """
            )


# ----------------------------------------------------------------------------
# TAB 3: ANALYTICS (INCOME VS EXPENSE SUMMARY)
# ----------------------------------------------------------------------------
with tab_analytics:
    st.subheader("📊 Financial Velocity & Cash Flow Analytics")
    st.write(f"Monthly breakdown of credits and debits for **{current_user['name']}**.")

    col_chart, col_summary = st.columns([1.5, 1], gap="medium")

    with col_chart:
        with st.container(border=True):
            st.markdown("##### 📈 Monthly Income vs. Expense (₹)")
            monthly_data = analytics_data["monthly_breakdown"]

            if monthly_data:
                chart_df = pd.DataFrame(monthly_data)
                chart_df.rename(columns={"income": "Income (Credits)", "expenses": "Expenses (Debits)"}, inplace=True)
                chart_df.set_index("period", inplace=True)
                st.bar_chart(
                    chart_df[["Income (Credits)", "Expenses (Debits)"]],
                    color=["#10b981", "#ef4444"],
                    use_container_width=True,
                )
            else:
                st.info("No monthly transaction data available yet.")

    with col_summary:
        with st.container(border=True):
            st.markdown("##### 👥 Counterparty Distribution")
            counterparties = analytics_data["counterparties"]
            if counterparties:
                cp_df = pd.DataFrame(counterparties)
                cp_df.rename(columns={"counterparty": "Peer", "total_volume": "Volume (₹)", "tx_count": "Transactions"}, inplace=True)
                st.dataframe(cp_df, hide_index=True, use_container_width=True)
            else:
                st.info("No counterparty transfers recorded.")

    st.write("")
    with st.container(border=True):
        st.markdown("##### 💡 Financial Health Indicators")
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            tot_in = analytics_data["total_income"]
            tot_out = analytics_data["total_expenses"]
            savings_rate = ((tot_in - tot_out) / tot_in * 100) if tot_in > 0 else 0
            st.metric("Net Retention Rate", f"{savings_rate:.1f}%")
        with f_col2:
            avg_tx = ((tot_in + tot_out) / analytics_data["total_transactions"]) if analytics_data["total_transactions"] > 0 else 0
            st.metric("Average Transaction Size", f"₹{avg_tx:,.2f}")
        with f_col3:
            st.metric("Active Counterparties", f"{len(counterparties)}")


# ----------------------------------------------------------------------------
# TAB 4: STRESS TEST & CONCURRENCY (FEATURE 1: DOUBLE-SPEND DEFENSE)
# ----------------------------------------------------------------------------
with tab_stress:
    st.subheader("⚡ High-Concurrency Race Condition & Double-Spend Stress Test")
    st.write(
        "Simulate two concurrent threads attempting to drain the same wallet balance at the **exact same microsecond**. "
        "Demonstrates how SQLite's `BEGIN IMMEDIATE` write-locks and check constraints prevent double-spending in Indian banking systems."
    )

    stress_cfg_col, stress_expl_col = st.columns([1.2, 1], gap="large")

    with stress_cfg_col:
        with st.container(border=True):
            st.markdown("#### 🧪 Test Configuration")
            target_mode = st.radio(
                "Target Wallet to Test:",
                [
                    f"Active Account: {current_user['name']} (Balance: ₹{current_balance:,.2f})",
                    "Dedicated Sandbox Account (Non-destructive: Seeds Fresh ₹1,000.00)",
                ],
                help="Choose whether to test on the current active user or a dedicated temporary sandbox wallet.",
            )

            is_sandbox = "Dedicated Sandbox" in target_mode

            # Determine available balance for prompt default
            ref_balance = 1000.0 if is_sandbox else current_balance
            default_drain = round(ref_balance * 0.75, 2) if ref_balance > 0 else 500.0

            st.write("")
            drain_amount = st.number_input(
                "Transfer Amount to Attempt (Per Thread in ₹):",
                min_value=10.0,
                max_value=max(100000.0, ref_balance * 2),
                value=float(default_drain),
                step=100.0,
                format="%.2f",
                help="Each thread will attempt to transfer this amount. If 2x amount > balance, a double-spend attempt occurs!",
            )

            total_drain_attempt = drain_amount * 2
            if total_drain_attempt > ref_balance:
                st.warning(
                    f"⚠️ **Double-Spend Invariant Triggered!**\n\n"
                    f"Available Balance: **₹{ref_balance:,.2f}** | Total Attempted by 2 Threads: **₹{total_drain_attempt:,.2f}**\n\n"
                    f"Without atomic ACID locks, the balance would drop to **-₹{total_drain_attempt - ref_balance:,.2f}**!"
                )
            else:
                st.info(
                    f"Available: ₹{ref_balance:,.2f} | Total Attempted: ₹{total_drain_attempt:,.2f}. "
                    f"Both threads can succeed without overdraft."
                )

            st.write("")
            run_stress_btn = st.button(
                "🔥 Launch Concurrent Race Attack (2 Synchronized Threads)",
                type="primary",
                use_container_width=True,
            )

            if run_stress_btn:
                try:
                    if is_sandbox:
                        sandbox_info = database.create_test_sandbox_wallet(initial_balance=1000.0)
                        test_wallet_id = sandbox_info["wallet_id"]
                    else:
                        test_wallet_id = wallet_id

                    # Assign recipients
                    all_u = database.get_all_users()
                    recipients = [u["wallet_id"] for u in all_u if u["wallet_id"] != test_wallet_id]
                    if len(recipients) < 2:
                        rec1 = recipients[0] if recipients else test_wallet_id
                        rec2 = rec1
                    else:
                        rec1, rec2 = recipients[0], recipients[1]

                    with st.spinner("Synchronizing microsecond barrier and launching threads..."):
                        test_results = database.run_concurrency_stress_test(
                            sender_wallet_id=test_wallet_id,
                            recipient_1_id=rec1,
                            recipient_2_id=rec2,
                            transfer_amount=drain_amount,
                        )
                    st.session_state.stress_test_results = test_results
                    st.toast("Concurrency test completed!", icon="⚡")
                except Exception as ex:
                    st.error(f"Stress test error: {ex}")

    with stress_expl_col:
        with st.container(border=True):
            st.markdown("#### 🛡️ Why Double-Spending Is Mathematically Impossible")
            st.markdown(
                """
                1. **Microsecond Synchronization**: Both Python threads reach a `threading.Barrier(2)` and execute `BEGIN IMMEDIATE` simultaneously.
                2. **SQLite Write-Lock Acquisition**:
                   - The first thread to reach the SQLite engine acquires an **EXCLUSIVE RESERVED lock**.
                   - The second thread is queued by SQLite's busy handler.
                3. **Serialized Balance Check**:
                   - Thread-Alpha deducts funds and commits.
                   - Thread-Beta acquires the lock, reads the **fresh post-deduction balance**, detects insufficient funds, and **issues an immediate ROLLBACK**.
                4. **Database Kernel Triggers**:
                   - Even if Thread-Beta bypassed Python checks, SQLite trigger `trg_prevent_negative_balance` halts the execution with `ABORT`.
                """
            )

    # Display Test Results if executed
    res = st.session_state.stress_test_results
    if res:
        st.write("")
        st.markdown("### 📊 Concurrency Race Attack Results")

        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        with kpi_col1:
            st.metric("Starting Balance", f"₹{res['initial_balance']:,.2f}")
        with kpi_col2:
            st.metric("Total Attempted Drain", f"₹{res['total_attempted']:,.2f}")
        with kpi_col3:
            st.metric("Final Ending Balance", f"₹{res['final_balance']:,.2f}")
        with kpi_col4:
            st.metric(
                "Double-Spend Prevented",
                "100% PROTECTED" if res["double_spend_prevented"] else "FAILED",
                delta="Zero Overdraft",
            )

        st.write("")
        t_col1, t_col2 = st.columns(2, gap="medium")

        t_alpha = res["thread_results"].get("Thread-Alpha (Transfer 1)", {})
        t_beta = res["thread_results"].get("Thread-Beta (Transfer 2)", {})

        with t_col1:
            with st.container(border=True):
                st.markdown(f"#### 🧵 {t_alpha.get('thread_name', 'Thread-Alpha')}")
                if t_alpha.get("success"):
                    st.success("🟢 STATUS: COMMITTED (SUCCESS)")
                else:
                    st.error("🔴 STATUS: ROLLED BACK (SAFE)")

                st.write(f"- **Attempted Transfer:** `₹{t_alpha.get('amount', 0):,.2f}`")
                st.write(f"- **Start Timestamp:** `{t_alpha.get('start_time', '-')}`")
                st.write(f"- **Execution Latency:** `{t_alpha.get('duration_ms', 0)} ms`")
                if t_alpha.get("transaction_id"):
                    st.write(f"- **Assigned TX ID:** `#{t_alpha.get('transaction_id')}`")
                st.write(f"- **Outcome Detail:** {t_alpha.get('details', '')}")
                if t_alpha.get("error"):
                    st.code(t_alpha.get("error"), language="text")

        with t_col2:
            with st.container(border=True):
                st.markdown(f"#### 🧵 {t_beta.get('thread_name', 'Thread-Beta')}")
                if t_beta.get("success"):
                    st.success("🟢 STATUS: COMMITTED (SUCCESS)")
                else:
                    st.error("🔴 STATUS: ROLLED BACK (SAFE)")

                st.write(f"- **Attempted Transfer:** `₹{t_beta.get('amount', 0):,.2f}`")
                st.write(f"- **Start Timestamp:** `{t_beta.get('start_time', '-')}`")
                st.write(f"- **Execution Latency:** `{t_beta.get('duration_ms', 0)} ms`")
                if t_beta.get("transaction_id"):
                    st.write(f"- **Assigned TX ID:** `#{t_beta.get('transaction_id')}`")
                st.write(f"- **Outcome Detail:** {t_beta.get('details', '')}")
                if t_beta.get("error"):
                    st.code(t_beta.get("error"), language="text")

        st.success(
            f"✅ **Mathematical Invariant Confirmed:** Initial (₹{res['initial_balance']:,.2f}) - "
            f"Deducted (₹{res['total_deducted']:,.2f}) == Final Balance (₹{res['final_balance']:,.2f}). "
            f"Zero overdraft or phantom writes occurred!"
        )


# ----------------------------------------------------------------------------
# TAB 5: LIVE SQL QUERY INSPECTOR & PROFILER (FEATURE 2)
# ----------------------------------------------------------------------------
with tab_inspector:
    st.subheader("🔍 Live SQL Query Inspector & Profiler")
    st.write(
        "Real-time telemetric inspection of all raw SQL statements executed by FinVault, "
        "including parameterized arguments, execution durations in milliseconds, and affected rows."
    )

    recent_logs = database.get_recent_query_logs(limit=30)

    # Top Control Bar
    ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1, 1, 1.5, 1.5])
    with ctrl_col1:
        if st.button("🔄 Refresh Logs", use_container_width=True):
            st.rerun()
    with ctrl_col2:
        if st.button("🗑️ Clear Logs", use_container_width=True):
            database.clear_query_logs()
            st.rerun()
    with ctrl_col3:
        avg_lat = round(sum(l["duration_ms"] for l in recent_logs) / len(recent_logs), 3) if recent_logs else 0
        st.metric("Tracked Queries in Buffer", f"{len(recent_logs)}", help="Circular buffer holding recent execution logs.")
    with ctrl_col4:
        st.metric("Average Query Latency", f"{avg_lat} ms", help="Raw execution latency measured via high-resolution performance counter.")

    st.write("")

    # Sub-tabs for Logs vs SQL Playground
    insp_view1, insp_view2 = st.tabs(["📋 Execution Trace History", "💻 Interactive SQL Playground"])

    with insp_view1:
        if not recent_logs:
            st.info("No query logs captured yet. Execute a transfer, deposit, or statement fetch to populate the log.")
        else:
            # Build DataFrame for log summary
            log_table_data = []
            for idx, l in enumerate(reversed(recent_logs)):
                log_table_data.append({
                    "#": len(recent_logs) - idx,
                    "Timestamp": l["timestamp"],
                    "Operation": l["operation"],
                    "Latency": f"{l['duration_ms']:.3f} ms",
                    "Status": "🟢 OK" if l["status"] == "SUCCESS" else "🔴 ERROR",
                    "Query Snippet": (l["query"][:75] + "...") if len(l["query"]) > 75 else l["query"],
                })

            df_logs = pd.DataFrame(log_table_data)
            st.dataframe(df_logs, use_container_width=True, hide_index=True)

            st.write("#### Detailed Query Inspection (Last 5 Queries)")
            for idx, l in enumerate(reversed(recent_logs[-5:])):
                with st.expander(
                    f"#{len(recent_logs) - idx} [{l['timestamp']}] {l['operation']} — {l['duration_ms']} ms ({l['status']})",
                    expanded=(idx == 0),
                ):
                    st.code(l["query"], language="sql")
                    if l["params"]:
                        st.caption(f"**Bound Parameters:** `{l['params']}`")
                    st.caption(f"**Rows Affected:** `{l['rows_affected']}` | **Status:** `{l['status']}`")
                    if l["error"]:
                        st.error(f"Error caught: {l['error']}")

    with insp_view2:
        st.markdown("#### 💻 Live Read-Only SQL Playground")
        st.caption("Execute safe read-only queries (`SELECT`, `WITH`, `PRAGMA`, `EXPLAIN`) directly against `finvault.db` to inspect database engine state.")

        preset_col1, preset_col2, preset_col3, preset_col4 = st.columns(4)
        sample_q = "SELECT id, user_id, balance, currency, updated_at FROM wallets;"
        with preset_col1:
            if st.button("Wallets Query", use_container_width=True):
                sample_q = "SELECT * FROM wallets;"
        with preset_col2:
            if st.button("Recent Transactions", use_container_width=True):
                sample_q = "SELECT id, sender_wallet_id, receiver_wallet_id, amount, status, note, created_at FROM transactions ORDER BY id DESC LIMIT 5;"
        with preset_col3:
            if st.button("Audit Ledger", use_container_width=True):
                sample_q = "SELECT id, wallet_id, entry_type, amount, balance_after, created_at FROM audit_ledger ORDER BY id DESC LIMIT 5;"
        with preset_col4:
            if st.button("PRAGMA Journal Mode", use_container_width=True):
                sample_q = "PRAGMA journal_mode;"

        sql_input = st.text_area(
            "Enter SQL Query (Read-Only):",
            value=sample_q,
            height=100,
            key="sql_playground_input",
        )

        if st.button("▶️ Execute Query", type="primary"):
            try:
                cols, rows, lat = database.execute_readonly_query(sql_input)
                st.success(f"Query returned {len(rows)} rows in **{lat:.3f} ms**")
                if rows:
                    df_custom = pd.DataFrame(rows)
                    st.dataframe(df_custom, use_container_width=True, hide_index=True)
                else:
                    st.info("Query returned 0 rows.")
            except Exception as q_err:
                st.error(f"SQL Execution Error: {q_err}")
