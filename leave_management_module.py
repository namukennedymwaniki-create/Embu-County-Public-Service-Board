"""
=============================================================
LEAVE MANAGEMENT MODULE
Embu County Public Service Board HR System
=============================================================

This module provides complete leave management functionality including:
- Leave application with automatic calculations
- Multi-level approval workflow
- Leave balance management
- Leave calendar and roster
- Comprehensive reporting
- Admin configuration

Integration Instructions:
1. Place this file in your project directory
2. Add the migration code to your init_db() function
3. Import the module in your main app
4. Add the menu items to your sidebar
5. Add the router to your main function

Author: Embu County Public Service Board
Version: 1.0.0
=============================================================
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import time

# Import from your main app
# Make sure these are available or redefine them
try:
    from streamlit_app_update import get_conn, log_audit, hash_password
except ImportError:
    # Fallback definitions if imported separately
    def get_conn():
        """Get database connection"""
        import sqlite3
        import psycopg2
        if st.secrets.get("DATABASE_URL"):
            return psycopg2.connect(st.secrets.get("DATABASE_URL"))
        return sqlite3.connect("ecde.db", check_same_thread=False)
    
    def log_audit(username, action, record_id, details, status="Success"):
        """Log audit trail"""
        print(f"AUDIT: {username} - {action} - {details}")


# =============================================================
# DATABASE SCHEMA - Add this to your init_db() function
# =============================================================

LEAVE_SCHEMA_SQL = """
-- =============================================
-- LEAVE MANAGEMENT MODULE - Database Schema
-- For Embu County Public Service Board HR System
-- =============================================

-- 1. LEAVE TYPES
CREATE TABLE IF NOT EXISTS leave_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    code VARCHAR(20) NOT NULL UNIQUE,
    description TEXT,
    is_paid BOOLEAN DEFAULT TRUE,
    max_days_per_year INTEGER,
    requires_attachment BOOLEAN DEFAULT FALSE,
    requires_acting_officer BOOLEAN DEFAULT FALSE,
    color VARCHAR(7) DEFAULT '#4A90D9',
    icon VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. LEAVE ENTITLEMENTS
