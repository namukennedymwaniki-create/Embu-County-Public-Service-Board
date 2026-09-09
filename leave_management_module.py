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

def create_leave_application(staff_no, leave_type_id, start_date, end_date, reason, applied_by=None):
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
        
        # Use applied_by if provided, otherwise use staff_no as the applicant
        applicant = applied_by if applied_by else staff_no
        
        # Check if leave_applications table has applied_by column
        if is_cloud:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'leave_applications' AND column_name = 'applied_by'
            """)
            has_applied_by = cursor.fetchone() is not None
        else:
            cursor.execute("PRAGMA table_info(leave_applications)")
            existing_cols = [col[1] for col in cursor.fetchall()]
            has_applied_by = 'applied_by' in existing_cols
        
        if has_applied_by:
            # Insert with applied_by column
            if is_cloud:
                cursor.execute("""
                    INSERT INTO leave_applications (
                        application_no, staff_no, leave_type_id, start_date, end_date,
                        requested_days, working_days, reason, status, created_at, applied_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (app_no, staff_no, leave_type_id, start_date, end_date,
                      working_days, working_days, reason, 'Pending Supervisor', now_str, applicant))
                app_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO leave_applications (
                        application_no, staff_no, leave_type_id, start_date, end_date,
                        requested_days, working_days, reason, status, created_at, applied_by
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (app_no, staff_no, leave_type_id, start_date.strftime("%Y-%m-%d"),
                      end_date.strftime("%Y-%m-%d"), working_days, working_days, reason,
                      'Pending Supervisor', now_str, applicant))
                app_id = cursor.lastrowid
        else:
            # Insert without applied_by column
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
        
        # Update pending days
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

