# leave_management_module.py
"""
County CLMS - Leave Management Module
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
    database_url = st.secrets.get("DATABASE_URL")
    
    if database_url:
        try:
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
        return sqlite3.connect("ecde.db", check_same_thread=False)

# =========================================================
# LEAVE MANAGEMENT FUNCTIONS
# =========================================================
def calculate_working_days(start_date, end_date):
    """Calculate working days excluding weekends and holidays"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
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
        current = start_date
        working_days = 0
        while current <= end_date:
            if current.weekday() < 5:
                working_days += 1
            current += timedelta(days=1)
        return working_days

def check_leave_balance(staff_no, leave_type_id):
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
                WHERE staff_no = %s AND leave_type_id = %s AND year = %s
            """, (staff_no, leave_type_id, current_year))
        else:
            cursor.execute("""
                SELECT allocated_days, used_days, pending_days, carry_forward_days
                FROM leave_entitlements
                WHERE staff_no = ? AND leave_type_id = ? AND year = ?
            """, (staff_no, leave_type_id, current_year))
        
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

def create_leave_application(staff_no, leave_type_id, start_date, end_date, reason):
    """Create a new leave application"""
    try:
        conn = get_conn()
        cursor = conn.cursor()
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        
        working_days = calculate_working_days(start_date, end_date)
        
        if working_days == 0:
            conn.close()
            return {"success": False, "error": "No working days in selected range"}
        
        balance = check_leave_balance(staff_no, leave_type_id)
        if balance < working_days:
            conn.close()
            return {"success": False, "error": f"Insufficient balance. Available: {balance}, Requested: {working_days}"}
        
        now = datetime.now()
        cursor.execute("SELECT COUNT(*) FROM leave_applications")
        count = cursor.fetchone()[0] + 1
        app_no = f"LA-{now.year}-{count:06d}"
        
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        if is_cloud:
            cursor.execute("""
                INSERT INTO leave_applications (
                    application_no, staff_no, leave_type_id, start_date, end_date,
                    requested_days, working_days, reason, status, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (app_no, staff_no, leave_type_id, start_date, end_date,
                  working_days, working_days, reason, 'Pending Supervisor', now_str))
            app_id = cursor.fetchone()[0]
        else:
            cursor.execute("""
                INSERT INTO leave_applications (
                    application_no, staff_no, leave_type_id, start_date, end_date,
                    requested_days, working_days, reason, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (app_no, staff_no, leave_type_id, start_date.strftime("%Y-%m-%d"),
                  end_date.strftime("%Y-%m-%d"), working_days, working_days, reason,
                  'Pending Supervisor', now_str))
            app_id = cursor.lastrowid
        
        if is_cloud:
            cursor.execute("""
                UPDATE leave_entitlements 
                SET pending_days = pending_days + %s 
                WHERE staff_no = %s AND leave_type_id = %s AND year = %s
            """, (working_days, staff_no, leave_type_id, now.year))
        else:
            cursor.execute("""
                UPDATE leave_entitlements 
                SET pending_days = pending_days + ? 
                WHERE staff_no = ? AND leave_type_id = ? AND year = ?
            """, (working_days, staff_no, leave_type_id, now.year))
        
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
        
        if is_cloud:
            cursor.execute("SELECT * FROM leave_applications WHERE id = %s", (application_id,))
        else:
            cursor.execute("SELECT * FROM leave_applications WHERE id = ?", (application_id,))
        app = cursor.fetchone()
        
        if not app:
            conn.close()
            return {"success": False, "error": "Application not found"}
        
        current_status = app[7]
        staff_no = app[2]
        leave_type_id = app[3]
        requested_days = app[6]
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if action == "approve":
            if current_status == "Pending Supervisor":
                new_status = "Pending HR"
            elif current_status == "Pending HR":
                new_status = "Approved"
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_entitlements 
                        SET used_days = used_days + %s, pending_days = pending_days - %s
                        WHERE staff_no = %s AND leave_type_id = %s AND year = %s
                    """, (requested_days, requested_days, staff_no, leave_type_id, datetime.now().year))
                else:
                    cursor.execute("""
                        UPDATE leave_entitlements 
                        SET used_days = used_days + ?, pending_days = pending_days - ?
                        WHERE staff_no = ? AND leave_type_id = ? AND year = ?
                    """, (requested_days, requested_days, staff_no, leave_type_id, datetime.now().year))
            else:
                conn.close()
                return {"success": False, "error": f"Cannot approve from status: {current_status}"}
        
        elif action == "reject":
            new_status = "Rejected"
            if is_cloud:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - %s
                    WHERE staff_no = %s AND leave_type_id = %s AND year = %s
                """, (requested_days, staff_no, leave_type_id, datetime.now().year))
            else:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - ?
                    WHERE staff_no = ? AND leave_type_id = ? AND year = ?
                """, (requested_days, staff_no, leave_type_id, datetime.now().year))
        
        elif action == "cancel":
            new_status = "Cancelled"
            if is_cloud:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - %s
                    WHERE staff_no = %s AND leave_type_id = %s AND year = %s
                """, (requested_days, staff_no, leave_type_id, datetime.now().year))
            else:
                cursor.execute("""
                    UPDATE leave_entitlements 
                    SET pending_days = pending_days - ?
                    WHERE staff_no = ? AND leave_type_id = ? AND year = ?
                """, (requested_days, staff_no, leave_type_id, datetime.now().year))
        
        else:
            conn.close()
            return {"success": False, "error": f"Invalid action: {action}"}
        
        if is_cloud:
            cursor.execute("UPDATE leave_applications SET status = %s, updated_at = %s WHERE id = %s",
                          (new_status, now, application_id))
        else:
            cursor.execute("UPDATE leave_applications SET status = ?, updated_at = ? WHERE id = ?",
                          (new_status, now, application_id))
        
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
# LEAVE MANAGEMENT UI
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
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Check if employees table has staff_no column
            if is_cloud:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'employees' AND column_name = 'staff_no'
                """)
                has_staff_no = cursor.fetchone() is not None
            else:
                cursor.execute("PRAGMA table_info(employees)")
                existing_cols = [col[1] for col in cursor.fetchall()]
                has_staff_no = 'staff_no' in existing_cols
            
            # Get total employees count
            if is_cloud:
                cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = TRUE")
            else:
                cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1")
            total_employees = cursor.fetchone()[0]
            
            # Get on leave today
            today = date.today()
            try:
                if is_cloud:
                    cursor.execute("""
                        SELECT COUNT(*) FROM leave_applications 
                        WHERE status = 'Approved' 
                        AND start_date <= CURRENT_DATE 
                        AND end_date >= CURRENT_DATE
                    """)
                else:
                    cursor.execute("""
                        SELECT COUNT(*) FROM leave_applications 
                        WHERE status = 'Approved' 
                        AND start_date <= ? 
                        AND end_date >= ?
                    """, (today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
                on_leave = cursor.fetchone()[0]
            except:
                on_leave = 0
            
            # Get pending counts
            try:
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending Supervisor'")
                pending_sup = cursor.fetchone()[0]
            except:
                pending_sup = 0
            
            try:
                cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE status = 'Pending HR'")
                pending_hr = cursor.fetchone()[0]
            except:
                pending_hr = 0
            
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
                is_cloud = st.secrets.get("DATABASE_URL") is not None
                
                # Use staff_no for joining (matches employees table)
                upcoming = pd.read_sql("""
                    SELECT 
                        e.name as employee_name,
                        e.staff_no as employee_no,
                        lt.name as leave_type,
                        la.start_date,
                        la.end_date,
                        la.requested_days,
                        la.status
                    FROM leave_applications la
                    JOIN employees e ON la.staff_no = e.staff_no
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
                import traceback
                st.code(traceback.format_exc())
                
        except Exception as e:
            st.error(f"Error loading dashboard: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    with tab2:
        st.subheader("📝 Apply for Leave")
        
        if "user" not in st.session_state or st.session_state.user is None:
            st.error("Please login first")
            return
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Get current user's staff_no
            username = st.session_state.user.get("username", "")
            
            # Try to find employee by staff_no or personal_no
            if is_cloud:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = %s OR personal_no = %s", (username, username))
            else:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = ? OR personal_no = ?", (username, username))
            emp_record = cursor.fetchone()
            
            if emp_record:
                staff_no = emp_record[0]
            else:
                # Try by personal_no
                if is_cloud:
                    cursor.execute("SELECT personal_no FROM employees WHERE personal_no = %s", (username,))
                else:
                    cursor.execute("SELECT personal_no FROM employees WHERE personal_no = ?", (username,))
                emp_record = cursor.fetchone()
                
                if emp_record:
                    staff_no = emp_record[0]
                else:
                    st.error("No employee record found for your account. Please contact HR.")
                    conn.close()
                    return
            
            # Get leave types
            if is_cloud:
                leave_types = pd.read_sql("SELECT * FROM leave_types WHERE is_active = TRUE", conn)
            else:
                leave_types = pd.read_sql("SELECT * FROM leave_types WHERE is_active = 1", conn)
            
            if leave_types.empty:
                st.warning("No leave types configured")
                conn.close()
                return
            
            # Check entitlements
            current_year = datetime.now().year
            if is_cloud:
                entitlements = pd.read_sql(f"""
                    SELECT * FROM leave_entitlements 
                    WHERE staff_no = '{staff_no}' AND year = {current_year}
                """, conn)
            else:
                entitlements = pd.read_sql(f"""
                    SELECT * FROM leave_entitlements 
                    WHERE staff_no = '{staff_no}' AND year = {current_year}
                """, conn)
            
            if entitlements.empty:
                # Create default entitlements
                for _, lt in leave_types.iterrows():
                    if is_cloud:
                        cursor.execute("""
                            INSERT INTO leave_entitlements (staff_no, leave_type_id, year, allocated_days)
                            VALUES (%s, %s, %s, %s)
                        """, (staff_no, lt['id'], current_year, lt['default_days']))
                    else:
                        cursor.execute("""
                            INSERT INTO leave_entitlements (staff_no, leave_type_id, year, allocated_days)
                            VALUES (?, ?, ?, ?)
                        """, (staff_no, lt['id'], current_year, lt['default_days']))
                conn.commit()
                
                if is_cloud:
                    entitlements = pd.read_sql(f"""
                        SELECT * FROM leave_entitlements 
                        WHERE staff_no = '{staff_no}' AND year = {current_year}
                    """, conn)
                else:
                    entitlements = pd.read_sql(f"""
                        SELECT * FROM leave_entitlements 
                        WHERE staff_no = '{staff_no}' AND year = {current_year}
                    """, conn)
            
            # Create leave application form
            with st.form("leave_application_form"):
                col1, col2 = st.columns(2)
                
                with col1:
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
                    
                    start_date = st.date_input("Start Date *", value=date.today(), key="leave_start")
                
                with col2:
                    end_date = st.date_input("End Date *", value=date.today() + timedelta(days=3), key="leave_end")
                    
                    working_days = calculate_working_days(start_date, end_date)
                    st.info(f"📅 Working Days: {working_days}")
                    
                    balance = check_leave_balance(staff_no, selected_leave_type)
                    st.info(f"💰 Available Balance: {balance} days")
                    
                    if working_days > balance:
                        st.error(f"❌ Requested {working_days} days but only {balance} available!")
                
                reason = st.text_area("Reason / Justification *", height=100, key="leave_reason")
                
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
                            staff_no=staff_no,
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
                
        except Exception as e:
            st.error(f"Error: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    with tab3:
        st.subheader("📋 My Leave Applications")
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            username = st.session_state.user.get("username", "")
            
            # Get current user's staff_no
            if is_cloud:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = %s OR personal_no = %s", (username, username))
            else:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = ? OR personal_no = ?", (username, username))
            emp_record = cursor.fetchone()
            
            if emp_record:
                staff_no = emp_record[0]
                
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
                        WHERE la.staff_no = '{staff_no}'
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
                        WHERE la.staff_no = '{staff_no}'
                        ORDER BY la.created_at DESC
                    """, conn)
                
                if applications.empty:
                    st.info("No leave applications found")
                else:
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
                            
                            if status in ['Pending Supervisor', 'Pending HR']:
                                if st.button(f"❌ Cancel Application", key=f"cancel_{app['application_no']}"):
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
            import traceback
            st.code(traceback.format_exc())
    
    with tab4:
        st.subheader("✅ Leave Approvals (Manager)")
        
        role = st.session_state.user.get("role", "User")
        if role not in ["Admin", "Super Admin", "HR", "Manager"]:
            st.error("⛔ Access Denied. You need Manager, HR, Admin or Super Admin role.")
            return
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Check if leave_applications has staff_no column
            if is_cloud:
                cursor.execute("""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'leave_applications' AND column_name = 'staff_no'
                """)
                has_staff_no = cursor.fetchone() is not None
            else:
                cursor.execute("PRAGMA table_info(leave_applications)")
                existing_cols = [col[1] for col in cursor.fetchall()]
                has_staff_no = 'staff_no' in existing_cols
            
            if has_staff_no:
                # Use staff_no for joining
                if role in ["Admin", "Super Admin", "HR"]:
                    pending = pd.read_sql("""
                        SELECT 
                            la.id,
                            la.application_no,
                            e.name as employee_name,
                            e.current_designation as designation,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status
                        FROM leave_applications la
                        JOIN employees e ON la.staff_no = e.staff_no
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
                            e.current_designation as designation,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status
                        FROM leave_applications la
                        JOIN employees e ON la.staff_no = e.staff_no
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.status = 'Pending Supervisor'
                        ORDER BY la.created_at DESC
                    """, conn)
            else:
                # Fallback: show applications without employee join
                if role in ["Admin", "Super Admin", "HR"]:
                    pending = pd.read_sql("""
                        SELECT 
                            la.id,
                            la.application_no,
                            la.staff_no as employee_name,
                            '' as designation,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status
                        FROM leave_applications la
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        WHERE la.status = 'Pending HR'
                        ORDER BY la.created_at DESC
                    """, conn)
                else:
                    pending = pd.read_sql("""
                        SELECT 
                            la.id,
                            la.application_no,
                            la.staff_no as employee_name,
                            '' as designation,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.reason,
                            la.status
                        FROM leave_applications la
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
            import traceback
            st.code(traceback.format_exc())