CREATE TABLE IF NOT EXISTS leave_entitlements (
    id SERIAL PRIMARY KEY,
    leave_type_id INTEGER REFERENCES leave_types(id),
    staff_category VARCHAR(50),
    years_of_service_min INTEGER,
    years_of_service_max INTEGER,
    days_entitled INTEGER NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. LEAVE BALANCES
CREATE TABLE IF NOT EXISTS leave_balances (
    id SERIAL PRIMARY KEY,
    staff_id INTEGER NOT NULL,
    leave_type_id INTEGER REFERENCES leave_types(id),
    year INTEGER NOT NULL,
    opening_balance DECIMAL(10,2) DEFAULT 0,
    entitled_days DECIMAL(10,2) DEFAULT 0,
    taken_days DECIMAL(10,2) DEFAULT 0,
    pending_days DECIMAL(10,2) DEFAULT 0,
    approved_days DECIMAL(10,2) DEFAULT 0,
    remaining_days DECIMAL(10,2) DEFAULT 0,
    carried_forward DECIMAL(10,2) DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(staff_id, leave_type_id, year)
);

-- 4. LEAVE APPLICATIONS
CREATE TABLE IF NOT EXISTS leave_applications (
    id SERIAL PRIMARY KEY,
    application_ref VARCHAR(20) NOT NULL UNIQUE,
    staff_id INTEGER NOT NULL,
    leave_type_id INTEGER REFERENCES leave_types(id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    number_of_days DECIMAL(10,2) NOT NULL,
    resumption_date DATE NOT NULL,
    reason TEXT,
    attachment_url TEXT,
    acting_officer_id INTEGER,
    status VARCHAR(20) DEFAULT 'PENDING',
    priority VARCHAR(20) DEFAULT 'NORMAL',
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    created_by INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. LEAVE APPROVALS
CREATE TABLE IF NOT EXISTS leave_approvals (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES leave_applications(id),
    approver_id INTEGER NOT NULL,
    approver_role VARCHAR(50),
    status VARCHAR(20) NOT NULL,
    comment TEXT,
    level INTEGER DEFAULT 1,
    sequence_order INTEGER DEFAULT 0,
    approved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 6. LEAVE RESUMPTION
CREATE TABLE IF NOT EXISTS leave_resumption (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES leave_applications(id),
    staff_id INTEGER NOT NULL,
    actual_resumption_date DATE,
    returned_on_time BOOLEAN DEFAULT TRUE,
    days_extension INTEGER DEFAULT 0,
    reason TEXT,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 7. PUBLIC HOLIDAYS
CREATE TABLE IF NOT EXISTS public_holidays (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    date DATE NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    country VARCHAR(50) DEFAULT 'Kenya',
    region VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, date)
);

-- 8. LEAVE CALENDAR
CREATE TABLE IF NOT EXISTS leave_calendar (
    id SERIAL PRIMARY KEY,
    application_id INTEGER REFERENCES leave_applications(id),
    staff_id INTEGER NOT NULL,
    date DATE NOT NULL,
    is_leave_day BOOLEAN DEFAULT TRUE,
    leave_type_id INTEGER REFERENCES leave_types(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 9. LEAVE SETTINGS
CREATE TABLE IF NOT EXISTS leave_settings (
    id SERIAL PRIMARY KEY,
    setting_key VARCHAR(50) NOT NULL UNIQUE,
    setting_value TEXT,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- INDEXES
CREATE INDEX IF NOT EXISTS idx_leave_applications_staff_id ON leave_applications(staff_id);
CREATE INDEX IF NOT EXISTS idx_leave_applications_status ON leave_applications(status);
CREATE INDEX IF NOT EXISTS idx_leave_applications_dates ON leave_applications(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_leave_applications_ref ON leave_applications(application_ref);
CREATE INDEX IF NOT EXISTS idx_leave_balances_staff_year ON leave_balances(staff_id, year);
CREATE INDEX IF NOT EXISTS idx_leave_calendar_staff_date ON leave_calendar(staff_id, date);
CREATE INDEX IF NOT EXISTS idx_leave_approvals_application ON leave_approvals(application_id);
CREATE INDEX IF NOT EXISTS idx_leave_approvals_approver ON leave_approvals(approver_id);

-- INITIAL DATA
INSERT INTO leave_types (name, code, description, is_paid, max_days_per_year, requires_attachment, requires_acting_officer, color, sort_order)
VALUES 
    ('Annual Leave', 'ANNUAL', 'Regular annual leave', TRUE, 30, FALSE, TRUE, '#4A90D9', 1),
    ('Sick Leave', 'SICK', 'Medical leave with doctor''s note', TRUE, 30, TRUE, FALSE, '#E74C3C', 2),
    ('Maternity Leave', 'MATERNITY', 'Maternity leave for female employees', TRUE, 90, TRUE, TRUE, '#9B59B6', 3),
    ('Paternity Leave', 'PATERNITY', 'Paternity leave for male employees', TRUE, 14, TRUE, TRUE, '#3498DB', 4),
    ('Compassionate Leave', 'COMPASSIONATE', 'Bereavement/family emergency leave', TRUE, 5, TRUE, FALSE, '#F39C12', 5),
    ('Study Leave', 'STUDY', 'Leave for educational purposes', FALSE, 30, TRUE, TRUE, '#2ECC71', 6),
    ('Compensatory Leave', 'COMPENSATORY', 'Leave earned through overtime', TRUE, 10, FALSE, FALSE, '#1ABC9C', 7),
    ('Unpaid Leave', 'UNPAID', 'Leave without pay', FALSE, 30, FALSE, TRUE, '#95A5A6', 8),
    ('Other Leave', 'OTHER', 'Other types of leave', FALSE, 0, FALSE, FALSE, '#7F8C8D', 9)
ON CONFLICT (name) DO NOTHING;

INSERT INTO leave_settings (setting_key, setting_value, description, category)
VALUES 
    ('leave_year_start', '2026-01-01', 'Start date of the leave year', 'general'),
    ('leave_year_end', '2026-12-31', 'End date of the leave year', 'general'),
    ('max_leave_carryforward', '5', 'Maximum days that can be carried forward', 'general'),
    ('auto_approve_days', '3', 'Automatically approve leave requests under this many days', 'workflow'),
    ('require_handover', 'true', 'Require acting officer for leave > X days', 'workflow'),
    ('handover_threshold', '5', 'Days threshold for requiring acting officer', 'workflow'),
    ('default_workflow', 'staff->supervisor->hod->hr', 'Default approval workflow', 'workflow')
ON CONFLICT (setting_key) DO NOTHING;
"""


# =============================================================
# LEAVE CALCULATOR SERVICE
# =============================================================

class LeaveCalculator:
    """Calculate leave days excluding weekends and public holidays"""
    
    def __init__(self):
        self.weekend_days = [5, 6]  # Saturday=5, Sunday=6
    
    def get_public_holidays(self, start_date, end_date):
        """Get public holidays between two dates"""
        conn = get_conn()
        if conn is None:
            return []
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            if is_cloud:
                cursor.execute("""
                    SELECT date FROM public_holidays 
                    WHERE date BETWEEN %s AND %s
                """, (start_str, end_str))
            else:
                cursor.execute("""
                    SELECT date FROM public_holidays 
                    WHERE date BETWEEN ? AND ?
                """, (start_str, end_str))
            
            holidays = [row[0] for row in cursor.fetchall()]
            return holidays
        except Exception as e:
            print(f"Error getting public holidays: {e}")
            return []
        finally:
            conn.close()
    
    def calculate_working_days(self, start_date, end_date):
        """Calculate number of working days between two dates"""
        if start_date > end_date:
            return 0
        
        current_date = start_date
        working_days = 0
        
        holidays = self.get_public_holidays(start_date, end_date)
        holiday_dates = [h.strftime("%Y-%m-%d") if hasattr(h, 'strftime') else str(h) for h in holidays]
        
        while current_date <= end_date:
            if current_date.weekday() not in self.weekend_days:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in holiday_dates:
                    working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    def calculate_resumption_date(self, start_date, total_days):
        """Calculate resumption date based on working days"""
        current_date = start_date
        days_counted = 0
        
        holidays = self.get_public_holidays(start_date, start_date + timedelta(days=total_days * 2))
        holiday_dates = [h.strftime("%Y-%m-%d") if hasattr(h, 'strftime') else str(h) for h in holidays]
        
        while days_counted < total_days:
            current_date += timedelta(days=1)
            if current_date.weekday() not in self.weekend_days:
                date_str = current_date.strftime("%Y-%m-%d")
                if date_str not in holiday_dates:
                    days_counted += 1
        
        return current_date
    
    def get_leave_days_count(self, start_date, end_date):
        """Get total leave days (working days only)"""
        return self.calculate_working_days(start_date, end_date)


# =============================================================
# LEAVE BALANCE SERVICE
# =============================================================

class LeaveBalanceService:
    """Manage leave balances for employees"""
    
    def __init__(self):
        self.calculator = LeaveCalculator()
    
    def get_balance(self, staff_id, leave_type_id, year=None):
        """Get leave balance for a staff member"""
        if year is None:
            year = datetime.now().year
        
        conn = get_conn()
        if conn is None:
            return None
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            if is_cloud:
                cursor.execute("""
                    SELECT opening_balance, entitled_days, taken_days, pending_days, 
                           approved_days, remaining_days, carried_forward
                    FROM leave_balances 
                    WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                """, (staff_id, leave_type_id, year))
            else:
                cursor.execute("""
                    SELECT opening_balance, entitled_days, taken_days, pending_days, 
                           approved_days, remaining_days, carried_forward
                    FROM leave_balances 
                    WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                """, (staff_id, leave_type_id, year))
            
            result = cursor.fetchone()
            
            if result:
                return {
                    'opening_balance': result[0] or 0,
                    'entitled_days': result[1] or 0,
                    'taken_days': result[2] or 0,
                    'pending_days': result[3] or 0,
                    'approved_days': result[4] or 0,
                    'remaining_days': result[5] or 0,
                    'carried_forward': result[6] or 0
                }
            else:
                return self.create_balance(staff_id, leave_type_id, year)
                
        except Exception as e:
            print(f"Error getting balance: {e}")
            return None
        finally:
            conn.close()
    
    def create_balance(self, staff_id, leave_type_id, year):
        """Create a new leave balance for a staff member"""
        conn = get_conn()
        if conn is None:
            return None
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            entitlement = self.get_entitlement(staff_id, leave_type_id)
            opening_balance = 0
            entitled_days = entitlement if entitlement else 0
            
            if is_cloud:
                cursor.execute("""
                    INSERT INTO leave_balances (
                        staff_id, leave_type_id, year, opening_balance, entitled_days,
                        taken_days, pending_days, approved_days, remaining_days, carried_forward
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (staff_id, leave_type_id, year, opening_balance, entitled_days,
                      0, 0, 0, entitled_days, 0))
                balance_id = cursor.fetchone()[0]
            else:
                cursor.execute("""
                    INSERT INTO leave_balances (
                        staff_id, leave_type_id, year, opening_balance, entitled_days,
                        taken_days, pending_days, approved_days, remaining_days, carried_forward
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (staff_id, leave_type_id, year, opening_balance, entitled_days,
                      0, 0, 0, entitled_days, 0))
                balance_id = cursor.lastrowid
            
            conn.commit()
            
            return {
                'opening_balance': opening_balance,
                'entitled_days': entitled_days,
                'taken_days': 0,
                'pending_days': 0,
                'approved_days': 0,
                'remaining_days': entitled_days,
                'carried_forward': 0
            }
            
        except Exception as e:
            print(f"Error creating balance: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
    
    def get_entitlement(self, staff_id, leave_type_id):
        """Get leave entitlement for a staff member"""
        conn = get_conn()
        if conn is None:
            return 0
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            if is_cloud:
                cursor.execute("""
                    SELECT days_entitled FROM leave_entitlements 
                    WHERE leave_type_id = %s 
                    AND (years_of_service_min IS NULL OR years_of_service_min <= 0)
                    AND is_default = TRUE
                    ORDER BY years_of_service_min DESC
                    LIMIT 1
                """, (leave_type_id,))
            else:
                cursor.execute("""
                    SELECT days_entitled FROM leave_entitlements 
                    WHERE leave_type_id = ? 
                    AND (years_of_service_min IS NULL OR years_of_service_min <= 0)
                    AND is_default = TRUE
                    ORDER BY years_of_service_min DESC
                    LIMIT 1
                """, (leave_type_id,))
            
            result = cursor.fetchone()
            
            if result:
                return result[0]
            
            if is_cloud:
                cursor.execute("SELECT max_days_per_year FROM leave_types WHERE id = %s", (leave_type_id,))
            else:
                cursor.execute("SELECT max_days_per_year FROM leave_types WHERE id = ?", (leave_type_id,))
            
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
            
        except Exception as e:
            print(f"Error getting entitlement: {e}")
            return 0
        finally:
            conn.close()
    
    def update_balance(self, staff_id, leave_type_id, days, action, year=None):
        """Update leave balance based on action"""
        if year is None:
            year = datetime.now().year
        
        conn = get_conn()
        if conn is None:
            return False
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            if action == 'apply':
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days + %s,
                            remaining_days = remaining_days - %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                    """, (days, days, staff_id, leave_type_id, year))
                else:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days + ?,
                            remaining_days = remaining_days - ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                    """, (days, days, staff_id, leave_type_id, year))
            
            elif action == 'approve':
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days - %s,
                            approved_days = approved_days + %s,
                            taken_days = taken_days + %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                    """, (days, days, days, staff_id, leave_type_id, year))
                else:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days - ?,
                            approved_days = approved_days + ?,
                            taken_days = taken_days + ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                    """, (days, days, days, staff_id, leave_type_id, year))
            
            elif action in ['reject', 'cancel']:
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days - %s,
                            remaining_days = remaining_days + %s,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                    """, (days, days, staff_id, leave_type_id, year))
                else:
                    cursor.execute("""
                        UPDATE leave_balances 
                        SET pending_days = pending_days - ?,
                            remaining_days = remaining_days + ?,
                            last_updated = CURRENT_TIMESTAMP
                        WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                    """, (days, days, staff_id, leave_type_id, year))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error updating balance: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


# =============================================================
# LEAVE WORKFLOW SERVICE
# =============================================================

class LeaveWorkflowService:
    """Manage leave approval workflow"""
    
    def __init__(self):
        self.workflow_steps = [
            {'level': 1, 'role': 'SUPERVISOR', 'label': 'Supervisor'},
            {'level': 2, 'role': 'HOD', 'label': 'Head of Department'},
            {'level': 3, 'role': 'HR', 'label': 'HR'},
        ]
    
    def get_approval_flow(self, application_id):
        """Get approval flow for a leave application"""
        conn = get_conn()
        if conn is None:
            return []
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            if is_cloud:
                cursor.execute("""
                    SELECT approver_role, status, comment, approver_id, approved_at
                    FROM leave_approvals 
                    WHERE application_id = %s
                    ORDER BY level ASC
                """, (application_id,))
            else:
                cursor.execute("""
                    SELECT approver_role, status, comment, approver_id, approved_at
                    FROM leave_approvals 
                    WHERE application_id = ?
                    ORDER BY level ASC
                """, (application_id,))
            
            results = cursor.fetchall()
            return [{
                'role': row[0],
                'status': row[1],
                'comment': row[2],
                'approver_id': row[3],
                'approved_at': row[4]
            } for row in results]
            
        except Exception as e:
            print(f"Error getting approval flow: {e}")
            return []
        finally:
            conn.close()
    
    def create_approval_chain(self, application_id, staff_id):
        """Create approval chain for a leave application"""
        conn = get_conn()
        if conn is None:
            return False
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            # Get staff details to find supervisors
            if is_cloud:
                cursor.execute("""
                    SELECT department, supervisor_id FROM staff WHERE id = %s
                """, (staff_id,))
            else:
                cursor.execute("""
                    SELECT department, supervisor_id FROM staff WHERE id = ?
                """, (staff_id,))
            
            staff = cursor.fetchone()
            if not staff:
                return False
            
            department = staff[0]
            supervisor_id = staff[1]
            
            # Get HOD for department
            if is_cloud:
                cursor.execute("""
                    SELECT id FROM staff WHERE department = %s AND role = 'HOD'
                """, (department,))
            else:
                cursor.execute("""
                    SELECT id FROM staff WHERE department = ? AND role = 'HOD'
                """, (department,))
            
            hod = cursor.fetchone()
            hod_id = hod[0] if hod else None
            
            # Get HR user
            if is_cloud:
                cursor.execute("SELECT id FROM users WHERE role = 'HR' LIMIT 1")
            else:
                cursor.execute("SELECT id FROM users WHERE role = 'HR' LIMIT 1")
            
            hr = cursor.fetchone()
            hr_id = hr[0] if hr else None
            
            # Create approval records
            approvals = [
                {'level': 1, 'role': 'SUPERVISOR', 'approver_id': supervisor_id},
                {'level': 2, 'role': 'HOD', 'approver_id': hod_id},
                {'level': 3, 'role': 'HR', 'approver_id': hr_id},
            ]
            
            for approval in approvals:
                if approval['approver_id']:
                    if is_cloud:
                        cursor.execute("""
                            INSERT INTO leave_approvals (
                                application_id, approver_id, approver_role, status, level, sequence_order
                            ) VALUES (%s, %s, %s, %s, %s, %s)
                        """, (application_id, approval['approver_id'], approval['role'], 
                              'PENDING', approval['level'], approval['level']))
                    else:
                        cursor.execute("""
                            INSERT INTO leave_approvals (
                                application_id, approver_id, approver_role, status, level, sequence_order
                            ) VALUES (?, ?, ?, ?, ?, ?)
                        """, (application_id, approval['approver_id'], approval['role'],
                              'PENDING', approval['level'], approval['level']))
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error creating approval chain: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def process_approval(self, application_id, approver_id, action, comment):
        """Process an approval (approve/reject/return)"""
        conn = get_conn()
        if conn is None:
            return False
        
        is_cloud = st.secrets.get("DATABASE_URL") is not None
        cursor = conn.cursor()
        
        try:
            # Get current approval status
            if is_cloud:
                cursor.execute("""
                    SELECT id, level, status FROM leave_approvals 
                    WHERE application_id = %s AND approver_id = %s
                """, (application_id, approver_id))
            else:
                cursor.execute("""
                    SELECT id, level, status FROM leave_approvals 
                    WHERE application_id = ? AND approver_id = ?
                """, (application_id, approver_id))
            
            approval = cursor.fetchone()
            if not approval:
                return False
            
            approval_id = approval[0]
            current_level = approval[1]
            current_status = approval[2]
            
            if current_status != 'PENDING':
                return False
            
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Update approval status
            if is_cloud:
                cursor.execute("""
                    UPDATE leave_approvals 
                    SET status = %s, comment = %s, approved_at = %s
                    WHERE id = %s
                """, (action.upper(), comment, now, approval_id))
            else:
                cursor.execute("""
                    UPDATE leave_approvals 
                    SET status = ?, comment = ?, approved_at = ?
                    WHERE id = ?
                """, (action.upper(), comment, now, approval_id))
            
            if action == 'approve':
                # Check if all approvals are done
                if is_cloud:
                    cursor.execute("""
                        SELECT COUNT(*) FROM leave_approvals 
                        WHERE application_id = %s AND status = 'PENDING'
                    """, (application_id,))
                else:
                    cursor.execute("""
                        SELECT COUNT(*) FROM leave_approvals 
                        WHERE application_id = ? AND status = 'PENDING'
                    """, (application_id,))
                
                pending_count = cursor.fetchone()[0]
                
                if pending_count == 0:
                    # All approvals done - update application status
                    if is_cloud:
                        cursor.execute("""
                            UPDATE leave_applications 
                            SET status = 'APPROVED', approved_at = %s
                            WHERE id = %s
                        """, (now, application_id))
                    else:
                        cursor.execute("""
                            UPDATE leave_applications 
                            SET status = 'APPROVED', approved_at = ?
                            WHERE id = ?
                        """, (now, application_id))
                    
                    # Update leave balance
                    if is_cloud:
                        cursor.execute("""
                            SELECT staff_id, leave_type_id, number_of_days 
                            FROM leave_applications WHERE id = %s
                        """, (application_id,))
                    else:
                        cursor.execute("""
                            SELECT staff_id, leave_type_id, number_of_days 
                            FROM leave_applications WHERE id = ?
                        """, (application_id,))
                    
                    app_data = cursor.fetchone()
                    if app_data:
                        balance_service = LeaveBalanceService()
                        balance_service.update_balance(
                            app_data[0], app_data[1], app_data[2], 'approve'
                        )
                
            elif action == 'reject' or action == 'return':
                status = 'REJECTED' if action == 'reject' else 'RETURNED'
                if is_cloud:
                    cursor.execute("""
                        UPDATE leave_applications 
                        SET status = %s
                        WHERE id = %s
                    """, (status, application_id))
                else:
                    cursor.execute("""
                        UPDATE leave_applications 
                        SET status = ?
                        WHERE id = ?
                    """, (status, application_id))
                
                if action == 'reject':
                    if is_cloud:
                        cursor.execute("""
                            SELECT staff_id, leave_type_id, number_of_days 
                            FROM leave_applications WHERE id = %s
                        """, (application_id,))
                    else:
                        cursor.execute("""
                            SELECT staff_id, leave_type_id, number_of_days 
                            FROM leave_applications WHERE id = ?
                        """, (application_id,))
                    
                    app_data = cursor.fetchone()
                    if app_data:
                        balance_service = LeaveBalanceService()
                        balance_service.update_balance(
                            app_data[0], app_data[1], app_data[2], 'reject'
                        )
            
            conn.commit()
            return True
            
        except Exception as e:
            print(f"Error processing approval: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()


# =============================================================
# LEAVE UI FUNCTIONS
# =============================================================

def leave_application():
    """Apply for Leave - Employee Interface"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📝 Apply for Leave</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Submit a leave application</p>
    </div>
    """, unsafe_allow_html=True)
    
    if "user" not in st.session_state or st.session_state.user is None:
        st.error("Please login to apply for leave")
        return
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        # =============================================
        # SEARCH AND FILTER PANEL
        # =============================================
        st.markdown("### 🔍 Search Employees")
        st.caption("Enter search criteria below to find employees")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search_term = st.text_input(
                "Search by Name, Staff No, or Personal No", 
                placeholder="Type to search...", 
                key="leave_search_fixed"
            )
        with col2:
            # Get departments from employees table
            try:
                if is_cloud:
                    cursor.execute("""
                        SELECT DISTINCT department 
                        FROM employees 
                        WHERE department IS NOT NULL AND department != '' 
                        ORDER BY department
                    """)
                else:
                    cursor.execute("""
                        SELECT DISTINCT department 
                        FROM employees 
                        WHERE department IS NOT NULL AND department != '' 
                        ORDER BY department
                    """)
                
                departments = [row[0] for row in cursor.fetchall()]
                departments.insert(0, "All Departments")
                selected_dept = st.selectbox("Filter by Department", departments, key="leave_dept_fixed")
            except:
                selected_dept = "All Departments"
        
        with col3:
            st.write("")  # Spacer
            st.write("")  # Spacer
            search_clicked = st.button("🔍 Search", use_container_width=True, type="primary", key="search_leave_btn")
        
        st.markdown("---")
        
        # =============================================
        # ONLY SEARCH IF BUTTON CLICKED OR SEARCH TERM EXISTS
        # =============================================
        employees = []
        show_results = False
        
        # Check if search should be performed
        if search_clicked or (search_term and search_term.strip()):
            show_results = True
            
            # Build query with filters
            query_params = []
            query_conditions = []
            
            base_query = """
                SELECT staff_no, personal_no, name, department, gender, 
                       current_designation, current_job_group
                FROM employees 
                WHERE staff_no IS NOT NULL AND staff_no != ''
            """
            
            # Search filter - required for search
            if search_term and search_term.strip():
                search_pattern = f"%{search_term.strip()}%"
                if is_cloud:
                    query_conditions.append("(staff_no ILIKE %s OR personal_no ILIKE %s OR name ILIKE %s)")
                else:
                    query_conditions.append("(staff_no LIKE ? OR personal_no LIKE ? OR name LIKE ?)")
                query_params.extend([search_pattern, search_pattern, search_pattern])
            else:
                # If no search term, show a message
                st.info("💡 Please enter a search term to find employees")
                conn.close()
                return
            
            # Department filter
            if selected_dept and selected_dept != "All Departments":
                if is_cloud:
                    query_conditions.append("department = %s")
                else:
                    query_conditions.append("department = ?")
                query_params.append(selected_dept)
            
            # Build final query
            final_query = base_query
            if query_conditions:
                final_query += " AND " + " AND ".join(query_conditions)
            
            final_query += " ORDER BY name LIMIT 50"  # Limit results for performance
            
            # Execute query
            if is_cloud:
                cursor.execute(final_query, tuple(query_params))
            else:
                cursor.execute(final_query, query_params)
            
            employees = cursor.fetchall()
        
        # =============================================
        # DISPLAY RESULTS
        # =============================================
        if show_results:
            if not employees:
                st.warning("⚠️ No employees found matching your search criteria.")
                
                # Check if there are employees without staff_no
                try:
                    if is_cloud:
                        cursor.execute("SELECT COUNT(*) FROM employees WHERE staff_no IS NULL OR staff_no = ''")
                    else:
                        cursor.execute("SELECT COUNT(*) FROM employees WHERE staff_no IS NULL OR staff_no = ''")
                    
                    null_count = cursor.fetchone()[0]
                    if null_count > 0:
                        st.warning(f"⚠️ Found {null_count} employees without staff numbers. Please fix them in the Import Staff tab.")
                except:
                    pass
                
                conn.close()
                return
            
            st.success(f"📊 Found {len(employees)} employee(s)")
            
            # =============================================
            # DISPLAY EMPLOYEE CARDS
            # =============================================
            st.markdown("### 👤 Select Employee")
            
            # Create a nice grid of employee cards
            cols_per_row = 3
            for i in range(0, len(employees), cols_per_row):
                cols = st.columns(cols_per_row)
                for j in range(cols_per_row):
                    if i + j < len(employees):
                        emp = employees[i + j]
                        staff_no, personal_no, name, dept, gender, designation, job_group = emp
                        
                        with cols[j]:
                            # Create a styled card
                            card_html = f"""
                            <div style="
                                border: 1px solid #e0e0e0;
                                border-radius: 10px;
                                padding: 15px;
                                margin: 5px 0;
                                background: {'#f8f9fa' if gender == 'Female' else '#ffffff'};
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                height: 180px;
                                display: flex;
                                flex-direction: column;
                                justify-content: space-between;
                            ">
                                <div>
                                    <strong style="font-size: 16px; color: #1a1a2e;">{name}</strong><br>
                                    <span style="color: #666; font-size: 14px;">Staff No: <strong>{staff_no}</strong></span><br>
                                    <span style="color: #666; font-size: 13px;">Department: {dept or 'N/A'}</span><br>
                                    <span style="color: #666; font-size: 13px;">Designation: {designation or 'N/A'}</span>
                                </div>
                                <div style="margin-top: 10px;">
                                    <span style="
                                        background: {'#28a745' if gender == 'Male' else '#6f42c1'};
                                        color: white;
                                        padding: 2px 10px;
                                        border-radius: 12px;
                                        font-size: 12px;
                                    ">{gender or 'N/A'}</span>
                                    <span style="
                                        background: '#17a2b8';
                                        color: white;
                                        padding: 2px 10px;
                                        border-radius: 12px;
                                        font-size: 12px;
                                        margin-left: 5px;
                                    ">{job_group or 'N/A'}</span>
                                </div>
                            </div>
                            """
                            st.markdown(card_html, unsafe_allow_html=True)
                            
                            # Select button for this employee
                            if st.button(f"📝 Select {name.split()[0]}", key=f"select_leave_{staff_no}", use_container_width=True):
                                st.session_state.selected_staff_no = staff_no
                                st.session_state.selected_employee = {
                                    'staff_no': staff_no,
                                    'personal_no': personal_no,
                                    'name': name,
                                    'department': dept,
                                    'gender': gender,
                                    'designation': designation,
                                    'job_group': job_group
                                }
                                st.rerun()
            
            st.markdown("---")
        else:
            # No search performed yet - show initial message
            st.info("🔍 Enter a search term above and click 'Search' to find employees")
            
            # Show a tip for searching
            with st.expander("💡 Search Tips"):
                st.markdown("""
                - **Search by Name**: Type any part of the employee's name
                - **Search by Staff No**: Enter the staff number
                - **Search by Personal No**: Enter the ID/National ID number
                - **Filter by Department**: Select a department to narrow results
                - **Combine filters**: Use both search and department filter together
                """)
            
            conn.close()
            return
        
        # =============================================
        # LEAVE APPLICATION FORM (when employee selected)
        # =============================================
        if 'selected_staff_no' in st.session_state and st.session_state.selected_staff_no:
            emp_data = st.session_state.selected_employee
            
            st.success(f"✅ Selected: **{emp_data['name']}** (Staff No: {emp_data['staff_no']})")
            
            # Show employee details
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Staff No", emp_data['staff_no'])
            with col2:
                st.metric("Personal No", emp_data['personal_no'])
            with col3:
                st.metric("Department", emp_data['department'] or 'N/A')
            with col4:
                st.metric("Designation", emp_data['designation'] or 'N/A')
            
            st.markdown("---")
            
            # Leave Application Form
            st.subheader("📋 Leave Application Form")
            
            # Get leave types
            try:
                if is_cloud:
                    cursor.execute("""
                        SELECT id, name, requires_attachment, requires_acting_officer, max_days_per_year
                        FROM leave_types WHERE is_active = TRUE ORDER BY sort_order
                    """)
                else:
                    cursor.execute("""
                        SELECT id, name, requires_attachment, requires_acting_officer, max_days_per_year
                        FROM leave_types WHERE is_active = 1 ORDER BY sort_order
                    """)
                
                leave_types = cursor.fetchall()
            except:
                # If leave_types table doesn't exist, use default
                st.warning("⚠️ Leave types not configured. Please contact administrator.")
                leave_types = []
            
            if not leave_types:
                st.warning("⚠️ No leave types configured. Please contact the administrator.")
                conn.close()
                return
            
            leave_type_options = {row[0]: row[1] for row in leave_types}
            
            col1, col2 = st.columns(2)
            with col1:
                selected_leave_type = st.selectbox(
                    "Leave Type",
                    list(leave_type_options.keys()),
                    format_func=lambda x: leave_type_options[x]
                )
                
                # Get leave type details
                leave_type_details = None
                for row in leave_types:
                    if row[0] == selected_leave_type:
                        leave_type_details = row
                        break
                
                requires_attachment = leave_type_details[2] if leave_type_details else False
                requires_acting_officer = leave_type_details[3] if leave_type_details else False
                max_days = leave_type_details[4] if leave_type_details else 30
            
            with col2:
                # Get leave balance - simplified for now
                try:
                    current_year = datetime.now().year
                    
                    try:
                        if is_cloud:
                            cursor.execute("""
                                SELECT remaining_days FROM leave_balances 
                                WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                            """, (emp_data['staff_no'], selected_leave_type, current_year))
                        else:
                            cursor.execute("""
                                SELECT remaining_days FROM leave_balances 
                                WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                            """, (emp_data['staff_no'], selected_leave_type, current_year))
                        
                        result = cursor.fetchone()
                        available_balance = result[0] if result else 30
                    except:
                        available_balance = 30
                    
                    st.info(f"📊 Available Balance: **{available_balance:.0f} days**")
                except Exception as e:
                    st.info("📊 Leave balance: 30 days (default)")
                    available_balance = 30
            
            # Date selection
            st.markdown("### 📅 Leave Period")
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start Date", min_value=datetime.now().date())
            
            with col2:
                end_date = st.date_input("End Date", min_value=start_date)
            
            # Calculate days
            calculator = LeaveCalculator()
            
            if start_date and end_date and start_date <= end_date:
                working_days = calculator.calculate_working_days(start_date, end_date)
                resumption_date = calculator.calculate_resumption_date(end_date, 1)
                
                st.info(f"📊 **Number of working days: {working_days}**")
                st.info(f"📅 **Resumption Date: {resumption_date.strftime('%d/%m/%Y')}**")
                
                if working_days > available_balance:
                    st.warning(f"⚠️ You have {available_balance:.0f} days available. This request requires {working_days} days.")
            else:
                working_days = 0
                resumption_date = end_date + timedelta(days=1) if end_date else None
            
            # Reason
            reason = st.text_area("Reason / Remarks", placeholder="Provide reason for leave...")
            
            # Attachment
            if requires_attachment:
                attachment = st.file_uploader("Attachment", type=["pdf", "jpg", "jpeg", "png", "doc", "docx"])
            else:
                attachment = None
            
            # Acting Officer - using employees table
            if requires_acting_officer or working_days > 5:
                st.markdown("### 🔄 Handover / Acting Officer")
                
                if is_cloud:
                    cursor.execute("""
                        SELECT staff_no, name FROM employees 
                        WHERE staff_no != %s AND staff_no IS NOT NULL
                    """, (emp_data['staff_no'],))
                else:
                    cursor.execute("""
                        SELECT staff_no, name FROM employees 
                        WHERE staff_no != ? AND staff_no IS NOT NULL
                    """, (emp_data['staff_no'],))
                
                acting_staff = cursor.fetchall()
                acting_options = {row[0]: row[1] for row in acting_staff}
                
                acting_officer = st.selectbox(
                    "Select Acting Officer",
                    [None] + list(acting_options.keys()),
                    format_func=lambda x: "None" if x is None else acting_options[x]
                )
            else:
                acting_officer = None
            
            # Submit button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("📤 SUBMIT LEAVE APPLICATION", use_container_width=True, type="primary"):
                    errors = []
                    
                    if not start_date or not end_date:
                        errors.append("Please select start and end dates")
                    elif start_date > end_date:
                        errors.append("Start date must be before end date")
                    
                    if working_days <= 0:
                        errors.append("Leave period must include at least one working day")
                    
                    if working_days > available_balance:
                        errors.append(f"Insufficient balance. Available: {available_balance:.0f} days, Requested: {working_days} days")
                    
                    if not reason or reason.strip() == "":
                        errors.append("Please provide a reason for leave")
                    
                    if requires_attachment and not attachment:
                        errors.append("Attachment is required for this leave type")
                    
                    if (requires_acting_officer or working_days > 5) and not acting_officer:
                        errors.append("Please select an acting officer")
                    
                    if errors:
                        for error in errors:
                            st.error(f"❌ {error}")
                    else:
                        try:
                            # Generate application reference
                            ref_year = datetime.now().strftime("%Y")
                            try:
                                if is_cloud:
                                    cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE EXTRACT(YEAR FROM created_at) = %s", (ref_year,))
                                else:
                                    cursor.execute("SELECT COUNT(*) FROM leave_applications WHERE strftime('%Y', created_at) = ?", (ref_year,))
                                count = cursor.fetchone()[0] or 0
                            except:
                                count = 0
                            
                            application_ref = f"LV-{ref_year}-{str(count + 1).zfill(5)}"
                            
                            attachment_url = attachment.name if attachment else None
                            
                            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # FIX: Get user ID instead of username
                            user_id = st.session_state.user.get('id')
                            if user_id is None:
                                # If user ID not available, try to get it from database
                                username = st.session_state.user.get('username', 'system')
                                if is_cloud:
                                    cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                                else:
                                    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
                                result = cursor.fetchone()
                                user_id = result[0] if result else None
                            
                            # If still no user_id, use NULL
                            created_by = user_id if user_id else None
                            
                            leave_type_id = selected_leave_type
                            acting_officer_val = acting_officer if acting_officer else None
                            
                            if is_cloud:
                                cursor.execute("""
                                    INSERT INTO leave_applications (
                                        application_ref, staff_id, leave_type_id, start_date, end_date,
                                        number_of_days, resumption_date, reason, attachment_url,
                                        acting_officer_id, status, created_by, created_at
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    RETURNING id
                                """, (
                                    application_ref, emp_data['staff_no'], leave_type_id,
                                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
                                    working_days, resumption_date.strftime("%Y-%m-%d"),
                                    reason, attachment_url, acting_officer_val,
                                    'PENDING', created_by, now
                                ))
                                application_id = cursor.fetchone()[0]
                            else:
                                cursor.execute("""
                                    INSERT INTO leave_applications (
                                        application_ref, staff_id, leave_type_id, start_date, end_date,
                                        number_of_days, resumption_date, reason, attachment_url,
                                        acting_officer_id, status, created_by, created_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (
                                    application_ref, emp_data['staff_no'], leave_type_id,
                                    start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
                                    working_days, resumption_date.strftime("%Y-%m-%d"),
                                    reason, attachment_url, acting_officer_val,
                                    'PENDING', created_by, now
                                ))
                                application_id = cursor.lastrowid
                            
                            # Update leave balance if table exists
                            try:
                                current_year = datetime.now().year
                                if is_cloud:
                                    cursor.execute("""
                                        UPDATE leave_balances 
                                        SET pending_days = pending_days + %s,
                                            remaining_days = remaining_days - %s
                                        WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                                    """, (working_days, working_days, emp_data['staff_no'], leave_type_id, current_year))
                                else:
                                    cursor.execute("""
                                        UPDATE leave_balances 
                                        SET pending_days = pending_days + ?,
                                            remaining_days = remaining_days - ?
                                        WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                                    """, (working_days, working_days, emp_data['staff_no'], leave_type_id, current_year))
                            except:
                                pass  # Balance table might not exist
                            
                            conn.commit()
                            
                            log_audit(
                                st.session_state.user.get('username', 'system'),
                                "LEAVE_APPLY",
                                application_id,
                                f"Leave application submitted: {emp_data['name']} - {leave_type_options[selected_leave_type]} ({working_days} days)"
                            )
                            
                            st.success("✅ Leave application submitted successfully!")
                            st.info(f"📋 Application Reference: **{application_ref}**")
                            st.balloons()
                            
                            # Clear selection
                            del st.session_state.selected_staff_no
                            del st.session_state.selected_employee
                            
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Error submitting application: {str(e)}")
                            conn.rollback()
            
            # Clear selection button
            if st.button("❌ Clear Selection", use_container_width=True):
                del st.session_state.selected_staff_no
                del st.session_state.selected_employee
                st.rerun()
        
        else:
            if show_results and employees:
                st.info("👆 Please select an employee from the list above to apply for leave.")
    
    except Exception as e:
        st.error(f"❌ Error loading employees: {str(e)}")
    finally:
        conn.close()


def leave_approvals():
    """Leave Approvals - Supervisor/HOD/HR Interface"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📋 Leave Approvals</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Review and process leave applications</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        # Updated query to use employees table with staff_no as TEXT
        if is_cloud:
            cursor.execute("""
                SELECT 
                    la.id, 
                    la.application_ref, 
                    e.name, 
                    e.department, 
                    lt.name as leave_type, 
                    la.start_date, 
                    la.end_date, 
                    la.number_of_days, 
                    la.resumption_date, 
                    la.reason,
                    la.status, 
                    la.submitted_at,
                    la.staff_id
                FROM leave_applications la
                JOIN employees e ON la.staff_id = e.staff_no
                JOIN leave_types lt ON la.leave_type_id = lt.id
                WHERE la.status = 'PENDING'
                ORDER BY la.submitted_at ASC
            """)
        else:
            cursor.execute("""
                SELECT 
                    la.id, 
                    la.application_ref, 
                    e.name, 
                    e.department, 
                    lt.name as leave_type, 
                    la.start_date, 
                    la.end_date, 
                    la.number_of_days, 
                    la.resumption_date, 
                    la.reason,
                    la.status, 
                    la.submitted_at,
                    la.staff_id
                FROM leave_applications la
                JOIN employees e ON la.staff_id = e.staff_no
                JOIN leave_types lt ON la.leave_type_id = lt.id
                WHERE la.status = 'PENDING'
                ORDER BY la.submitted_at ASC
            """)
        
        pending_applications = cursor.fetchall()
        
        if not pending_applications:
            st.info("✅ No pending leave applications")
            conn.close()
            return
        
        st.info(f"📊 {len(pending_applications)} pending application(s)")
        
        for app in pending_applications:
            app_id, ref, name, department, leave_type, start_date, end_date, days, resumption, reason, status, submitted, staff_id = app
            
            with st.container():
                col1, col2, col3, col4, col5 = st.columns([2, 1.5, 1.5, 1.5, 1])
                
                with col1:
                    st.write(f"**{name}**")
                    st.caption(f"Staff No: {staff_id}")
                    st.caption(ref)
                with col2:
                    st.write(department or "N/A")
                    st.caption(leave_type)
                with col3:
                    st.write(f"{start_date} → {end_date}")
                    st.caption(f"{days} days")
                with col4:
                    st.write(f"Returns: {resumption}")
                    st.caption(f"Submitted: {submitted}")
                with col5:
                    if st.button(f"📋 Review", key=f"review_{app_id}"):
                        st.session_state.leave_application_id = app_id
                        st.rerun()
                
                if st.session_state.get('leave_application_id') == app_id:
                    st.markdown("---")
                    st.subheader(f"📝 Leave Application: {ref}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Employee Details**")
                        st.write(f"Name: {name}")
                        st.write(f"Staff No: {staff_id}")
                        st.write(f"Department: {department or 'N/A'}")
                        st.write(f"Leave Type: {leave_type}")
                        st.markdown("**Leave Details**")
                        st.write(f"From: {start_date}")
                        st.write(f"To: {end_date}")
                        st.write(f"Days: {days}")
                        st.write(f"Resumption: {resumption}")
                    with col2:
                        st.markdown("**Reason**")
                        st.write(reason or "No reason provided")
                    
                    st.markdown("### ✅ Approval Actions")
                    comment = st.text_area("Comment", placeholder="Add your comments...", key=f"comment_{app_id}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("✅ Approve", key=f"approve_{app_id}", use_container_width=True, type="primary"):
                            try:
                                # Update approval status
                                if is_cloud:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP
                                        WHERE id = %s
                                    """, (app_id,))
                                else:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP
                                        WHERE id = ?
                                    """, (app_id,))
                                
                                # Update leave balance
                                try:
                                    if is_cloud:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - %s,
                                                approved_days = approved_days + %s,
                                                taken_days = taken_days + %s
                                            WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                                        """, (days, days, days, staff_id, app[2], datetime.now().year))
                                    else:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - ?,
                                                approved_days = approved_days + ?,
                                                taken_days = taken_days + ?
                                            WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                                        """, (days, days, days, staff_id, app[2], datetime.now().year))
                                except:
                                    pass
                                
                                conn.commit()
                                
                                log_audit(
                                    st.session_state.user.get('username', 'system'), 
                                    "LEAVE_APPROVE", 
                                    app_id, 
                                    f"Leave application {ref} approved"
                                )
                                
                                st.success("✅ Application approved!")
                                del st.session_state.leave_application_id
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error approving: {e}")
                                conn.rollback()
                    
                    with col2:
                        if st.button("↩️ Return", key=f"return_{app_id}", use_container_width=True):
                            try:
                                if is_cloud:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'RETURNED'
                                        WHERE id = %s
                                    """, (app_id,))
                                else:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'RETURNED'
                                        WHERE id = ?
                                    """, (app_id,))
                                
                                # Return days to balance
                                try:
                                    if is_cloud:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - %s,
                                                remaining_days = remaining_days + %s
                                            WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                                        """, (days, days, staff_id, app[2], datetime.now().year))
                                    else:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - ?,
                                                remaining_days = remaining_days + ?
                                            WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                                        """, (days, days, staff_id, app[2], datetime.now().year))
                                except:
                                    pass
                                
                                conn.commit()
                                
                                log_audit(
                                    st.session_state.user.get('username', 'system'), 
                                    "LEAVE_RETURN", 
                                    app_id, 
                                    f"Leave application {ref} returned"
                                )
                                
                                st.success("✅ Application returned for revision!")
                                del st.session_state.leave_application_id
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error returning: {e}")
                                conn.rollback()
                    
                    with col3:
                        if st.button("❌ Reject", key=f"reject_{app_id}", use_container_width=True):
                            try:
                                if is_cloud:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'REJECTED'
                                        WHERE id = %s
                                    """, (app_id,))
                                else:
                                    cursor.execute("""
                                        UPDATE leave_applications 
                                        SET status = 'REJECTED'
                                        WHERE id = ?
                                    """, (app_id,))
                                
                                # Return days to balance
                                try:
                                    if is_cloud:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - %s,
                                                remaining_days = remaining_days + %s
                                            WHERE staff_id = %s AND leave_type_id = %s AND year = %s
                                        """, (days, days, staff_id, app[2], datetime.now().year))
                                    else:
                                        cursor.execute("""
                                            UPDATE leave_balances 
                                            SET pending_days = pending_days - ?,
                                                remaining_days = remaining_days + ?
                                            WHERE staff_id = ? AND leave_type_id = ? AND year = ?
                                        """, (days, days, staff_id, app[2], datetime.now().year))
                                except:
                                    pass
                                
                                conn.commit()
                                
                                log_audit(
                                    st.session_state.user.get('username', 'system'), 
                                    "LEAVE_REJECT", 
                                    app_id, 
                                    f"Leave application {ref} rejected"
                                )
                                
                                st.success("✅ Application rejected!")
                                del st.session_state.leave_application_id
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error rejecting: {e}")
                                conn.rollback()
                
                st.divider()
    
    except Exception as e:
        st.error(f"Error loading approvals: {e}")
    finally:
        conn.close()

def leave_calendar():
    """Leave Calendar View"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📅 Leave Calendar</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">View leave schedules by department and type</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        # Filters
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Get departments from employees table
            if is_cloud:
                cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
            else:
                cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
            
            departments = [row[0] for row in cursor.fetchall()]
            selected_department = st.selectbox("Department", ["All"] + departments)
        
        with col2:
            if is_cloud:
                cursor.execute("SELECT name FROM leave_types WHERE is_active = TRUE ORDER BY sort_order")
            else:
                cursor.execute("SELECT name FROM leave_types WHERE is_active = 1 ORDER BY sort_order")
            
            leave_types = [row[0] for row in cursor.fetchall()]
            selected_leave_type = st.selectbox("Leave Type", ["All"] + leave_types)
        
        with col3:
            if 'calendar_month' not in st.session_state:
                st.session_state.calendar_month = datetime.now().month
            if 'calendar_year' not in st.session_state:
                st.session_state.calendar_year = datetime.now().year
            
            month_names = ["January", "February", "March", "April", "May", "June",
                          "July", "August", "September", "October", "November", "December"]
            
            col_a, col_b, col_c = st.columns([1, 2, 1])
            with col_a:
                if st.button("◀", key="prev_month_cal"):
                    if st.session_state.calendar_month > 1:
                        st.session_state.calendar_month -= 1
                    else:
                        st.session_state.calendar_month = 12
                        st.session_state.calendar_year -= 1
                    st.rerun()
            with col_b:
                st.write(f"**{month_names[st.session_state.calendar_month - 1]} {st.session_state.calendar_year}**")
            with col_c:
                if st.button("▶", key="next_month_cal"):
                    if st.session_state.calendar_month < 12:
                        st.session_state.calendar_month += 1
                    else:
                        st.session_state.calendar_month = 1
                        st.session_state.calendar_year += 1
                    st.rerun()
        
        with col4:
            if st.button("📅 Today", use_container_width=True, key="today_cal"):
                st.session_state.calendar_month = datetime.now().month
                st.session_state.calendar_year = datetime.now().year
                st.rerun()
        
        # Get leave data for the month
        month_start = datetime(st.session_state.calendar_year, st.session_state.calendar_month, 1)
        if st.session_state.calendar_month == 12:
            month_end = datetime(st.session_state.calendar_year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = datetime(st.session_state.calendar_year, st.session_state.calendar_month + 1, 1) - timedelta(days=1)
        
        month_start_str = month_start.strftime("%Y-%m-%d")
        month_end_str = month_end.strftime("%Y-%m-%d")
        
        # Updated query to use employees table
        query = """
            SELECT e.name, e.department, la.start_date, la.end_date, lt.name as leave_type, lt.color
            FROM leave_applications la
            JOIN employees e ON la.staff_id = e.staff_no
            JOIN leave_types lt ON la.leave_type_id = lt.id
            WHERE la.status = 'APPROVED'
            AND la.start_date <= %s AND la.end_date >= %s
        """
        
        if selected_department != "All":
            query += f" AND e.department = '{selected_department}'"
        if selected_leave_type != "All":
            query += f" AND lt.name = '{selected_leave_type}'"
        
        query += " ORDER BY e.name, la.start_date"
        
        if is_cloud:
            cursor.execute(query, (month_end_str, month_start_str))
        else:
            cursor.execute(query, (month_end_str, month_start_str))
        
        leave_entries = cursor.fetchall()
        
        # Build calendar
        st.markdown("---")
        
        first_day = month_start.weekday()
        days_in_month = (month_end - month_start).days + 1
        
        calendar_data = {}
        for entry in leave_entries:
            name, department, start_date, end_date, leave_type, color = entry
            current_date = start_date
            while current_date <= end_date:
                if current_date.month == st.session_state.calendar_month:
                    day_key = current_date.day
                    if day_key not in calendar_data:
                        calendar_data[day_key] = []
                    calendar_data[day_key].append({
                        'name': name,
                        'department': department,
                        'leave_type': leave_type,
                        'color': color
                    })
                current_date += timedelta(days=1)
        
        # Display calendar
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        
        cols = st.columns(7)
        for i, day in enumerate(days):
            with cols[i]:
                st.markdown(f"**{day}**")
        
        week_rows = []
        current_day = 1
        week = []
        for i in range(7):
            if i >= first_day:
                week.append(current_day)
                current_day += 1
            else:
                week.append(None)
        week_rows.append(week)
        
        while current_day <= days_in_month:
            week = []
            for i in range(7):
                if current_day <= days_in_month:
                    week.append(current_day)
                    current_day += 1
                else:
                    week.append(None)
            week_rows.append(week)
        
        today = datetime.now().day
        
        for week in week_rows:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day is not None:
                        if day == today and st.session_state.calendar_month == datetime.now().month and st.session_state.calendar_year == datetime.now().year:
                            st.markdown(f"**🔵 {day}**")
                        else:
                            st.write(f"**{day}**")
                        
                        if day in calendar_data:
                            for entry in calendar_data[day]:
                                color = entry.get('color', '#4A90D9')
                                st.markdown(f"""
                                <div style="background: {color}; color: white; padding: 2px 4px; border-radius: 4px; font-size: 10px; margin: 1px 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                                    {entry['name'][:10]}
                                </div>
                                """, unsafe_allow_html=True)
                    else:
                        st.write("")
        
        total_entries = sum(len(entries) for entries in calendar_data.values())
        st.caption(f"📊 {total_entries} leave entries for this month")
    
    except Exception as e:
        st.error(f"Error loading calendar: {e}")
    finally:
        conn.close()

def leave_roster():
    """Leave Roster - Who is away and when they're returning"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📋 Leave Roster</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">View staff currently on leave and their return dates</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            search_term = st.text_input("Search Employee", placeholder="Name or Staff No...")
        with col2:
            if is_cloud:
                cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL ORDER BY department")
            else:
                cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL ORDER BY department")
            
            departments = [row[0] for row in cursor.fetchall()]
            selected_department = st.selectbox("Department", ["All"] + departments)
        with col3:
            if is_cloud:
                cursor.execute("SELECT name FROM leave_types WHERE is_active = TRUE ORDER BY sort_order")
            else:
                cursor.execute("SELECT name FROM leave_types WHERE is_active = 1 ORDER BY sort_order")
            
            leave_types = [row[0] for row in cursor.fetchall()]
            selected_leave_type = st.selectbox("Leave Type", ["All"] + leave_types)
        with col4:
            status_filter = st.selectbox("Status", ["All", "On Leave", "Returning Soon (7 days)"])
        
        today = datetime.now().strftime("%Y-%m-%d")
        week_end = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        
        query = """
            SELECT e.staff_no, e.name, e.department, lt.name as leave_type, 
                   la.start_date, la.end_date, la.number_of_days, la.resumption_date,
                   e.personal_no
            FROM leave_applications la
            JOIN employees e ON la.staff_id = e.staff_no
            JOIN leave_types lt ON la.leave_type_id = lt.id
            WHERE la.status = 'APPROVED'
        """
        
        if status_filter == "On Leave":
            query += f" AND la.start_date <= '{today}' AND la.end_date >= '{today}'"
        elif status_filter == "Returning Soon (7 days)":
            query += f" AND la.resumption_date BETWEEN '{today}' AND '{week_end}'"
        
        if selected_department != "All":
            query += f" AND e.department = '{selected_department}'"
        if selected_leave_type != "All":
            query += f" AND lt.name = '{selected_leave_type}'"
        if search_term:
            if is_cloud:
                query += f" AND (e.name ILIKE '%{search_term}%' OR e.staff_no LIKE '%{search_term}%')"
            else:
                query += f" AND (e.name LIKE '%{search_term}%' OR e.staff_no LIKE '%{search_term}%')"
        
        query += " ORDER BY la.resumption_date ASC"
        
        if is_cloud:
            cursor.execute(query)
        else:
            cursor.execute(query)
        
        roster_data = cursor.fetchall()
        
        if not roster_data:
            st.info("📭 No staff currently on leave")
            conn.close()
            return
        
        st.success(f"📊 Found {len(roster_data)} staff on leave")
        
        roster_list = []
        for row in roster_data:
            staff_no, name, department, leave_type, start_date, end_date, days, resumption, personal_no = row
            
            today_dt = datetime.now().date()
            resumption_dt = resumption if isinstance(resumption, date) else datetime.strptime(str(resumption), "%Y-%m-%d").date()
            days_until_return = (resumption_dt - today_dt).days
            
            roster_list.append({
                'Staff No': staff_no,
                'Employee': name,
                'Department': department or 'N/A',
                'Leave Type': leave_type,
                'Period': f"{start_date} - {end_date}",
                'Days': days,
                'Return Date': resumption,
                'Days Until Return': days_until_return
            })
        
        roster_df = pd.DataFrame(roster_list)
        
        def color_return(row):
            if row['Days Until Return'] <= 0:
                return ['background-color: #f8d7da; color: #721c24;'] * len(row)
            elif row['Days Until Return'] <= 3:
                return ['background-color: #fff3cd; color: #856404;'] * len(row)
            elif row['Days Until Return'] <= 7:
                return ['background-color: #d4edda; color: #155724;'] * len(row)
            return [''] * len(row)
        
        styled_roster = roster_df.style.apply(color_return, axis=1)
        st.dataframe(styled_roster, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            csv = roster_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export as CSV", csv, f"leave_roster_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv", use_container_width=True)
    
    except Exception as e:
        st.error(f"Error loading roster: {e}")
    finally:
        conn.close()


def leave_balances():
    """Leave Balances - View staff leave balances"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📊 Leave Balances</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">View staff leave entitlements and balances</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        current_year = datetime.now().year
        selected_year = st.selectbox("Leave Year", list(range(current_year - 2, current_year + 2)), index=2)
        search_term = st.text_input("Search Employee", placeholder="Name or ID...")
        
        query = """
            SELECT s.id, s.name, s.department, s.personal_no,
                   lb.entitled_days, lb.taken_days, lb.pending_days,
                   lb.approved_days, lb.remaining_days, lb.opening_balance
            FROM staff s
            LEFT JOIN leave_balances lb ON s.id = lb.staff_id AND lb.year = %s
        """
        
        if search_term:
            if is_cloud:
                query += f" AND (s.name ILIKE '%{search_term}%' OR s.id_number LIKE '%{search_term}%')"
            else:
                query += f" AND (s.name LIKE '%{search_term}%' OR s.id_number LIKE '%{search_term}%')"
        
        query += " ORDER BY s.name"
        
        if is_cloud:
            cursor.execute(query, (selected_year,))
        else:
            cursor.execute(query, (selected_year,))
        
        balance_data = cursor.fetchall()
        
        if not balance_data:
            st.info("📭 No staff records found")
            conn.close()
            return
        
        balance_list = []
        for row in balance_data:
            staff_id, name, department, personal_no, entitled, taken, pending, approved, remaining, opening = row
            balance_list.append({
                'Employee': name,
                'Personal No': personal_no or 'N/A',
                'Department': department or 'N/A',
                'Entitled': entitled or 0,
                'Taken': taken or 0,
                'Pending': pending or 0,
                'Approved': approved or 0,
                'Remaining': remaining or 0,
                'Opening Balance': opening or 0
            })
        
        balance_df = pd.DataFrame(balance_list)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Staff", len(balance_df))
        with col2:
            st.metric("Total Days Taken", f"{balance_df['Taken'].sum():.0f}")
        with col3:
            st.metric("Total Pending", f"{balance_df['Pending'].sum():.0f}")
        with col4:
            st.metric("Total Remaining", f"{balance_df['Remaining'].sum():.0f}")
        
        st.markdown("---")
        st.dataframe(balance_df, use_container_width=True)
        
        csv = balance_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Balances (CSV)", csv, f"leave_balances_{selected_year}.csv", "text/csv", use_container_width=True)
    
    except Exception as e:
        st.error(f"Error loading balances: {e}")
    finally:
        conn.close()


def leave_reports():
    """Leave Reports"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📊 Leave Reports</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Generate leave reports and analytics</p>
    </div>
    """, unsafe_allow_html=True)
    
    report_type = st.selectbox(
        "Select Report Type",
        [
            "Leave Utilization Report",
            "Staff on Leave Report",
            "Leave Applications Report",
            "Department Leave Report",
            "Monthly Leave Report",
            "Leave Balance Report"
        ]
    )
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", datetime.now())
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    try:
        # Get departments from employees table
        if is_cloud:
            cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
        else:
            cursor.execute("SELECT DISTINCT department FROM employees WHERE department IS NOT NULL AND department != '' ORDER BY department")
        
        departments = [row[0] for row in cursor.fetchall()]
        selected_department = st.selectbox("Department", ["All"] + departments)
        
        if report_type == "Leave Utilization Report":
            st.subheader("📊 Leave Utilization Report")
            
            if is_cloud:
                cursor.execute("""
                    SELECT lt.name as leave_type, 
                           COALESCE(SUM(lb.taken_days), 0) as taken,
                           COALESCE(SUM(lb.entitled_days), 0) as entitled,
                           COUNT(DISTINCT lb.staff_id) as staff_count
                    FROM leave_types lt
                    LEFT JOIN leave_balances lb ON lt.id = lb.leave_type_id
                    WHERE lt.is_active = TRUE
                    GROUP BY lt.id, lt.name
                    ORDER BY lt.sort_order
                """)
            else:
                cursor.execute("""
                    SELECT lt.name as leave_type, 
                           COALESCE(SUM(lb.taken_days), 0) as taken,
                           COALESCE(SUM(lb.entitled_days), 0) as entitled,
                           COUNT(DISTINCT lb.staff_id) as staff_count
                    FROM leave_types lt
                    LEFT JOIN leave_balances lb ON lt.id = lb.leave_type_id
                    WHERE lt.is_active = 1
                    GROUP BY lt.id, lt.name
                    ORDER BY lt.sort_order
                """)
            
            data = cursor.fetchall()
            if data:
                df = pd.DataFrame([{
                    'Leave Type': row[0],
                    'Total Staff': row[3],
                    'Days Taken': row[1],
                    'Days Entitled': row[2],
                    'Utilization %': f"{(row[1] / row[2] * 100) if row[2] > 0 else 0:.1f}%"
                } for row in data])
                st.dataframe(df, use_container_width=True)
                
                chart_data = df[['Leave Type', 'Days Taken', 'Days Entitled']].set_index('Leave Type')
                st.bar_chart(chart_data)
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", csv, f"utilization_report_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
        
        elif report_type == "Staff on Leave Report":
            st.subheader("👥 Staff on Leave Report")
            
            start_str = start_date.strftime("%Y-%m-%d")
            end_str = end_date.strftime("%Y-%m-%d")
            
            query = """
                SELECT e.name, e.department, lt.name as leave_type,
                       la.start_date, la.end_date, la.number_of_days, la.resumption_date,
                       la.application_ref
                FROM leave_applications la
                JOIN employees e ON la.staff_id = e.staff_no
                JOIN leave_types lt ON la.leave_type_id = lt.id
                WHERE la.status = 'APPROVED'
                AND la.start_date <= %s AND la.end_date >= %s
            """
            
            if selected_department != "All":
                query += f" AND e.department = '{selected_department}'"
            query += " ORDER BY e.name"
            
            if is_cloud:
                cursor.execute(query, (end_str, start_str))
            else:
                cursor.execute(query, (end_str, start_str))
            
            data = cursor.fetchall()
            if data:
                df = pd.DataFrame([{
                    'Employee': row[0],
                    'Department': row[1] or 'N/A',
                    'Leave Type': row[2],
                    'From': row[3],
                    'To': row[4],
                    'Days': row[5],
                    'Returns': row[6],
                    'Ref': row[7]
                } for row in data])
                st.dataframe(df, use_container_width=True)
                st.caption(f"📊 {len(df)} staff on leave")
                
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Report", csv, f"staff_on_leave_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
            else:
                st.info("No staff on leave in this period")
        
        # ... (other report types need similar updates - change staff to employees)
        
    except Exception as e:
        st.error(f"Error generating report: {e}")
    finally:
        conn.close()


def leave_admin():
    """Leave Administration - System Configuration"""
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">⚙️ Leave Administration</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Configure leave settings, types, entitlements, and policies</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user.get("role") not in ["Admin", "Super Admin"]:
        st.error("⛔ Access Denied. Admin or Super Admin privileges required.")
        return
    
    conn = get_conn()
    if conn is None:
        st.error("Database connection failed")
        return
    
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    cursor = conn.cursor()
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🏷️ Leave Types",
        "📋 Entitlements",
        "📅 Public Holidays",
        "⚙️ System Settings",
        "📋 Policies"
    ])
    
    with tab1:
        st.subheader("🏷️ Manage Leave Types")
        
        with st.expander("➕ Add New Leave Type", expanded=False):
            with st.form("add_leave_type_form"):
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input("Name *", placeholder="e.g., Annual Leave")
                    code = st.text_input("Code *", placeholder="e.g., ANNUAL")
                    description = st.text_area("Description")
                    max_days = st.number_input("Maximum Days per Year", min_value=0, value=30)
                with col2:
                    is_paid = st.checkbox("Paid Leave", value=True)
                    requires_attachment = st.checkbox("Requires Attachment", value=False)
                    requires_acting = st.checkbox("Requires Acting Officer", value=False)
                    color = st.color_picker("Color", value="#4A90D9")
                    sort_order = st.number_input("Sort Order", min_value=0, value=0)
                
                if st.form_submit_button("Add Leave Type", use_container_width=True) and name and code:
                    try:
                        if is_cloud:
                            cursor.execute("""
                                INSERT INTO leave_types (
                                    name, code, description, is_paid, max_days_per_year,
                                    requires_attachment, requires_acting_officer, color, sort_order
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (name, code.upper(), description, is_paid, max_days,
                                  requires_attachment, requires_acting, color, sort_order))
                        else:
                            cursor.execute("""
                                INSERT INTO leave_types (
                                    name, code, description, is_paid, max_days_per_year,
                                    requires_attachment, requires_acting_officer, color, sort_order
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (name, code.upper(), description, is_paid, max_days,
                                  requires_attachment, requires_acting, color, sort_order))
                        conn.commit()
                        st.success(f"✅ Leave type '{name}' added successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        # Display existing leave types
        if is_cloud:
            cursor.execute("""
                SELECT id, name, code, description, is_paid, max_days_per_year,
                       requires_attachment, requires_acting_officer, color, is_active, sort_order
                FROM leave_types ORDER BY sort_order
            """)
        else:
            cursor.execute("""
                SELECT id, name, code, description, is_paid, max_days_per_year,
                       requires_attachment, requires_acting_officer, color, is_active, sort_order
                FROM leave_types ORDER BY sort_order
            """)
        
        leave_types = cursor.fetchall()
        
        if leave_types:
            for lt in leave_types:
                lt_id, name, code, description, is_paid, max_days, req_attach, req_acting, color, is_active, sort_order = lt
                with st.expander(f"{'🟢 ' if is_active else '🔴 '}{name} ({code})", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Description:** {description or 'N/A'}")
                        st.write(f"**Max Days/Year:** {max_days}")
                        st.write(f"**Paid:** {'Yes' if is_paid else 'No'}")
                    with col2:
                        st.write(f"**Requires Attachment:** {'Yes' if req_attach else 'No'}")
                        st.write(f"**Requires Acting Officer:** {'Yes' if req_acting else 'No'}")
                        st.write(f"**Color:** {color}")
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if is_active:
                            if st.button(f"🔄 Deactivate", key=f"deactivate_{lt_id}"):
                                if is_cloud:
                                    cursor.execute("UPDATE leave_types SET is_active = FALSE WHERE id = %s", (lt_id,))
                                else:
                                    cursor.execute("UPDATE leave_types SET is_active = 0 WHERE id = ?", (lt_id,))
                                conn.commit()
                                st.rerun()
                        else:
                            if st.button(f"🔄 Activate", key=f"activate_{lt_id}"):
                                if is_cloud:
                                    cursor.execute("UPDATE leave_types SET is_active = TRUE WHERE id = %s", (lt_id,))
                                else:
                                    cursor.execute("UPDATE leave_types SET is_active = 1 WHERE id = ?", (lt_id,))
                                conn.commit()
                                st.rerun()
                    with col3:
                        if st.button(f"🗑️ Delete", key=f"delete_{lt_id}"):
                            if is_cloud:
                                cursor.execute("DELETE FROM leave_types WHERE id = %s", (lt_id,))
                            else:
                                cursor.execute("DELETE FROM leave_types WHERE id = ?", (lt_id,))
                            conn.commit()
                            st.rerun()
        else:
            st.info("No leave types configured")
    
    with tab2:
        st.subheader("📋 Leave Entitlements")
        
        if is_cloud:
            cursor.execute("SELECT id, name FROM leave_types WHERE is_active = TRUE ORDER BY sort_order")
        else:
            cursor.execute("SELECT id, name FROM leave_types WHERE is_active = 1 ORDER BY sort_order")
        
        leave_types = cursor.fetchall()
        
        if not leave_types:
            st.warning("Please create leave types first")
        else:
            with st.expander("➕ Add Entitlement", expanded=False):
                with st.form("add_entitlement_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        leave_type_id = st.selectbox(
                            "Leave Type",
                            [row[0] for row in leave_types],
                            format_func=lambda x: next((row[1] for row in leave_types if row[0] == x), str(x))
                        )
                        staff_category = st.text_input("Staff Category", placeholder="e.g., Permanent, Contract")
                        years_min = st.number_input("Years of Service (Min)", min_value=0, value=0)
                    with col2:
                        years_max = st.number_input("Years of Service (Max)", min_value=0, value=0)
                        days_entitled = st.number_input("Days Entitled", min_value=1, value=30)
                        is_default = st.checkbox("Default Entitlement", value=False)
                    
                    if st.form_submit_button("Add Entitlement", use_container_width=True):
                        try:
                            if is_cloud:
                                cursor.execute("""
                                    INSERT INTO leave_entitlements (
                                        leave_type_id, staff_category, years_of_service_min, years_of_service_max,
                                        days_entitled, is_default
                                    ) VALUES (%s, %s, %s, %s, %s, %s)
                                """, (leave_type_id, staff_category or None, years_min, years_max if years_max > 0 else None, days_entitled, is_default))
                            else:
                                cursor.execute("""
                                    INSERT INTO leave_entitlements (
                                        leave_type_id, staff_category, years_of_service_min, years_of_service_max,
                                        days_entitled, is_default
                                    ) VALUES (?, ?, ?, ?, ?, ?)
                                """, (leave_type_id, staff_category or None, years_min, years_max if years_max > 0 else None, days_entitled, is_default))
                            conn.commit()
                            st.success("✅ Entitlement added successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
            
            if is_cloud:
                cursor.execute("""
                    SELECT le.id, lt.name as leave_type, le.staff_category,
                           le.years_of_service_min, le.years_of_service_max,
                           le.days_entitled, le.is_default
                    FROM leave_entitlements le
                    JOIN leave_types lt ON le.leave_type_id = lt.id
                    ORDER BY lt.sort_order, le.staff_category
                """)
            else:
                cursor.execute("""
                    SELECT le.id, lt.name as leave_type, le.staff_category,
                           le.years_of_service_min, le.years_of_service_max,
                           le.days_entitled, le.is_default
                    FROM leave_entitlements le
                    JOIN leave_types lt ON le.leave_type_id = lt.id
                    ORDER BY lt.sort_order, le.staff_category
                """)
            
            entitlements = cursor.fetchall()
            if entitlements:
                df = pd.DataFrame([{
                    'ID': row[0],
                    'Leave Type': row[1],
                    'Category': row[2] or 'All',
                    'Years Min': row[3] or 0,
                    'Years Max': row[4] or '∞',
                    'Days': row[5],
                    'Default': '✓' if row[6] else ''
                } for row in entitlements])
                st.dataframe(df, use_container_width=True)
                
                ent_ids = [ent[0] for ent in entitlements]
                delete_ent_id = st.selectbox("Delete Entitlement", [0] + ent_ids, format_func=lambda x: "Select to delete..." if x == 0 else f"ID: {x}")
                if delete_ent_id and delete_ent_id != 0:
                    if st.button("🗑️ Delete Entitlement", use_container_width=True):
                        if is_cloud:
                            cursor.execute("DELETE FROM leave_entitlements WHERE id = %s", (delete_ent_id,))
                        else:
                            cursor.execute("DELETE FROM leave_entitlements WHERE id = ?", (delete_ent_id,))
                        conn.commit()
                        st.rerun()
            else:
                st.info("No entitlements configured")
    
    with tab3:
        st.subheader("📅 Public Holidays")
        
        with st.form("add_holiday_form"):
            col1, col2 = st.columns(2)
            with col1:
                holiday_name = st.text_input("Holiday Name *", placeholder="e.g., Jamhuri Day")
                holiday_date = st.date_input("Date")
            with col2:
                is_recurring = st.checkbox("Recurring Yearly", value=False)
                country = st.text_input("Country", value="Kenya")
                region = st.text_input("Region (optional)", placeholder="e.g., Embu County")
            
            if st.form_submit_button("Add Holiday", use_container_width=True) and holiday_name and holiday_date:
                try:
                    if is_cloud:
                        cursor.execute("""
                            INSERT INTO public_holidays (name, date, is_recurring, country, region)
                            VALUES (%s, %s, %s, %s, %s)
                        """, (holiday_name, holiday_date.strftime("%Y-%m-%d"), is_recurring, country, region or None))
                    else:
                        cursor.execute("""
                            INSERT INTO public_holidays (name, date, is_recurring, country, region)
                            VALUES (?, ?, ?, ?, ?)
                        """, (holiday_name, holiday_date.strftime("%Y-%m-%d"), is_recurring, country, region or None))
                    conn.commit()
                    st.success(f"✅ Holiday '{holiday_name}' added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
        
        if is_cloud:
            cursor.execute("SELECT id, name, date, is_recurring, country, region FROM public_holidays ORDER BY date")
        else:
            cursor.execute("SELECT id, name, date, is_recurring, country, region FROM public_holidays ORDER BY date")
        
        holidays = cursor.fetchall()
        if holidays:
            for h in holidays:
                h_id, name, date, is_recurring, country, region = h
                col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
                with col1:
                    st.write(f"**{name}**")
                with col2:
                    st.write(f"{date}")
                with col3:
                    st.write("🔄 Recurring" if is_recurring else "📅 One-time")
                with col4:
                    if st.button(f"🗑️", key=f"del_holiday_{h_id}"):
                        if is_cloud:
                            cursor.execute("DELETE FROM public_holidays WHERE id = %s", (h_id,))
                        else:
                            cursor.execute("DELETE FROM public_holidays WHERE id = ?", (h_id,))
                        conn.commit()
                        st.rerun()
                st.divider()
        else:
            st.info("No public holidays configured")
    
    with tab4:
        st.subheader("⚙️ Leave System Settings")
        
        if is_cloud:
            cursor.execute("SELECT setting_key, setting_value, description FROM leave_settings ORDER BY category, setting_key")
        else:
            cursor.execute("SELECT setting_key, setting_value, description FROM leave_settings ORDER BY category, setting_key")
        
        settings = cursor.fetchall()
        if settings:
            for setting_key, setting_value, description in settings:
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"**{setting_key.replace('_', ' ').title()}**")
                    st.caption(description or "")
                with col2:
                    new_value = st.text_input("Value", value=setting_value, key=f"setting_{setting_key}", label_visibility="collapsed")
                with col3:
                    if new_value != setting_value:
                        if st.button(f"💾", key=f"save_setting_{setting_key}"):
                            if is_cloud:
                                cursor.execute("UPDATE leave_settings SET setting_value = %s WHERE setting_key = %s", (new_value, setting_key))
                            else:
                                cursor.execute("UPDATE leave_settings SET setting_value = ? WHERE setting_key = ?", (new_value, setting_key))
                            conn.commit()
                            st.success("✅ Saved!")
                            st.rerun()
                st.divider()
        else:
            st.info("No settings configured")
    
    with tab5:
        st.subheader("📋 Leave Policies")
        
        policy_content = st.text_area(
            "Leave Policy Document",
            value="""# Embu County Public Service Board - Leave Policy

## 1. Annual Leave
- Every employee is entitled to 30 working days of annual leave per year
- Leave must be taken within the leave year
- Unused leave may be carried forward with approval

## 2. Sick Leave
- Employees are entitled to up to 30 days of sick leave on full pay per year
- Medical certificate required for leave exceeding 3 days

## 3. Maternity Leave
- 90 consecutive calendar days on full pay
- Must be applied for at least 3 months in advance

## 4. Paternity Leave
- 14 days on full pay
- Must be applied for within 7 days of child's birth

## 5. Compassionate Leave
- Up to 5 days on full pay for bereavement or family emergencies

## 6. Study Leave
- Available for approved educational programs
- Maximum 30 days per year

## 7. Compensatory Leave
- Earned through approved overtime work
- Maximum 10 days per year

## 8. Unpaid Leave
- Granted in exceptional circumstances
- Maximum 30 days per year

## Leave Application Process
1. Submit application via the HR System
2. Approval chain: Supervisor → HOD → HR
3. Leave must be approved before commencement
4. Acting officer must be assigned for leave exceeding 5 days
""",
            height=400
        )
        
        if st.button("💾 Save Policy", use_container_width=True):
            try:
                if is_cloud:
                    cursor.execute("""
                        INSERT INTO leave_settings (setting_key, setting_value, description, category)
                        VALUES ('leave_policy', %s, 'Leave policy document', 'policy')
                        ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value
                    """, (policy_content,))
                else:
                    cursor.execute("""
                        INSERT INTO leave_settings (setting_key, setting_value, description, category)
                        VALUES ('leave_policy', ?, 'Leave policy document', 'policy')
                        ON CONFLICT (setting_key) DO UPDATE SET setting_value = excluded.setting_value
                    """, (policy_content,))
                conn.commit()
                st.success("✅ Leave policy saved successfully!")
            except Exception as e:
                st.error(f"Error saving policy: {e}")
    
    conn.close()


# =============================================================
# LEAVE MANAGEMENT ROUTER
# =============================================================

def leave_management_router():
    """Router for leave management sub-pages"""
    
    # Get the menu item from session state
    menu = st.session_state.get('selected_menu', '🏖️ Leave Management')
    
    # Determine which subpage to show
    if menu == "🏖️ Leave Management":
        leave_dashboard()
    elif menu == "    ├─ Dashboard":
        leave_dashboard()
    elif menu == "    ├─ Apply for Leave":
        leave_application()
    elif menu == "    ├─ My Leave":
        st.info("📋 My Leave - View your leave history and status (Coming soon)")
    elif menu == "    ├─ Leave Approvals":
        leave_approvals()
    elif menu == "    ├─ Leave Calendar":
        leave_calendar()
    elif menu == "    ├─ Leave Roster":
        leave_roster()
    elif menu == "    ├─ Leave Balances":
        leave_balances()
    elif menu == "    └─ Reports":
        leave_reports()
    else:
        leave_dashboard()


# =============================================================
# MENU HELPER FUNCTIONS
# =============================================================

def get_leave_menu_items(role):
    """Get leave management menu items based on user role"""
    menu_items = ["🏖️ Leave Management"]
    
    # Sub-menu items
    if role in ["User", "HR", "Admin", "Super Admin"]:
        menu_items.append("    ├─ Dashboard")
        menu_items.append("    ├─ Apply for Leave")
        menu_items.append("    ├─ My Leave")
    
    if role in ["HR", "Admin", "Super Admin"]:
        menu_items.append("    ├─ Leave Approvals")
    
    if role in ["User", "HR", "Admin", "Super Admin"]:
        menu_items.append("    ├─ Leave Calendar")
        menu_items.append("    ├─ Leave Roster")
        menu_items.append("    ├─ Leave Balances")
    
    if role in ["HR", "Admin", "Super Admin"]:
        menu_items.append("    └─ Reports")
    
    return menu_items


def migrate_leave_tables():
    """Run leave management schema migration - call this in init_db()"""
    conn = get_conn()
    if conn is None:
        print("Database connection failed for leave migration")
        return
    
    cursor = conn.cursor()
    is_cloud = st.secrets.get("DATABASE_URL") is not None
    
    # Split schema into individual statements
    statements = [s.strip() for s in LEAVE_SCHEMA_SQL.split(';') if s.strip()]
    
    for stmt in statements:
        try:
            # Convert PostgreSQL syntax to SQLite if needed
            if not is_cloud:
                # Replace SERIAL with INTEGER PRIMARY KEY AUTOINCREMENT
                stmt = stmt.replace('SERIAL PRIMARY KEY', 'INTEGER PRIMARY KEY AUTOINCREMENT')
                # Remove RETURNING clauses
                stmt = stmt.replace(' RETURNING id', '')
                # Replace TRUE/FALSE with 1/0 for SQLite
                stmt = stmt.replace('TRUE', '1').replace('FALSE', '0')
                # Replace ON CONFLICT with simpler handling
                if 'ON CONFLICT' in stmt:
                    stmt = stmt.split('ON CONFLICT')[0] + ';'
            
            cursor.execute(stmt)
        except Exception as e:
            print(f"Error executing: {stmt[:50]}... Error: {e}")
    
    conn.commit()
    conn.close()
    print("✅ Leave management schema migration completed")
