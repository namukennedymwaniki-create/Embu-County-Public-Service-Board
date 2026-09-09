# leave_management_module.py
"""
County CLMS - Leave Management Module
Can be imported into your existing Streamlit app
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import traceback
import sqlite3
import psycopg2

# =========================================================
# DATABASE CONNECTION
# =========================================================
def get_conn():
    """Get database connection - works on both local and Streamlit Cloud"""
    
    # Check if we're on Streamlit Cloud with a DATABASE_URL secret
    database_url = st.secrets.get("DATABASE_URL")
    
    if database_url:
        # Running on Streamlit Cloud - use PostgreSQL
        try:
            # Ensure SSL is enabled for Neon
            if "sslmode" not in database_url:
                if "?" in database_url:
                    database_url += "&sslmode=require"
                else:
                    database_url += "?sslmode=require"
            
            conn = psycopg2.connect(
                database_url,
                connect_timeout=30,
                keepalives=1,
                keepalives_idle=5,
                keepalives_interval=2,
                keepalives_count=2
            )
            return conn
            
        except Exception as e:
            st.error(f"❌ Database connection failed: {e}")
            return None
    else:
        # Running locally - use SQLite
        return sqlite3.connect("ecde.db", check_same_thread=False)
# =========================================================
# LEAVE MANAGEMENT TABLES
# =========================================================
def migrate_leave_tables():
    """Create leave management tables in both SQLite and PostgreSQL"""
    try:
        conn = get_conn()
        if conn is None:
            print("Cannot connect to database for leave migration")
            return
        
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        if is_cloud:
            # PostgreSQL
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_types (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE,
                    code TEXT UNIQUE,
                    default_days INTEGER DEFAULT 21,
                    description TEXT,
                    require_approval BOOLEAN DEFAULT TRUE,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_entitlements (
                    id SERIAL PRIMARY KEY,
                    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
                    leave_type_id INTEGER REFERENCES leave_types(id) ON DELETE CASCADE,
                    year INTEGER,
                    allocated_days NUMERIC(10,2) DEFAULT 0,
                    used_days NUMERIC(10,2) DEFAULT 0,
                    pending_days NUMERIC(10,2) DEFAULT 0,
                    carry_forward_days NUMERIC(10,2) DEFAULT 0,
                    UNIQUE(employee_id, leave_type_id, year)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_applications (
                    id SERIAL PRIMARY KEY,
                    application_no TEXT UNIQUE,
                    employee_id INTEGER REFERENCES employees(id) ON DELETE CASCADE,
                    leave_type_id INTEGER REFERENCES leave_types(id) ON DELETE CASCADE,
                    start_date DATE,
                    end_date DATE,
                    requested_days INTEGER,
                    working_days INTEGER,
                    reason TEXT,
                    status TEXT DEFAULT 'Pending Supervisor',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    supervisor_approved_at TIMESTAMP,
                    hr_approved_at TIMESTAMP,
                    rejection_reason TEXT,
                    cancelled_at TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_approvals (
                    id SERIAL PRIMARY KEY,
                    application_id INTEGER REFERENCES leave_applications(id) ON DELETE CASCADE,
                    approver_id INTEGER REFERENCES users(id),
                    stage TEXT,
                    action TEXT,
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public_holidays (
                    id SERIAL PRIMARY KEY,
                    holiday_date DATE UNIQUE,
                    description TEXT,
                    year INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_applications_employee ON leave_applications(employee_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_applications_status ON leave_applications(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_entitlements_employee ON leave_entitlements(employee_id)")
            
        else:
            # SQLite
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    code TEXT UNIQUE,
                    default_days INTEGER DEFAULT 21,
                    description TEXT,
                    require_approval INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_entitlements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER,
                    leave_type_id INTEGER,
                    year INTEGER,
                    allocated_days REAL DEFAULT 0,
                    used_days REAL DEFAULT 0,
                    pending_days REAL DEFAULT 0,
                    carry_forward_days REAL DEFAULT 0,
                    UNIQUE(employee_id, leave_type_id, year),
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_no TEXT UNIQUE,
                    employee_id INTEGER,
                    leave_type_id INTEGER,
                    start_date TEXT,
                    end_date TEXT,
                    requested_days INTEGER,
                    working_days INTEGER,
                    reason TEXT,
                    status TEXT DEFAULT 'Pending Supervisor',
                    created_at TEXT,
                    updated_at TEXT,
                    supervisor_approved_at TEXT,
                    hr_approved_at TEXT,
                    rejection_reason TEXT,
                    cancelled_at TEXT,
                    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
                    FOREIGN KEY (leave_type_id) REFERENCES leave_types(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS leave_approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER,
                    approver_id INTEGER,
                    stage TEXT,
                    action TEXT,
                    comments TEXT,
                    created_at TEXT,
                    FOREIGN KEY (application_id) REFERENCES leave_applications(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public_holidays (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    holiday_date TEXT UNIQUE,
                    description TEXT,
                    year INTEGER,
                    created_at TEXT
                )
            """)
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_app_employee ON leave_applications(employee_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_app_status ON leave_applications(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_leave_ent_employee ON leave_entitlements(employee_id)")
        
        # Add leave columns to employees table if not exist
        try:
            if is_cloud:
                cursor.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS leave_balance INTEGER DEFAULT 30")
                cursor.execute("ALTER TABLE employees ADD COLUMN IF NOT EXISTS leave_taken INTEGER DEFAULT 0")
            else:
                cursor.execute("PRAGMA table_info(employees)")
                existing_cols = [col[1] for col in cursor.fetchall()]
                if 'leave_balance' not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN leave_balance INTEGER DEFAULT 30")
                if 'leave_taken' not in existing_cols:
                    cursor.execute("ALTER TABLE employees ADD COLUMN leave_taken INTEGER DEFAULT 0")
        except Exception as e:
            print(f"Employee column migration warning: {e}")
        
        # Seed default leave types
        cursor.execute("SELECT COUNT(*) FROM leave_types")
        if cursor.fetchone()[0] == 0:
            default_types = [
                ("Annual Leave", "ANN", 30, "Regular annual leave"),
                ("Sick Leave", "SICK", 30, "Medical leave"),
                ("Maternity Leave", "MAT", 90, "Maternity leave"),
                ("Paternity Leave", "PAT", 14, "Paternity leave"),
                ("Compassionate Leave", "COMP", 10, "Family emergency leave"),
                ("Study Leave", "STDY", 15, "Educational leave"),
            ]
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for name, code, days, desc in default_types:
                cursor.execute("""
                    INSERT INTO leave_types (name, code, default_days, description, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (name, code, days, desc, now))
        
        conn.commit()
        conn.close()
        print("✅ Leave management tables migrated successfully")
        
    except Exception as e:
        print(f"❌ Leave migration error: {e}")
        import traceback
        traceback.print_exc()

def seed_leave_holidays():
    """Seed public holidays for current year"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        current_year = datetime.now().year
        holidays = [
            (date(current_year, 1, 1), "New Year's Day"),
            (date(current_year, 5, 1), "Labor Day"),
            (date(current_year, 6, 1), "Madaraka Day"),
            (date(current_year, 10, 20), "Mashujaa Day"),
            (date(current_year, 12, 12), "Jamhuri Day"),
            (date(current_year, 12, 25), "Christmas Day"),
            (date(current_year, 12, 26), "Boxing Day"),
        ]
        
        for holiday_date, desc in holidays:
            if is_cloud:
                cursor.execute("""
                    INSERT INTO public_holidays (holiday_date, description, year)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (holiday_date) DO NOTHING
                """, (holiday_date, desc, current_year))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO public_holidays (holiday_date, description, year)
                    VALUES (?, ?, ?)
                """, (holiday_date.strftime("%Y-%m-%d"), desc, current_year))
        
        conn.commit()
        conn.close()
        print(f"✅ Seeded {len(holidays)} public holidays for {current_year}")
        
    except Exception as e:
        print(f"❌ Holiday seeding error: {e}")

# =========================================================
# LEAVE MANAGEMENT FUNCTIONS
# =========================================================
def calculate_working_days(start_date, end_date):
    """Calculate working days excluding weekends and holidays"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        # Get holidays
        cursor.execute("SELECT holiday_date FROM public_holidays")
        holidays = [row[0] for row in cursor.fetchall()]
        if is_cloud:
            holidays = [h.date() if hasattr(h, 'date') else h for h in holidays]
        else:
            holidays = [datetime.strptime(h, "%Y-%m-%d").date() for h in holidays]
        
        conn.close()
        
        current = start_date
        working_days = 0
        while current <= end_date:
            if current.weekday() < 5 and current not in holidays:
                working_days += 1
            current += timedelta(days=1)
        
        return working_days
    except:
        # Fallback - just weekends
        current = start_date
        working_days = 0
        while current <= end_date:
            if current.weekday() < 5:
                working_days += 1
            current += timedelta(days=1)
        return working_days

def check_leave_balance(employee_id, leave_type_id):
    """Check remaining leave balance"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        current_year = datetime.now().year
        
        if is_cloud:
            cursor.execute("""
                SELECT allocated_days, used_days, pending_days, carry_forward_days
                FROM leave_entitlements
                WHERE employee_id = %s AND leave_type_id = %s AND year = %s
            """, (employee_id, leave_type_id, current_year))
        else:
            cursor.execute("""
                SELECT allocated_days, used_days, pending_days, carry_forward_days
                FROM leave_entitlements
                WHERE employee_id = ? AND leave_type_id = ? AND year = ?
            """, (employee_id, leave_type_id, current_year))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            allocated = float(result[0])
            used = float(result[1])
            pending = float(result[2])
            carry = float(result[3])
            return allocated + carry - used - pending
        else:
            return 0
    except:
        return 0

def create_leave_application(employee_id, leave_type_id, start_date, end_date, reason):
    """Create a new leave application"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        # Calculate working days
        working_days = calculate_working_days(start_date, end_date)
        
        if working_days == 0:
            conn.close()
            return {"success": False, "error": "No working days in selected range"}
        
        # Check balance
        balance = check_leave_balance(employee_id, leave_type_id)
        if balance < working_days:
            conn.close()
            return {"success": False, "error": f"Insufficient balance. Available: {balance}, Requested: {working_days}"}
        
        # Generate application number
        now = datetime.now()
        cursor.execute("SELECT COUNT(*) FROM leave_applications")
        count = cursor.fetchone()[0] + 1
        app_no = f"LA-{now.year}-{count:06d}"
        
        # Insert application
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_cloud:
            cursor.execute("""
                INSERT INTO leave_applications (
                    application_no, employee_id, leave_type_id, start_date, end_date,
                    requested_days, working_days, reason, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (app_no, employee_id, leave_type_id, start_date, end_date,
                  working_days, working_days, reason, 'Pending Supervisor', now_str))
            app_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO leave_applications (
                    application_no, employee_id, leave_type_id, start_date, end_date,
                    requested_days, working_days, reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (app_no, employee_id, leave_type_id, start_date.strftime("%Y-%m-%d"),
                  end_date.strftime("%Y-%m-%d"), working_days, working_days, reason,
                  'Pending Supervisor', now_str))
            app_id = cursor.lastrowid
        
        # Update pending days
        if is_cloud:
            cursor.execute("""
                UPDATE leave_entitlements 
                SET pending_days = pending_days + %s 
                WHERE employee_id = %s AND leave_type_id = %s AND year = %s
            """, (working_days, employee_id, leave_type_id, now.year))
        else:
            cursor.execute("""
                UPDATE leave_entitlements 
                SET pending_days = pending_days + ? 
                WHERE employee_id = ? AND leave_type_id = ? AND year = ?
            """, (working_days, employee_id, leave_type_id, now.year))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "application_id": app_id, "application_no": app_no, "days": working_days}
        
    except Exception as e:
        print(f"Error creating leave application: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

def process_leave_approval(application_id, action, approver_id, comments=""):
    """Process leave approval or rejection"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        # Get application
        if is_cloud:
            cursor.execute("SELECT * FROM leave_applications WHERE id = %s", (application_id,))
        else:
            cursor.execute("SELECT * FROM leave_applications WHERE id = ?", (application_id,))
        app = cursor.fetchone()
        
        if not app:
            conn.close()
            return {"success": False, "error": "Application not found"}
        
        current_status = app[8]  # status column
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if action == "approve":
            if current_status == "Pending Supervisor":
                new_status = "Pending HR"
            elif current_status == "Pending HR":
                new_status = "Approved"
                
                # Deduct from balance
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_entitlements 
                        SET used_days = used_days + %s, pending_days = pending_days - %s
                        WHERE employee_id = %s AND leave_type_id = %s AND year = %s
                    """, (app[6], app[6], app[2], app[3], datetime.now().year))
                else:
                    cursor.execute("""
                        UPDATE leave_entitlements 
                        SET used_days = used_days + ?, pending_days = pending_days - ?
                        WHERE employee_id = ? AND leave_type_id = ? AND year = ?
                    """, (app[6], app[6], app[2], app[3], datetime.now().year))
            else:
                conn.close()
                return {"success": False, "error": f"Cannot approve from status: {current_status}"}
        
        elif action == "reject":
            new_status = "Rejected"
            
            # Release pending days
            if is_cloud:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - %s
                    WHERE employee_id = %s AND leave_type_id = %s AND year = %s
                """, (app[6], app[2], app[3], datetime.now().year))
            else:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - ?
                    WHERE employee_id = ? AND leave_type_id = ? AND year = ?
                """, (app[6], app[2], app[3], datetime.now().year))
        
        elif action == "cancel":
            new_status = "Cancelled"
            
            # Release pending days
            if is_cloud:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - %s
                    WHERE employee_id = %s AND leave_type_id = %s AND year = %s
                """, (app[6], app[2], app[3], datetime.now().year))
            else:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - ?
                    WHERE employee_id = ? AND leave_type_id = ? AND year = ?
                """, (app[6], app[2], app[3], datetime.now().year))
        
        else:
            conn.close()
            return {"success": False, "error": f"Invalid action: {action}"}
        
        # Update application status
        if is_cloud:
            cursor.execute("UPDATE leave_applications SET status = %s, updated_at = %s WHERE id = %s",
                          (new_status, now, application_id))
        else:
            cursor.execute("UPDATE leave_applications SET status = ?, updated_at = ? WHERE id = ?",
                          (new_status, now, application_id))
        
        # Add approval record
        stage = "Supervisor" if current_status == "Pending Supervisor" else "HR"
        if is_cloud:
            cursor.execute("""
                INSERT INTO leave_approvals (application_id, approver_id, stage, action, comments, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (application_id, approver_id, stage, action.capitalize(), comments, now))
        else:
            cursor.execute("""
                INSERT INTO leave_approvals (application_id, approver_id, stage, action, comments, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (application_id, approver_id, stage, action.capitalize(), comments, now))
        
        conn.commit()
        conn.close()
        
        return {"success": True, "status": new_status}
        
    except Exception as e:
        print(f"Error processing approval: {e}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

# =========================================================
# LEAVE MANAGEMENT UI FUNCTIONS
# =========================================================
def leave_dashboard():
    """Leave Management Dashboard"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">🏖️ Leave Management</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Manage employee leave requests and balances</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "📝 Apply for Leave",
        "📋 My Applications",
        "✅ Approvals (Manager)"
    ])
    
    with tab1:
        st.subheader("📊 Leave Overview")
        
        # Get statistics
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            
            # Total employees with leave
            cursor = conn.cursor()
            if is_cloud:
                cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = TRUE")
                total_employees = cursor.fetchone()[0]
                
                cursor.execute("""
                    SELECT COUNT(*) FROM leave_applications 
                    WHERE status = 'Approved' 
                    AND start_date <= CURRENT_DATE 
                    AND end_date >= CURRENT_DATE
                """)
                on_leave = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending Supervisor'")
                pending_sup = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending HR'")
                pending_hr = cursor.fetchone()[0]
            else:
                cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1")
                total_employees = cursor.fetchone()[0]
                
                today = date.today().strftime("%Y-%m-%d")
                cursor.execute("""
                    SELECT COUNT(*) FROM leave_applications 
                    WHERE status = 'Approved' 
                    AND start_date <= ? 
                    AND end_date >= ?
                """, (today, today))
                on_leave = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending Supervisor'")
                pending_sup = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending HR'")
                pending_hr = cursor.fetchone()[0]
            
            conn.close()
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Employees", total_employees)
            with col2:
                st.metric("On Leave Today", on_leave)
            with col3:
                st.metric("Pending Supervisor", pending_sup)
            with col4:
                st.metric("Pending HR", pending_hr)
            
            # Show upcoming leaves
            st.markdown("---")
            st.subheader("📅 Upcoming/Current Leaves")
            
            try:
                conn = get_conn()
                if is_cloud:
                    upcoming = pd.read_sql("""
                        SELECT 
                            e.name as employee_name,
                            e.personal_no,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.status
                        FROM leave_applications la
                        JOIN employees e ON la.employee_id = e.id
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.status = 'Approved'
                        ORDER BY la.start_date DESC
                        LIMIT 20
                    """, conn)
                else:
                    upcoming = pd.read_sql("""
                        SELECT 
                            e.name as employee_name,
                            e.personal_no,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.status
                        FROM leave_applications la
                        JOIN employees e ON la.employee_id = e.id
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.status = 'Approved'
                        ORDER BY la.start_date DESC
                        LIMIT 20
                    """, conn)
                conn.close()
                
                if not upcoming.empty:
                    st.dataframe(upcoming, use_container_width=True)
                else:
                    st.info("No approved leaves found")
                    
            except Exception as e:
                st.error(f"Error loading leaves: {e}")
                
        except Exception as e:
            st.error(f"Error loading dashboard: {e}")
    
    with tab2:
        st.subheader("📝 Apply for Leave")
        
        # Check if user is logged in and has employee record
        if "user" not in st.session_state or st.session_state.user is None:
            st.error("Please login first")
            return
        
        # Get employee information
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            
            # Get current user's employee record
            username = st.session_state.user.get("username", "")
            
            if is_cloud:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM employees WHERE personal_no = %s", (username,))
                emp_record = cursor.fetchone()
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM employees WHERE personal_no = ?", (username,))
                emp_record = cursor.fetchone()
            
            if emp_record:
                employee_id = emp_record[0]
                
                # Get leave types
                leave_types = pd.read_sql("SELECT * FROM leave_types WHERE is_active = 1", conn)
                
                if leave_types.empty:
                    st.warning("No leave types configured")
                    conn.close()
                    return
                
                # Check if user has entitlements for current year
                current_year = datetime.now().year
                entitlements = pd.read_sql(f"SELECT * FROM leave_entitlements WHERE employee_id = {employee_id} AND year = {current_year}", conn)
                
                if entitlements.empty:
                    # Create default entitlements
                    for _, lt in leave_types.iterrows():
                        if is_cloud:
                            cursor.execute("""
                                INSERT INTO leave_entitlements (employee_id, leave_type_id, year, allocated_days)
                                VALUES (%s, %s, %s, %s)
                            """, (employee_id, lt['id'], current_year, lt['default_days']))
                        else:
                            cursor.execute("""
                                INSERT INTO leave_entitlements (employee_id, leave_type_id, year, allocated_days)
                                VALUES (?, ?, ?, ?)
                            """, (employee_id, lt['id'], current_year, lt['default_days']))
                    conn.commit()
                    
                    # Reload entitlements
                    entitlements = pd.read_sql(f"SELECT * FROM leave_entitlements WHERE employee_id = {employee_id} AND year = {current_year}", conn)
                
                # Create leave application form
                with st.form("leave_application_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        # Leave Type
                        leave_type_options = {}
                        for _, ent in entitlements.iterrows():
                            lt = leave_types[leave_types['id'] == ent['leave_type_id']].iloc[0]
                            remaining = float(ent['allocated_days']) + float(ent['carry_forward_days']) - float(ent['used_days']) - float(ent['pending_days'])
                            leave_type_options[ent['leave_type_id']] = f"{lt['name']} (Available: {remaining} days)"
                        
                        selected_leave_type = st.selectbox(
                            "Leave Type *",
                            list(leave_type_options.keys()),
                            format_func=lambda x: leave_type_options[x],
                            key="leave_type_select"
                        )
                        
                        # Start Date
                        start_date = st.date_input("Start Date *", value=date.today(), key="leave_start")
                    
                    with col2:
                        # End Date
                        end_date = st.date_input("End Date *", value=date.today() + timedelta(days=3), key="leave_end")
                        
                        # Show calculated days
                        working_days = calculate_working_days(start_date, end_date)
                        st.info(f"📅 Working Days: {working_days}")
                        
                        # Show balance
                        balance = check_leave_balance(employee_id, selected_leave_type)
                        st.info(f"💰 Available Balance: {balance} days")
                        
                        if working_days > balance:
                            st.error(f"❌ Requested {working_days} days but only {balance} available!")
                    
                    # Reason
                    reason = st.text_area("Reason / Justification *", height=100, key="leave_reason")
                    
                    # Submit button
                    submitted = st.form_submit_button("📤 Submit Leave Application", use_container_width=True, type="primary")
                    
                    if submitted:
                        if not reason:
                            st.error("Please provide a reason")
                        elif working_days == 0:
                            st.error("No working days in selected range")
                        elif working_days > balance:
                            st.error(f"Insufficient balance: Requested {working_days}, Available {balance}")
                        else:
                            result = create_leave_application(
                                employee_id=employee_id,
                                leave_type_id=selected_leave_type,
                                start_date=start_date,
                                end_date=end_date,
                                reason=reason
                            )
                            
                            if result["success"]:
                                st.success(f"✅ Leave application {result['application_no']} submitted for {result['days']} working days!")
                                st.balloons()
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                
                conn.close()
            else:
                st.error("No employee record found for your account. Please contact HR.")
                conn.close()
                
        except Exception as e:
            st.error(f"Error: {e}")
            traceback.print_exc()
    
    with tab3:
        st.subheader("📋 My Leave Applications")
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            
            username = st.session_state.user.get("username", "")
            
            if is_cloud:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM employees WHERE personal_no = %s", (username,))
                emp_record = cursor.fetchone()
            else:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM employees WHERE personal_no = ?", (username,))
                emp_record = cursor.fetchone()
            
            if emp_record:
                employee_id = emp_record[0]
                
                # Get applications
                if is_cloud:
                    applications = pd.read_sql(f"""
                        SELECT 
                            la.application_no,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status,
                            lt.name as leave_type,
                            la.created_at
                        FROM leave_applications la
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.employee_id = {employee_id}
                        ORDER BY la.created_at DESC
                    """, conn)
                else:
                    applications = pd.read_sql(f"""
                        SELECT 
                            la.application_no,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status,
                            lt.name as leave_type,
                            la.created_at
                        FROM leave_applications la
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.employee_id = {employee_id}
                        ORDER BY la.created_at DESC
                    """, conn)
                
                if applications.empty:
                    st.info("No leave applications found")
                else:
                    # Display applications
                    for idx, app in applications.iterrows():
                        status = app['status']
                        
                        if status == 'Approved':
                            badge = "🟢 Approved"
                        elif status == 'Rejected':
                            badge = "🔴 Rejected"
                        elif status == 'Cancelled':
                            badge = "⚪ Cancelled"
                        else:
                            badge = f"🟡 {status}"
                        
                        with st.expander(f"📄 {app['application_no']} - {app['leave_type']} ({app['start_date']} to {app['end_date']}) - {badge}"):
                            st.write(f"**Days Requested:** {app['requested_days']}")
                            st.write(f"**Reason:** {app['reason']}")
                            st.write(f"**Submitted:** {app['created_at']}")
                            
                            # Cancel button for pending applications
                            if status in ['Pending Supervisor', 'Pending HR']:
                                if st.button(f"❌ Cancel Application", key=f"cancel_{app['application_no']}"):
                                    # Get application ID
                                    if is_cloud:
                                        cursor.execute("SELECT id FROM leave_applications WHERE application_no = %s", (app['application_no'],))
                                    else:
                                        cursor.execute("SELECT id FROM leave_applications WHERE application_no = ?", (app['application_no'],))
                                    app_id = cursor.fetchone()[0]
                                    
                                    result = process_leave_approval(app_id, "cancel", st.session_state.user.get("id", 0))
                                    if result["success"]:
                                        st.success(f"✅ Application {app['application_no']} cancelled!")
                                        st.rerun()
                                    else:
                                        st.error(f"❌ {result['error']}")
                conn.close()
            else:
                st.info("No employee record found")
                conn.close()
                
        except Exception as e:
            st.error(f"Error loading applications: {e}")
            traceback.print_exc()
    
    with tab4:
        st.subheader("✅ Leave Approvals (Manager)")
        
        # Check role
        role = st.session_state.user.get("role", "User")
        if role not in ["Admin", "Super Admin", "HR", "Manager"]:
            st.error("⛔ Access Denied. You need Manager, HR, Admin or Super Admin role.")
            return
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Get pending applications
            if role in ["Admin", "Super Admin", "HR"]:
                pending = pd.read_sql("""
                    SELECT 
                        la.id,
                        la.application_no,
                        e.name as employee_name,
                        e.designation,
                        lt.name as leave_type,
                        la.start_date,
                        la.end_date,
                        la.requested_days,
                        la.reason,
                        la.status
                    FROM leave_applications la
                    JOIN employees e ON la.employee_id = e.id
                    JOIN leave_types lt ON la.leave_type_id = lt.id
                    WHERE la.status = 'Pending HR'
                    ORDER BY la.created_at DESC
                """, conn)
            else:
                pending = pd.read_sql("""
                    SELECT 
                        la.id,
                        la.application_no,
                        e.name as employee_name,
                        e.designation,
                        lt.name as leave_type,
                        la.start_date,
                        la.end_date,
                        la.requested_days,
                        la.reason,
                        la.status
                    FROM leave_applications la
                    JOIN employees e ON la.employee_id = e.id
                    JOIN leave_types lt ON la.leave_type_id = lt.id
                    WHERE la.status = 'Pending Supervisor'
                    ORDER BY la.created_at DESC
                """, conn)
            
            if pending.empty:
                st.info("No pending leave approvals")
                conn.close()
                return
            
            st.success(f"📋 Found {len(pending)} pending leave request(s)")
            
            for idx, app in pending.iterrows():
                with st.expander(f"📄 {app['application_no']} - {app['employee_name']} - {app['leave_type']} ({app['requested_days']} days)"):
                    st.write(f"**Employee:** {app['employee_name']} ({app['designation']})")
                    st.write(f"**Leave Type:** {app['leave_type']}")
                    st.write(f"**Dates:** {app['start_date']} to {app['end_date']}")
                    st.write(f"**Days:** {app['requested_days']}")
                    st.write(f"**Reason:** {app['reason']}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button(f"✅ Approve", key=f"approve_{app['id']}", use_container_width=True):
                            result = process_leave_approval(app['id'], "approve", st.session_state.user.get("id", 0), "Approved by manager")
                            if result["success"]:
                                st.success(f"✅ {app['application_no']} approved! Status: {result['status']}")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                    with col2:
                        if st.button(f"❌ Reject", key=f"reject_{app['id']}", use_container_width=True):
                            # Get rejection reason
                            reason_input = st.text_input("Rejection reason", key=f"reason_{app['id']}")
                            result = process_leave_approval(app['id'], "reject", st.session_state.user.get("id", 0), reason_input)
                            if result["success"]:
                                st.success(f"✅ {app['application_no']} rejected!")
                                st.rerun()
                            else:
                                st.error(f"❌ {result['error']}")
                    with col3:
                        if st.button(f"📄 View Details", key=f"view_{app['id']}", use_container_width=True):
                            st.info("View details in expander above")
            
            conn.close()
            
        except Exception as e:
            st.error(f"Error loading approvals: {e}")
            traceback.print_exc()