def leave_dashboard():
    """Leave Management Dashboard"""
    
    # Apply professional styling
    st.markdown("""
    <style>
    /* =========================================================
       LEAVE DASHBOARD - PROFESSIONAL STYLING
       ========================================================= */
    
    /* Page Header */
    .leave-header {
        background: linear-gradient(135deg, #1a2332 0%, #0f172a 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        border: 1px solid rgba(59, 130, 246, 0.2);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    
    .leave-header h1 {
        color: white !important;
        margin: 0 !important;
        font-size: 1.8rem !important;
        font-weight: 700 !important;
    }
    
    .leave-header p {
        color: rgba(255, 255, 255, 0.8) !important;
        margin-top: 0.5rem !important;
    }
    
    /* Stats Cards */
    .stats-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
        margin-bottom: 1rem;
        position: relative;
        overflow: hidden;
    }
    
    .stats-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.12);
    }
    
    .stats-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 4px;
        background: linear-gradient(90deg, #3b82f6, transparent);
    }
    
    .stats-card .label {
        color: #6b7280;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    .stats-card .value {
        font-size: 2.5rem;
        font-weight: 700;
        color: #111827;
        line-height: 1.2;
        margin: 0.5rem 0;
    }
    
    .stats-card .trend {
        font-size: 0.8rem;
        display: flex;
        align-items: center;
        gap: 4px;
        color: #6b7280;
    }
    
    .stats-card .icon-wrapper {
        width: 48px;
        height: 48px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.5rem;
    }
    
    /* Application Cards */
    .app-card {
        background: white;
        border-radius: 12px;
        padding: 1.25rem;
        margin-bottom: 0.75rem;
        border: 1px solid #e5e7eb;
        transition: all 0.3s ease;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
    }
    
    .app-card:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        border-color: #3b82f6;
    }
    
    .app-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #111827;
    }
    
    .app-meta {
        font-size: 0.8rem;
        color: #6b7280;
        margin-top: 0.25rem;
    }
    
    .status-badge {
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
    }
    
    .status-approved {
        background: #d1fae5;
        color: #065f46;
        border: 1px solid #10b981;
    }
    
    .status-pending {
        background: #fef3c7;
        color: #92400e;
        border: 1px solid #f59e0b;
    }
    
    .status-rejected {
        background: #fee2e2;
        color: #991b1b;
        border: 1px solid #ef4444;
    }
    
    .status-cancelled {
        background: #f3f4f6;
        color: #374151;
        border: 1px solid #9ca3af;
    }
    
    /* Progress Bar */
    .progress-container {
        background: #f3f4f6;
        border-radius: 6px;
        height: 8px;
        overflow: hidden;
        margin-top: 8px;
    }
    
    .progress-bar {
        height: 100%;
        border-radius: 6px;
        background: linear-gradient(90deg, #3b82f6, #2563eb);
        transition: width 0.5s ease;
    }
    
    /* Quick Actions */
    .quick-action-btn {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 16px;
        border-radius: 8px;
        background: white;
        border: 1px solid #e5e7eb;
        color: #374151;
        text-decoration: none;
        transition: all 0.3s ease;
        font-weight: 500;
        cursor: pointer;
    }
    
    .quick-action-btn:hover {
        background: #f9fafb;
        border-color: #3b82f6;
        color: #3b82f6;
    }
    </style>
    
    <!-- Page Header -->
    <div class="leave-header">
        <h1>🏖️ Leave Management Dashboard</h1>
        <p>Manage employee leave requests, balances, and approvals</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Overview",
        "📝 Apply for Leave",
        "📋 My Applications",
        "✅ Approvals (Manager)"
    ])
    
    # =========================================================
    # TAB 1: OVERVIEW
    # =========================================================
    with tab1:
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # =========================================================
            # GET STATISTICS - DYNAMIC VALUES
            # =========================================================
            
            # Total employees
            try:
                if is_cloud:
                    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = TRUE")
                else:
                    cursor.execute("SELECT COUNT(*) FROM employees WHERE is_active = 1")
                total_employees = cursor.fetchone()[0]
            except:
                cursor.execute("SELECT COUNT(*) FROM employees")
                total_employees = cursor.fetchone()[0]
            
            # On leave today
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
            
            # Pending counts
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
            
            # Total pending
            total_pending = pending_sup + pending_hr
            
            # Leave utilization rate
            utilization_rate = 0
            if total_employees > 0:
                utilization_rate = min(100, round((on_leave / total_employees) * 100))
            
            conn.close()
            
            # =========================================================
            # DISPLAY STATS CARDS - USING STREAMLIT CONTAINERS
            # =========================================================
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                with st.container():
                    st.markdown(f"""
                    <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h4 style="color: #6b7280; margin: 0;">Total Employees</h4>
                        <h2 style="color: #111827; margin: 10px 0;">{total_employees}</h2>
                        <p style="color: #10b981; margin: 0;">📈 Active</p>
                    </div>
                    """, unsafe_allow_html=True)

            with col2:
                with st.container():
                    st.markdown(f"""
                    <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h4 style="color: #6b7280; margin: 0;">On Leave Today</h4>
                        <h2 style="color: #111827; margin: 10px 0;">{on_leave}</h2>
                        <p style="color: #10b981; margin: 0;">✅ Currently absent</p>
                    </div>
                    """, unsafe_allow_html=True)

            with col3:
                with st.container():
                    st.markdown(f"""
                    <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h4 style="color: #6b7280; margin: 0;">Pending Approvals</h4>
                        <h2 style="color: #111827; margin: 10px 0;">{total_pending}</h2>
                        <p style="color: #f59e0b; margin: 0;">⏳ Needs review</p>
                    </div>
                    """, unsafe_allow_html=True)

            with col4:
                with st.container():
                    st.markdown(f"""
                    <div style="background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                        <h4 style="color: #6b7280; margin: 0;">Leave Utilization</h4>
                        <h2 style="color: #111827; margin: 10px 0;">{utilization_rate}%</h2>
                        <div style="background: #f3f4f6; border-radius: 6px; height: 8px; overflow: hidden; margin-top: 8px;">
                            <div style="height: 100%; border-radius: 6px; background: linear-gradient(90deg, #3b82f6, #2563eb); width: {utilization_rate}%;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            
            # =========================================================
            # QUICK ACTIONS
            # =========================================================
            st.markdown("### ⚡ Quick Actions")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if st.button("📝 Apply for Leave", use_container_width=True):
                    st.session_state.leave_active_tab = "📝 Apply for Leave"
                    st.rerun()
            with col2:
                if st.button("📋 My Applications", use_container_width=True):
                    st.session_state.leave_active_tab = "📋 My Applications"
                    st.rerun()
            with col3:
                if st.button("✅ Approvals", use_container_width=True):
                    st.session_state.leave_active_tab = "✅ Approvals (Manager)"
                    st.rerun()
            with col4:
                if st.button("🔍 View Roster", use_container_width=True):
                    st.info("📅 Roster feature coming soon!")
            
            st.markdown("---")
            
            # =========================================================
            # RECENT APPLICATIONS
            # =========================================================
            st.markdown("### 📋 Recent Applications")
            
            try:
                conn = get_conn()
                
                # Get recent applications
                if is_cloud:
                    recent_apps = pd.read_sql("""
                        SELECT 
                            la.application_no,
                            e.name as employee_name,
                            e.staff_no as employee_no,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.status,
                            la.created_at
                        FROM leave_applications la
                        JOIN employees e ON la.staff_no = e.staff_no
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        ORDER BY la.created_at DESC
                        LIMIT 10
                    """, conn)
                else:
                    recent_apps = pd.read_sql("""
                        SELECT 
                            la.application_no,
                            e.name as employee_name,
                            e.staff_no as employee_no,
                            lt.name as leave_type,
                            la.start_date,
                            la.end_date,
                            la.requested_days,
                            la.status,
                            la.created_at
                        FROM leave_applications la
                        JOIN employees e ON la.staff_no = e.staff_no
                        JOIN leave_types lt ON la.leave_type_id = lt.id
                        ORDER BY la.created_at DESC
                        LIMIT 10
                    """, conn)
                
                conn.close()
                
                if not recent_apps.empty:
                    for idx, app in recent_apps.iterrows():
                        status_class = ""
                        status_emoji = ""
                        
                        if app['status'] == 'Approved':
                            status_class = "status-approved"
                            status_emoji = "✅"
                        elif app['status'] in ['Pending Supervisor', 'Pending HR']:
                            status_class = "status-pending"
                            status_emoji = "⏳"
                        elif app['status'] == 'Rejected':
                            status_class = "status-rejected"
                            status_emoji = "❌"
                        else:
                            status_class = "status-cancelled"
                            status_emoji = "❌"
                        
                        # CRITICAL: Use st.markdown() with unsafe_allow_html=True, NOT st.code()
                        st.markdown(f"""
                        <div class="app-card">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <div class="app-title">{app['employee_name']} - {app['leave_type']}</div>
                                    <div class="app-meta">
                                        📅 {app['start_date']} to {app['end_date']} | {app['requested_days']} days
                                    </div>
                                </div>
                                <div>
                                    <span class="status-badge {status_class}">
                                        {status_emoji} {app['status']}
                                    </span>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("📭 No leave applications found")
                    
            except Exception as e:
                st.error(f"Error loading recent applications: {e}")
                
        except Exception as e:
            st.error(f"Error loading dashboard: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # =========================================================
    # TAB 2: APPLY FOR LEAVE
    # =========================================================
    with tab2:
        st.subheader("📝 Apply for Leave")
        
        if "user" not in st.session_state or st.session_state.user is None:
            st.error("Please login first")
            return
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Get current user's role
            user_role = st.session_state.user.get("role", "User")
            username = st.session_state.user.get("username", "")
            
            # Check if user can apply for others (HR, Admin, Super Admin)
            can_apply_for_others = user_role in ["HR", "Admin", "Super Admin"]
            
            # SELECT EMPLOYEE (For HR/Admin or Self)
            selected_staff_no = None
            
            if can_apply_for_others:
                st.info("🏢 **HR Mode:** You can apply for leave on behalf of employees.")
                
                # Get all active employees
                if is_cloud:
                    employees_df = pd.read_sql("""
                        SELECT staff_no, name, current_designation, department 
                        FROM employees 
                        WHERE is_active = TRUE 
                        ORDER BY name
                    """, conn)
                else:
                    employees_df = pd.read_sql("""
                        SELECT staff_no, name, current_designation, department 
                        FROM employees 
                        WHERE is_active = 1 
                        ORDER BY name
                    """, conn)
                
                if employees_df.empty:
                    st.error("No employees found in database")
                    conn.close()
                    return
                
                # Create employee options
                employee_options = ["-- Select Employee --"] + [
                    f"{row['staff_no']} - {row['name']} ({row['current_designation'] if row['current_designation'] else 'No Designation'})"
                    for _, row in employees_df.iterrows()
                ]
                
                selected_employee = st.selectbox(
                    "👤 Select Employee *",
                    employee_options,
                    key="leave_employee_select"
                )
                
                if selected_employee == "-- Select Employee --":
                    st.warning("⚠️ Please select an employee to apply for leave")
                    conn.close()
                    return
                
                # Extract staff_no from selection
                selected_staff_no = selected_employee.split(" - ")[0]
                
                # Show selected employee info
                emp_info = employees_df[employees_df['staff_no'] == selected_staff_no].iloc[0]
                st.info(f"📌 Applying for: **{emp_info['name']}** ({emp_info['department']})")
                
            else:
                # Regular employee applying for self
                if is_cloud:
                    cursor.execute("SELECT staff_no FROM employees WHERE staff_no = %s OR personal_no = %s", (username, username))
                else:
                    cursor.execute("SELECT staff_no FROM employees WHERE staff_no = ? OR personal_no = ?", (username, username))
                emp_record = cursor.fetchone()
                
                if emp_record:
                    selected_staff_no = emp_record[0]
                else:
                    st.error("No employee record found for your account. Please contact HR.")
                    conn.close()
                    return
            
            # GET LEAVE TYPES AND BALANCES
            if is_cloud:
                leave_types = pd.read_sql("SELECT * FROM leave_types WHERE is_active = TRUE", conn)
            else:
                leave_types = pd.read_sql("SELECT * FROM leave_types WHERE is_active = 1", conn)
            
            if leave_types.empty:
                st.warning("No leave types configured")
                conn.close()
                return
            
            # Get entitlements for selected employee
            current_year = datetime.now().year
            if is_cloud:
                entitlements = pd.read_sql(f"""
                    SELECT * FROM leave_entitlements 
                    WHERE staff_no = '{selected_staff_no}' AND year = {current_year}
                """, conn)
            else:
                entitlements = pd.read_sql(f"""
                    SELECT * FROM leave_entitlements 
                    WHERE staff_no = '{selected_staff_no}' AND year = {current_year}
                """, conn)
            
            if entitlements.empty:
                # Create default entitlements
                for _, lt in leave_types.iterrows():
                    if is_cloud:
                        cursor.execute("""
                            INSERT INTO leave_entitlements (staff_no, leave_type_id, year, allocated_days)
                            VALUES (%s, %s, %s, %s)
                        """, (selected_staff_no, lt['id'], current_year, lt['default_days']))
                    else:
                        cursor.execute("""
                            INSERT INTO leave_entitlements (staff_no, leave_type_id, year, allocated_days)
                            VALUES (?, ?, ?, ?)
                        """, (selected_staff_no, lt['id'], current_year, lt['default_days']))
                conn.commit()
                
                # Reload entitlements
                if is_cloud:
                    entitlements = pd.read_sql(f"""
                        SELECT * FROM leave_entitlements 
                        WHERE staff_no = '{selected_staff_no}' AND year = {current_year}
                    """, conn)
                else:
                    entitlements = pd.read_sql(f"""
                        SELECT * FROM leave_entitlements 
                        WHERE staff_no = '{selected_staff_no}' AND year = {current_year}
                    """, conn)
            
            # Create leave application form
            st.markdown("---")
            st.subheader("📝 Leave Application Details")
            
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
                    
                    balance = check_leave_balance(selected_staff_no, selected_leave_type)
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
                            staff_no=selected_staff_no,
                            leave_type_id=selected_leave_type,
                            start_date=start_date,
                            end_date=end_date,
                            reason=reason,
                            applied_by=username
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
    
    # =========================================================
    # TAB 3: MY APPLICATIONS
    # =========================================================
    with tab3:
        st.subheader("📋 My Leave Applications")
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            username = st.session_state.user.get("username", "")
            user_role = st.session_state.user.get("role", "User")
            
            # Get current user's staff_no
            if is_cloud:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = %s OR personal_no = %s", (username, username))
            else:
                cursor.execute("SELECT staff_no FROM employees WHERE staff_no = ? OR personal_no = ?", (username, username))
            emp_record = cursor.fetchone()
            
            if emp_record:
                staff_no = emp_record[0]
                
                # Get applications for self
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
                st.info("No employee record found for your account")
                conn.close()
                return
                
        except Exception as e:
            st.error(f"Error loading applications: {e}")
            import traceback
            st.code(traceback.format_exc())
    
    # =========================================================
    # TAB 4: APPROVALS
    # =========================================================
    with tab4:
        st.subheader("✅ Leave Approvals (Manager)")
        
        role = st.session_state.user.get("role", "User")
        if role not in ["Admin", "Super Admin", "HR", "Supervisor"]:
            st.error("⛔ Access Denied. You need Manager, HR, Admin or Super Admin role.")
            return
        
        try:
            conn = get_conn()
            is_cloud = st.secrets.get("DATABASE_URL") is not None
            cursor = conn.cursor()
            
            # Get pending applications based on role
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