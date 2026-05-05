import streamlit as st
import sqlite3
import pandas as pd
import hashlib
from datetime import datetime
import traceback
import plotly.express as px
import plotly.graph_objects as go
import io
import shutil

# =========================================================
# APP CONFIG
# =========================================================
st.set_page_config(
    page_title="EMBU COUNTY PUBLIC SERVICE BOARD", 
    layout="wide",
    page_icon="🏛️",
    initial_sidebar_state="expanded"
)

# =========================================================
# DB CONNECTION
# =========================================================
def get_conn():
    return sqlite3.connect("ecde.db", check_same_thread=False)

# =========================================================
# SECURITY FUNCTIONS
# =========================================================
def hash_password(password):
    salt = "ecde_secure_salt"
    return hashlib.sha256((salt + password).encode()).hexdigest()

def login_user(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        SELECT * FROM users 
        WHERE username=? AND password=?
    """, (username, hash_password(password)))

    user = c.fetchone()
    conn.close()
    return user

def create_user(username, password, role):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO users (username, password, role, created_at)
            VALUES (?,?,?,?)
        """, (username, hash_password(password), role, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def create_default_admin():
    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        c.execute("""
            INSERT INTO users (username, password, role, created_at)
            VALUES (?,?,?,?)
        """, ("admin", hash_password("admin123"), "Admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    conn.close()

# =========================================================
# DATABASE INIT
# =========================================================
# =========================================================
# DATABASE INIT
# =========================================================
# =========================================================
# DATABASE INIT
# =========================================================
# =========================================================
# DATABASE INIT
# =========================================================
def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Users table
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        created_at TEXT
    )
    """)

    # Staff/Applicants table
    c.execute("""
    CREATE TABLE IF NOT EXISTS staff (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sno INTEGER,
        name TEXT,
        gender TEXT,
        id_number TEXT UNIQUE,
        yob INTEGER,
        ethnicity TEXT,
        disability TEXT,
        contact TEXT,
        kcse TEXT,
        qualifications TEXT,
        subcounty TEXT,
        ward TEXT,
        experience TEXT,
        remarks TEXT,
        created_at TEXT,
        created_by TEXT,
        application_status TEXT DEFAULT 'Pending',
        position_applied TEXT,
        application_date TEXT,
        interview_date TEXT,
        interview_score REAL,
        email TEXT,
        kcse_grade TEXT,
        institution TEXT,
        graduation_year INTEGER,
        professional_body TEXT,
        experience_years INTEGER,
        current_employer TEXT,
        referee1_name TEXT,
        referee1_contact TEXT,
        referee2_name TEXT,
        referee2_contact TEXT,
        documents_ready TEXT,
        declaration_accepted TEXT DEFAULT 'No'
    )
    """)
    
    # NEW: Dropdown options table
    c.execute("""
    CREATE TABLE IF NOT EXISTS dropdown_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        option_value TEXT,
        option_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    # NEW: Advertised positions table
    c.execute("""
    CREATE TABLE IF NOT EXISTS advertised_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_title TEXT,
        position_code TEXT,
        department TEXT,
        employment_type TEXT,
        vacancies INTEGER,
        requirements TEXT,
        responsibilities TEXT,
        salary_range TEXT,
        application_deadline TEXT,
        status TEXT DEFAULT 'Open',
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    # NEW: Recruitment rounds table
    c.execute("""
    CREATE TABLE IF NOT EXISTS recruitment_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_name TEXT,
        start_date TEXT,
        end_date TEXT,
        positions_available TEXT,
        status TEXT DEFAULT 'Upcoming',
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    # NEW: Audit log table
    c.execute("""
    CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user TEXT,
        action TEXT,
        record_id INTEGER,
        details TEXT,
        timestamp TEXT
    )
    """)
    # NEW: Position tracking tables
    c.execute("""
CREATE TABLE IF NOT EXISTS position_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id INTEGER,
    position_title TEXT,
    position_code TEXT,
    applicant_id INTEGER,
    applicant_name TEXT,
    id_number TEXT,
    application_date TEXT,
    status TEXT DEFAULT 'Pending',
    status_updated_date TEXT,
    interview_date TEXT,
    interview_score REAL,
    interview_remarks TEXT,
    shortlist_date TEXT,
    hired_date TEXT,
    rejection_reason TEXT,
    notes TEXT,
    updated_by TEXT,
    FOREIGN KEY (position_id) REFERENCES advertised_positions(id)
)
""")
    # Create indexes
    c.execute("CREATE INDEX IF NOT EXISTS idx_id_number ON staff(id_number)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_name ON staff(name)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_subcounty ON staff(subcounty)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_status ON staff(application_status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_position_applications_position ON position_applications(position_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_position_applications_status ON position_applications(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_position_applications_applicant ON position_applications(applicant_id)")
    
    conn.commit()
    conn.close()
# =========================================================
# ENSURE DATABASE HAS ALL REQUIRED COLUMNS
# =========================================================
def ensure_database_columns():
    """Add missing columns to staff table if they don't exist"""
    conn = get_conn()
    c = conn.cursor()
    
    # Get existing columns
    c.execute("PRAGMA table_info(staff)")
    existing_columns = [col[1] for col in c.fetchall()]
    
    # List of all columns that should exist
    required_columns = {
        'gender': "TEXT",
        'email': "TEXT",
        'position_applied': "TEXT",
        'application_status': "TEXT DEFAULT 'Pending'",
        'subcounty': "TEXT",
        'ward': "TEXT",
        'qualifications': "TEXT",
        'institution': "TEXT",
        'graduation_year': "INTEGER",
        'experience_years': "INTEGER",
        'kcse_grade': "TEXT",
        'interview_score': "REAL",
        'interview_date': "TEXT"
    }
    
    # Add missing columns
    for col_name, col_type in required_columns.items():
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE staff ADD COLUMN {col_name} {col_type}")
                print(f"Added column: {col_name}")
            except Exception as e:
                print(f"Error adding {col_name}: {e}")
    
    conn.commit()
    conn.close()
# =========================================================
# INITIALIZE DROPDOWN OPTIONS
# =========================================================
def init_dropdown_options():
    """Initialize default dropdown options if table is empty"""
    conn = get_conn()
    c = conn.cursor()
    
    # Check if options exist
    c.execute("SELECT COUNT(*) FROM dropdown_options")
    count = c.fetchone()[0]
    
    if count == 0:
        default_options = {
            "Ethnicity": ["Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii", "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu", "Swahili", "Samburu", "Pokot", "Other"],
            "Disability": ["None", "Physical Disability", "Visual Impairment", "Hearing Impairment", "Learning Disability", "Albinism", "Other"],
            "KCSE_Grade": ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"],
            "Qualification": ["ECDE Certificate", "ECDE Diploma", "Bachelor's Degree in ECDE", "Bachelor's Degree in Education", "Postgraduate Diploma in ECDE", "Master's Degree in ECDE", "Master's Degree in Education", "PhD in ECDE", "Other"],
            "SubCounty": ["Central", "East", "North", "South", "West", "Kisumu Central", "Kisumu East", "Kisumu West", "Kisumu North", "Kisumu South", "Nairobi Central", "Nairobi North", "Nairobi South", "Nairobi West", "Nairobi East", "Mombasa Central", "Mombasa North", "Mombasa South", "Mombasa West", "Other"],
            "Ward": ["Ward 1", "Ward 2", "Ward 3", "Ward 4", "Ward 5", "Other"],
            "EmploymentType": ["Permanent", "Contract", "Temporary", "Volunteer", "Intern"],
            "SourceOfInfo": ["Newspaper Advertisement", "County Website", "Social Media", "Word of Mouth", "Job Portal", "Other"]
        }
        
        for category, options in default_options.items():
            for idx, option in enumerate(options):
                c.execute("""
                    INSERT INTO dropdown_options (category, option_value, option_order, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (category, option, idx, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "System"))
        
        conn.commit()
        print("Default dropdown options initialized")
    
    conn.close()

# =========================================================
# MIGRATE DATABASE (For existing databases)
# =========================================================
def migrate_database():
    """Add new columns and tables to existing database if they don't exist"""
    conn = get_conn()
    c = conn.cursor()
    
    # Add new columns to staff table if they don't exist
    new_columns = [
        ("application_status", "TEXT DEFAULT 'Pending'"),
        ("position_applied", "TEXT"),
        ("application_date", "TEXT"),
        ("interview_date", "TEXT"),
        ("interview_score", "REAL"),
        ("email", "TEXT"),
        ("kcse_grade", "TEXT"),
        ("institution", "TEXT"),
        ("graduation_year", "INTEGER"),
        ("professional_body", "TEXT"),
        ("experience_years", "INTEGER"),
        ("current_employer", "TEXT"),
        ("referee1_name", "TEXT"),
        ("referee1_contact", "TEXT"),
        ("referee2_name", "TEXT"),
        ("referee2_contact", "TEXT"),
        ("documents_ready", "TEXT"),
        ("declaration_accepted", "TEXT DEFAULT 'No'")
    ]
    
    for col_name, col_type in new_columns:
        try:
            c.execute(f"ALTER TABLE staff ADD COLUMN {col_name} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    conn.commit()
    conn.close()
# =========================================================
# MIGRATE DATABASE (Add new columns to existing database)
# =========================================================
def migrate_database():
    """Add new columns to existing database if they don't exist"""
    conn = get_conn()
    c = conn.cursor()
    
    # List of columns to add if they don't exist
    new_columns = [
        ("application_status", "TEXT DEFAULT 'Pending'"),
        ("position_applied", "TEXT"),
        ("application_date", "TEXT"),
        ("interview_date", "TEXT"),
        ("interview_score", "REAL"),
        ("email", "TEXT"),
        ("kcse_grade", "TEXT"),
        ("institution", "TEXT"),
        ("graduation_year", "INTEGER"),
        ("professional_body", "TEXT"),
        ("experience_years", "INTEGER"),
        ("current_employer", "TEXT"),
        ("referee1_name", "TEXT"),
        ("referee1_contact", "TEXT"),
        ("referee2_name", "TEXT"),
        ("referee2_contact", "TEXT"),
        ("documents_ready", "TEXT"),
        ("declaration_accepted", "TEXT DEFAULT 'No'")
    ]
    
    # Add each column if it doesn't exist
    for col_name, col_type in new_columns:
        try:
            c.execute(f"ALTER TABLE staff ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    
    # Create indexes after columns are added
    try:
        c.execute("CREATE INDEX IF NOT EXISTS idx_id_number ON staff(id_number)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_name ON staff(name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_subcounty ON staff(subcounty)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_status ON staff(application_status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_position ON staff(position_applied)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_application_date ON staff(application_date)")
    except Exception as e:
        print(f"Index creation error: {e}")
    
    conn.commit()
    conn.close()# =========================================================
# MIGRATE DATABASE (Add new columns if they don't exist)
# =========================================================
def migrate_database():
    """Add new columns to existing database if they don't exist"""
    conn = get_conn()
    c = conn.cursor()
    
    # Check if columns exist and add them if they don't
    try:
        c.execute("ALTER TABLE staff ADD COLUMN application_status TEXT DEFAULT 'Pending'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN position_applied TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN application_date TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN interview_date TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN interview_score REAL")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN email TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN kcse_grade TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN institution TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN graduation_year INTEGER")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN professional_body TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN experience_years INTEGER")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN current_employer TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN referee1_name TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN referee1_contact TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN referee2_name TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN referee2_contact TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN documents_ready TEXT")
    except sqlite3.OperationalError:
        pass
    
    try:
        c.execute("ALTER TABLE staff ADD COLUMN declaration_accepted TEXT DEFAULT 'No'")
    except sqlite3.OperationalError:
        pass
    
    conn.commit()
    conn.close()

# Call this function after init_db() in main()
# =========================================================
# SESSION INIT
# =========================================================
if "user" not in st.session_state:
    st.session_state.user = None
if "edit_staff_id" not in st.session_state:
    st.session_state.edit_staff_id = None

# =========================================================
# PROFESSIONAL UI THEME
# =========================================================
def apply_theme():
    st.markdown("""
    <style>
    /* Main container styling */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 95%;
    }
    
    /* Professional header */
    .main-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2b42 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
    }
    
    /* Card styling */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        border-left: 4px solid #1e3a5f;
        transition: transform 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.12);
    }
    
    .metric-title {
        color: #6c757d;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }
    
    .metric-value {
        color: #1e3a5f;
        font-size: 2rem;
        font-weight: 700;
        margin-bottom: 0.25rem;
    }
    
    .metric-change {
        color: #28a745;
        font-size: 0.8rem;
    }
    
    /* Chart container */
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        margin-bottom: 1.5rem;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1e3a5f 0%, #0f2b42 100%);
        border-right: none;
    }
    
    section[data-testid="stSidebar"] * {
        color: #ffffff;
    }
    
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stRadio label {
        color: rgba(255,255,255,0.9);
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f2b42 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        transition: all 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(30,58,95,0.3);
    }
    
    /* Dataframe styling */
    .stDataFrame {
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 1rem;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        background-color: white;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        color: #6c757d;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #1e3a5f;
        color: white;
    }
    
    /* Footer */
    footer {
        visibility: hidden;
    }
    
    /* Hide streamlit branding */
    #MainMenu {visibility: hidden;}
    
    /* Success message styling */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid;
    }
    
    /* Progress bar styling */
    .stProgress > div > div {
        background-color: #1e3a5f;
    }
    </style>
    """, unsafe_allow_html=True)

# =========================================================
# LOGIN
# =========================================================
def login():
    st.markdown("""
    <style>
    .login-container {
        max-width: 400px;
        margin: 0 auto;
        padding: 2rem;
    }
    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown('<div class="login-container">', unsafe_allow_html=True)
        st.markdown('<div class="login-header">', unsafe_allow_html=True)
        st.image("https://cdn-icons-png.flaticon.com/512/2838/2838912.png", width=100)
        st.title("🏛️ EMBU COUNTY PUBLIC SERVICE BOARD")
        st.markdown("### Welcome Back")
        st.markdown("---")
        st.markdown('</div>', unsafe_allow_html=True)
        
        username = st.text_input("Username", placeholder="Enter your username", key="login_username")
        password = st.text_input("Password", type="password", placeholder="Enter your password", key="login_password")
        
        if st.button("Sign In", use_container_width=True):
            user = login_user(username, password)
            
            if user:
                st.session_state.user = {
                    "id": user[0],
                    "username": user[1],
                    "role": user[3]
                }
                # Log audit
                log_audit(user[1], "LOGIN", user[0], "User logged in")
                st.success("Login successful!")
                st.rerun()
            else:
                st.error("Invalid credentials")
        st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# AUDIT LOG FUNCTION
# =========================================================
def log_audit(user, action, record_id, details):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("""
            INSERT INTO audit_log (user, action, record_id, details, timestamp)
            VALUES (?,?,?,?,?)
        """, (user, action, record_id, details, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

# =========================================================
# SIDEBAR
# =========================================================
def sidebar():
    with st.sidebar:
        st.markdown("### 🏛️ ECPSB Recruitment System")
        st.markdown("---")
        
        # User profile section
        st.markdown(f"""
        <div style='background: rgba(255,255,255,0.1); padding: 1rem; border-radius: 8px; margin-bottom: 1rem;'>
            <div style='font-size: 0.8rem; opacity: 0.8;'>Logged in as</div>
            <div style='font-weight: 600;'>{st.session_state.user['username']}</div>
            <div style='font-size: 0.8rem; margin-top: 0.25rem;'><span style='background: #28a745; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.7rem;'>{st.session_state.user['role']}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        # Quick stats in sidebar
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM staff")
        total_applicants = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM staff WHERE application_status = 'Pending'")
        pending_review = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM staff WHERE application_status = 'Shortlisted'")
        shortlisted = c.fetchone()[0]
        conn.close()
        
        st.markdown(f"""
        <div style='background: rgba(255,255,255,0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.7rem; opacity: 0.8;'>Total Applicants</div>
            <div style='font-size: 1.2rem; font-weight: 700;'>{total_applicants:,}</div>
        </div>
        <div style='background: rgba(255,255,255,0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.7rem; opacity: 0.8;'>Pending Review</div>
            <div style='font-size: 1.2rem; font-weight: 700;'>{pending_review}</div>
        </div>
        <div style='background: rgba(255,255,255,0.1); padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem;'>
            <div style='font-size: 0.7rem; opacity: 0.8;'>Shortlisted</div>
            <div style='font-size: 1.2rem; font-weight: 700;'>{shortlisted}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Main navigation with icons
        menu_options = {
            "📊 Dashboard": "📈 Overview & KPIs",
            "👥 Staff Profile": "👤 View individual staff",
            "📝 Applicant Registration": "📝 Register new applicant",
            "✏️ Edit Application": "✏️ Update applicant information",
            "⭐ Shortlist Management": "⭐ Shortlist candidates manually or via upload",
            "📊 Position Dashboard": "📈 Track applicants by position",
            "📥 Import Excel": "📁 Bulk upload",
            "📋 Records": "📊 View all records",
            "📈 Reports": "📑 Generate reports",
            "📤 Export Center": "💾 Export data",
            "✅ Data Quality": "🔍 Validate data",
            "🔒 Audit Trail": "📜 Track changes",
            "💾 Backup & Restore": "💿 Database tools",
            "⚙️ Settings": "🔧 Configure system",
            "👤 Users": "👥 Manage users"
        }
        
        menu = st.radio(
            "Navigation",
            list(menu_options.keys()),
            format_func=lambda x: f"{x}",
            label_visibility="collapsed"
        )
        
        # Show description
        st.caption(menu_options[menu])
        
        st.markdown("---")
        
        if st.button("🚪 Logout", use_container_width=True):
            log_audit(st.session_state.user['username'], "LOGOUT", 0, "User logged out")
            st.session_state.clear()
            st.rerun()
        
        st.markdown("<div style='font-size: 0.7rem; text-align: center; margin-top: 2rem; opacity: 0.6;'>ECDE Recruitment System v2.0</div>", unsafe_allow_html=True)
    
    return menu

# =========================================================
# DASHBOARD
# =========================================================
def dashboard():
    # Header with timestamp
    st.markdown(f"""
    <div class="main-header">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h1 style="color: white; margin: 0;">Executive Dashboard</h1>
                <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Real-time overview of ECDE staff metrics</p>
            </div>
            <div style="background: rgba(255,255,255,0.1); padding: 0.5rem; border-radius: 8px;">
                <span>📅 Last Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Refresh button
    if st.button("🔄 Refresh Data", key="refresh_dashboard"):
        st.cache_data.clear()
        st.rerun()
    
    # Load data
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM staff", conn)
    conn.close()

    if df.empty:
        st.warning("⚠️ No records available. Please import data using the 'Import Excel' page.")
        return

    # Filters
    st.subheader("🔍 Filter Data")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        subcounty_filter = st.multiselect("Sub-County", df['subcounty'].dropna().unique())
    with col2:
        gender_filter = st.multiselect("Gender", ['Male', 'Female'])
    with col3:
        if 'yob' in df.columns and not df['yob'].isna().all():
            min_year = int(df['yob'].min())
            max_year = int(df['yob'].max())
            year_range = st.slider("Year of Birth", min_year, max_year, (min_year, max_year))
    
    # Apply filters
    filtered_df = df.copy()
    if subcounty_filter:
        filtered_df = filtered_df[filtered_df['subcounty'].isin(subcounty_filter)]
    if gender_filter:
        filtered_df = filtered_df[filtered_df['gender'].isin(gender_filter)]
    if 'year_range' in locals():
        filtered_df = filtered_df[(filtered_df['yob'] >= year_range[0]) & (filtered_df['yob'] <= year_range[1])]
    
    st.info(f"📊 Showing {len(filtered_df):,} of {len(df):,} total records")
    
    # Calculate metrics
    total = len(filtered_df)
    males = len(filtered_df[filtered_df["gender"] == "Male"])
    females = len(filtered_df[filtered_df["gender"] == "Female"])
    total_subcounties = filtered_df["subcounty"].nunique()
    total_wards = filtered_df["ward"].nunique()
    
    # Age calculations
    current_year = datetime.now().year
    filtered_df['age'] = current_year - filtered_df['yob']
    avg_age = filtered_df['age'].mean() if not filtered_df['age'].isna().all() else 0
    
    # Gender ratio
    gender_ratio = (males / females) if females > 0 else 0
    
    # KPI Row
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Staff</div>
            <div class="metric-value">{total:,}</div>
            <div class="metric-change">👥 Active teachers</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Gender Distribution</div>
            <div class="metric-value">♂️ {males:,} | ♀️ {females:,}</div>
            <div class="metric-change">Ratio {gender_ratio:.1f}:1 (M:F)</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Coverage</div>
            <div class="metric-value">{total_subcounties}</div>
            <div class="metric-change">Sub-Counties</div>
            <div style="font-size: 0.8rem; margin-top: 0.5rem;">{total_wards} Wards</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Average Age</div>
            <div class="metric-value">{avg_age:.0f}</div>
            <div class="metric-change">Years old</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Charts Row 1
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.subheader("📍 Staff Distribution by Sub-County")
        subcounty_data = filtered_df["subcounty"].value_counts().head(10)
        
        fig1 = px.bar(
            x=subcounty_data.values,
            y=subcounty_data.index,
            orientation='h',
            title="Top 10 Sub-Counties",
            labels={'x': 'Number of Staff', 'y': 'Sub-County'},
            color=subcounty_data.values,
            color_continuous_scale='Blues'
        )
        fig1.update_layout(
            height=400,
            showlegend=False,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Arial", size=12),
            title_font_size=14
        )
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.subheader("⚧ Gender Distribution")
        
        fig2 = px.pie(
            values=[males, females],
            names=['Male', 'Female'],
            title=f"Total: {total} Staff",
            color_discrete_sequence=['#1e3a5f', '#e74c3c'],
            hole=0.4
        )
        fig2.update_layout(
            height=400,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Arial", size=12),
            title_font_size=14
        )
        fig2.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Charts Row 2
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.subheader("📅 Age Distribution")
        
        fig3 = px.histogram(
            filtered_df,
            x='age',
            nbins=20,
            title="Staff Age Profile",
            labels={'age': 'Age (Years)', 'count': 'Number of Staff'},
            color_discrete_sequence=['#1e3a5f']
        )
        fig3.update_layout(
            height=400,
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(family="Arial", size=12),
            title_font_size=14
        )
        st.plotly_chart(fig3, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        if 'created_at' in filtered_df.columns:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            st.subheader("📈 Staff Growth Trend")
            
            filtered_df['created_at_date'] = pd.to_datetime(filtered_df['created_at']).dt.date
            growth_data = filtered_df.groupby('created_at_date').size().reset_index(name='count')
            growth_data = growth_data.sort_values('created_at_date')
            
            if not growth_data.empty:
                fig4 = px.line(growth_data, x='created_at_date', y='count', 
                              title="Staff Growth Over Time",
                              labels={'count': 'New Staff', 'created_at_date': 'Date'})
                fig4.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white')
                st.plotly_chart(fig4, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

# =========================================================
# STAFF PROFILE
# =========================================================
def staff_profile():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Staff Profile</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">View detailed staff information</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    df = pd.read_sql("SELECT id, name, id_number, subcounty, ward FROM staff ORDER BY name", conn)
    conn.close()
    
    if df.empty:
        st.warning("No staff records found.")
        return
    
    # Staff selector
    staff_names = df['name'].tolist()
    selected_staff = st.selectbox("Select Staff Member", staff_names)
    
    # Get full details
    conn = get_conn()
    staff_data = pd.read_sql(f"SELECT * FROM staff WHERE name = '{selected_staff}'", conn)
    conn.close()
    
    if not staff_data.empty:
        staff = staff_data.iloc[0]
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown(f"""
            <div style="background: white; padding: 1.5rem; border-radius: 12px; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <div style="font-size: 4rem;">👤</div>
                <h3>{staff['name']}</h3>
                <p><strong>Staff ID:</strong> {staff['id']}</p>
                <p><strong>ID Number:</strong> {staff['id_number']}</p>
                <p><strong>Status:</strong> <span style="color: #28a745;">✅ Active</span></p>
                <p><strong>Record Created:</strong><br>{staff['created_at']}</p>
                <p><strong>Created By:</strong> {staff['created_by']}</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style="background: white; padding: 1.5rem; border-radius: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08);">
                <h3>📋 Personal Information</h3>
                <table style="width: 100%;">
            """, unsafe_allow_html=True)
            
            details = {
                "Gender": staff['gender'],
                "Year of Birth": staff['yob'],
                "Age": datetime.now().year - staff['yob'] if staff['yob'] else "N/A",
                "Ethnicity": staff['ethnicity'] or "Not specified",
                "Disability": staff['disability'] or "None",
                "Contact": staff['contact'] or "Not provided",
                "KCSE Year": staff['kcse'] or "Not specified",
                "Qualifications": staff['qualifications'] or "Not specified",
                "Sub-County": staff['subcounty'] or "Not specified",
                "Ward": staff['ward'] or "Not specified",
                "Experience": staff['experience'] or "Not specified",
                "Remarks": staff['remarks'] or "None"
            }
            
            for key, value in details.items():
                st.markdown(f"""
                <tr>
                    <td style='padding: 10px; border-bottom: 1px solid #e0e0e0;'><strong>{key}:</strong></td>
                    <td style='padding: 10px; border-bottom: 1px solid #e0e0e0;'>{value}</td>
                </tr>
                """, unsafe_allow_html=True)
            
            st.markdown("</table></div>", unsafe_allow_html=True)
        
        # Action buttons
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("✏️ Edit Profile", use_container_width=True):
                st.info("Edit feature coming soon")
        with col2:
            if st.button("📄 Generate Report", use_container_width=True):
                st.info("Report generation feature coming soon")
        with col3:
            if st.button("📞 Contact Info", use_container_width=True):
                if staff['contact']:
                    st.success(f"📱 Contact: {staff['contact']}")
                else:
                    st.warning("No contact information available")

# =========================================================
# APPLICANT REGISTRATION (RECRUITMENT)
# =========================================================
def data_entry():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📝 Job Application Form</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">ECDE Teacher Recruitment - Register your application</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs for better organization
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Position", "👤 Personal Information", "📚 Education", "📍 Location", "📎 Documents"])
    
    # Initialize variables
    position_applied = ""
    advertisement_ref = ""
    application_date = datetime.now().strftime("%Y-%m-%d")
    name = ""
    gender = "Male"
    id_number = ""
    yob = 1990
    ethnicity = ""
    disability = ""
    contact = ""
    email = ""
    kcse_year = 0
    kcse_grade = ""
    qualifications = ""
    institution = ""
    graduation_year = 0
    subcounty = ""
    ward = ""
    experience_years = 0
    current_employer = ""
    referee_name = ""
    referee_contact = ""
    remarks = ""
    
    with tab1:
        st.markdown("### 📋 Position Information")
        st.info("Please select the position you are applying for")
        
        col1, col2 = st.columns(2)
        
        with col1:
            position_applied = st.selectbox("🎯 Position Applied For*", [
                "Select Position",
                "ECDE Teacher - Permanent",
                "ECDE Teacher - Contract",
                "ECDE Trainer",
                "ECDE Supervisor",
                "ECDE Coordinator",
                "ECDE Curriculum Developer",
                "ECDE Administrator",
                "Intern ECDE Teacher",
                "Volunteer ECDE Teacher"
            ], help="Select the position you wish to apply for")
            
            advertisement_ref = st.text_input("📢 Advertisement Reference Number", 
                                              placeholder="e.g., ECDE/01/2024",
                                              help="Reference number from the job advertisement")
        
        with col2:
            application_date = st.date_input("📅 Application Date", value=datetime.now(), help="Date of application")
            source_of_info = st.selectbox("📺 How did you hear about this position?", [
                "Select Source",
                "Newspaper Advertisement",
                "County Website",
                "Social Media",
                "Word of Mouth",
                "Job Portal",
                "Other"
            ], help="Where did you learn about this vacancy?")
        
        # Previous application status
        previously_applied = st.radio("Have you applied for any ECDE position with us before?", ["No", "Yes"], horizontal=True)
        if previously_applied == "Yes":
            previous_year = st.number_input("Which year did you previously apply?", min_value=2010, max_value=2025, step=1)
            st.info(f"Note: Previous application from {previous_year} will be considered")
    
    with tab2:
        st.markdown("### 👤 Personal Information")
        col1, col2 = st.columns(2)
        
        with col1:
            name = st.text_input("👨‍🏫 Full Name (as per ID)*", placeholder="Enter your full name", help="Required field")
            gender = st.selectbox("⚧ Gender*", ["Male", "Female", "Other"], help="Required field")
            id_number = st.text_input("🆔 National ID Number*", placeholder="Enter ID number (e.g., 12345678)", help="Required field - Must be unique")
            yob = st.number_input("🎂 Year of Birth", step=1, min_value=1950, max_value=2026, help="Select year of birth")
            
        with col2:
            age = datetime.now().year - yob if yob else 0
            if age > 0:
                if age < 18:
                    st.warning(f"⚠️ Age: {age} years - Below minimum recruitment age (18+)")
                elif age > 55:
                    st.warning(f"⚠️ Age: {age} years - Check if within retirement requirements")
                else:
                    st.success(f"✅ Age: {age} years")
            
            ethnicity = st.selectbox("🌍 Ethnicity (Optional)", [
                "Select Ethnicity",
                "Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii",
                "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu",
                "Swahili", "Samburu", "Pokot", "Other"
            ], help="Optional - for diversity reporting")
            
            disability = st.selectbox("♿ Disability Status", [
                "None",
                "Physical Disability",
                "Visual Impairment",
                "Hearing Impairment",
                "Learning Disability",
                "Albinism",
                "Other"
            ], help="Select if applicable - for equal opportunity employment")
    
    with tab3:
        st.markdown("### 📚 Education & Professional Qualifications")
        
        # KCSE Results
        st.markdown("#### 📖 KCSE Results")
        col1, col2 = st.columns(2)
        with col1:
            kcse_year = st.number_input("KCSE Year", min_value=2000, max_value=2026, step=1, help="Year of KCSE completion")
        with col2:
            kcse_grade = st.selectbox("KCSE Mean Grade", [
                "Select Grade",
                "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"
            ], help="Overall KCSE mean grade")
        
        # Highest Qualification
        st.markdown("#### 🎓 Highest Academic Qualification")
        col1, col2 = st.columns(2)
        with col1:
            qualifications = st.selectbox("Qualification Level", [
                "Select Qualification",
                "ECDE Certificate",
                "ECDE Diploma",
                "Bachelor's Degree in ECDE",
                "Bachelor's Degree in Education (Early Childhood)",
                "Postgraduate Diploma in ECDE",
                "Master's Degree in ECDE",
                "Master's Degree in Education",
                "PhD in ECDE",
                "Other"
            ], help="Select your highest qualification")
            
            if qualifications == "Other":
                other_qual = st.text_input("Specify other qualification", placeholder="Enter your qualification")
        
        with col2:
            institution = st.text_input("🏛️ Institution Name", placeholder="e.g., Kenyatta University, Moi University")
            graduation_year = st.number_input("📅 Year of Graduation", min_value=1980, max_value=2026, step=1)
        
        # Professional Certifications
        st.markdown("#### 📜 Professional Certifications")
        professional_body = st.text_input("Professional Body Registration", 
                                         placeholder="e.g., TSC Registration Number",
                                         help="Teachers Service Commission registration number if registered")
        
        additional_certs = st.text_area("Other Certifications & Trainings", 
                                       placeholder="List any additional professional certifications, workshops, or short courses...",
                                       height=100)
    
    with tab4:
        st.markdown("### 📍 Location & Work Experience")
        
        # Current Location
        st.markdown("#### 🏠 Current Residence")
        col1, col2 = st.columns(2)
        with col1:
            subcounty = st.selectbox("🏢 Current Sub-County", [
                "Select Sub-County",
                "Central", "East", "North", "South", "West",
                "Kisumu Central", "Kisumu East", "Kisumu West", "Kisumu North", "Kisumu South",
                "Nairobi Central", "Nairobi North", "Nairobi South", "Nairobi West", "Nairobi East",
                "Mombasa Central", "Mombasa North", "Mombasa South", "Mombasa West",
                "Other"
            ], help="Your current sub-county of residence")
        with col2:
            ward = st.selectbox("🏘️ Current Ward", [
                "Select Ward",
                "Other"
            ], help="Your current ward of residence")
        
        # Contact Information
        st.markdown("#### 📞 Contact Information")
        col1, col2 = st.columns(2)
        with col1:
            contact = st.text_input("📱 Phone Number*", placeholder="07XXXXXXXX", help="Required - Format: 07XXXXXXXX")
        with col2:
            email = st.text_input("📧 Email Address", placeholder="youremail@example.com", help="For official communication")
        
        # Work Experience
        st.markdown("#### 💼 Work Experience")
        col1, col2 = st.columns(2)
        with col1:
            experience_years = st.slider("Years of Teaching Experience", 0, 40, 0, help="Total years of teaching experience")
        with col2:
            current_employer = st.text_input("Current Employer (if any)", placeholder="School/Institution name")
        
        experience_details = st.text_area("Work Experience Details", 
                                         placeholder="Describe your previous teaching positions:\n- School Name\n- Position held\n- Duration\n- Key responsibilities and achievements",
                                         height=150)
        
        # Availability
        earliest_start = st.date_input("📅 Earliest Start Date", help="When can you join if selected?")
    
    with tab5:
        st.markdown("### 📎 Additional Information & References")
        
        # Referees
        st.markdown("#### 👥 Professional Referees")
        st.info("Please provide two professional referees who can vouch for your work")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Referee 1**")
            referee1_name = st.text_input("Referee 1 - Full Name", key="ref1_name", placeholder="Full name")
            referee1_title = st.text_input("Referee 1 - Title/Position", key="ref1_title", placeholder="e.g., Head Teacher")
            referee1_contact = st.text_input("Referee 1 - Phone/Email", key="ref1_contact", placeholder="Phone number or email")
        
        with col2:
            st.markdown("**Referee 2**")
            referee2_name = st.text_input("Referee 2 - Full Name", key="ref2_name", placeholder="Full name")
            referee2_title = st.text_input("Referee 2 - Title/Position", key="ref2_title", placeholder="e.g., Education Officer")
            referee2_contact = st.text_input("Referee 2 - Phone/Email", key="ref2_contact", placeholder="Phone number or email")
        
        # Document Checklist
        st.markdown("#### 📋 Document Checklist")
        st.info("Please confirm you have the following documents ready for submission")
        
        col1, col2 = st.columns(2)
        with col1:
            id_doc = st.checkbox("National ID Card/Passport")
            kcse_cert = st.checkbox("KCSE Certificate")
            degree_cert = st.checkbox("Degree/Diploma Certificate")
            tsc_cert = st.checkbox("TSC Certificate (if registered)")
        
        with col2:
            cv_doc = st.checkbox("Curriculum Vitae (CV)")
            recommendation = st.checkbox("Recommendation Letters")
            police_cert = st.checkbox("Police Clearance Certificate")
            other_docs = st.checkbox("Other Supporting Documents")
        
        # Declaration
        st.markdown("#### ✍️ Declaration")
        declaration = st.checkbox("I declare that all information provided is true and accurate to the best of my knowledge. I understand that any false information may lead to disqualification.")
        
        remarks = st.text_area("Additional Remarks", 
                              placeholder="Any other information you would like to add...",
                              height=80)
    
    # Required fields note
    st.markdown("---")
    st.markdown("""
    <div style="background: #f8f9fa; padding: 0.75rem; border-radius: 8px; margin-bottom: 1rem;">
        <small>⚠️ <strong>Note:</strong> Fields marked with <span style="color: red;">*</span> are required</small>
    </div>
    """, unsafe_allow_html=True)
    
    # Submit button
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        submit = st.button("📤 Submit Application", use_container_width=True, type="primary")

    if submit:
        # Validation
        errors = []
        if position_applied == "Select Position":
            errors.append("Please select the position you are applying for")
        if not name:
            errors.append("Full Name is required")
        if not id_number:
            errors.append("ID Number is required")
        if not contact:
            errors.append("Phone Number is required")
        if not declaration:
            errors.append("Please accept the declaration to submit your application")
        
        if errors:
            for error in errors:
                st.error(f"❌ {error}")
        else:
            conn = get_conn()
            c = conn.cursor()
            
            try:
                # Build comprehensive remarks with all application details
                full_remarks = f"""
                === APPLICATION DETAILS ===
                Position: {position_applied}
                Advert Ref: {advertisement_ref}
                Source: {source_of_info}
                Application Date: {application_date}
                
                === EDUCATION ===
                KCSE: {kcse_year} - Grade {kcse_grade}
                Qualification: {qualifications}
                Institution: {institution}
                Graduation: {graduation_year}
                Professional Body: {professional_body}
                
                === EXPERIENCE ===
                Experience: {experience_years} years
                Current Employer: {current_employer}
                Earliest Start: {earliest_start}
                
                === REFERENCES ===
                Referee 1: {referee1_name} ({referee1_title}) - {referee1_contact}
                Referee 2: {referee2_name} ({referee2_title}) - {referee2_contact}
                
                === DOCUMENTS ===
                Documents Ready: ID:{id_doc}, KCSE:{kcse_cert}, Certificate:{degree_cert}, TSC:{tsc_cert}, CV:{cv_doc}
                
                === ADDITIONAL ===
                {remarks}
                """
                
                c.execute("""
                INSERT INTO staff (
                    sno,name,gender,id_number,yob,ethnicity,disability,contact,
                    kcse,qualifications,subcounty,ward,experience,remarks,
                    created_at,created_by
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, (
                    0,  # sno - auto-generated application number
                    name,
                    gender,
                    id_number,
                    yob if yob else 0,
                    ethnicity if ethnicity and ethnicity != "Select Ethnicity" else "",
                    disability if disability and disability != "None" else "",
                    contact,
                    kcse_year if kcse_year else 0,
                    f"{qualifications} from {institution} ({graduation_year}) | KCSE: {kcse_grade}",
                    subcounty if subcounty and subcounty != "Select Sub-County" else "",
                    ward if ward and ward != "Select Ward" else "",
                    f"{experience_years} years - {experience_details}",
                    full_remarks,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.user["username"]
                ))
                
                conn.commit()
                log_audit(st.session_state.user['username'], "APPLICATION_SUBMIT", c.lastrowid, f"Job application: {name} for {position_applied}")
                
                # Success message
                st.balloons()
                st.success(f"""
                ✅ **Application Successfully Submitted!**
                
                **Application Summary:**
                - Name: {name}
                - Position: {position_applied}
                - ID Number: {id_number}
                - Application Date: {application_date}
                
                **Next Steps:**
                1. You will receive a confirmation SMS/Email
                2. Shortlisted candidates will be contacted for interview
                3. Keep your phone accessible for communication
                
                Thank you for applying to the County ECDE Recruitment!
                """)
                
                # Clear form by rerunning
                st.rerun()
                
            except sqlite3.IntegrityError:
                st.error(f"❌ An application with ID Number {id_number} already exists! Please check your ID number.")
            except Exception as e:
                st.error(f"❌ Error submitting application: {str(e)}")
            finally:
                conn.close()
# =========================================================
# APPLICANT REGISTRATION (RECRUITMENT)
# =========================================================
def records():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Staff Records</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">View, search and manage teacher data</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM staff ORDER BY id DESC", conn)
    conn.close()
    
    if df.empty:
        st.warning("No records found. Please add records using Staff Entry or Import Excel.")
        return
    
    # Advanced search section
    with st.expander("🔍 Advanced Search", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            search_name = st.text_input("Search by name", placeholder="Enter name...")
            search_id = st.text_input("Search by ID number", placeholder="Enter ID number...")
        with col2:
            search_subcounty = st.selectbox("Sub-County", ["All"] + sorted(df['subcounty'].dropna().unique().tolist()))
            search_qualification = st.text_input("Search by qualification", placeholder="Enter qualification...")
        with col3:
            search_ward = st.selectbox("Ward", ["All"] + sorted(df['ward'].dropna().unique().tolist()))
            gender_filter = st.selectbox("Gender", ["All", "Male", "Female"])
    
    # Simple search
    st.subheader("🔍 Quick Search")
    search = st.text_input("Search by Name or ID", placeholder="Type name or ID number...")
    
    # Apply filters
    filtered_df = df.copy()
    
    if search:
        filtered_df = filtered_df[
            filtered_df["name"].str.contains(search, case=False, na=False) |
            filtered_df["id_number"].str.contains(search, na=False)
        ]
    
    if 'search_name' in locals() and search_name:
        filtered_df = filtered_df[filtered_df["name"].str.contains(search_name, case=False, na=False)]
    
    if 'search_id' in locals() and search_id:
        filtered_df = filtered_df[filtered_df["id_number"].str.contains(search_id, na=False)]
    
    if 'search_subcounty' in locals() and search_subcounty != "All":
        filtered_df = filtered_df[filtered_df["subcounty"] == search_subcounty]
    
    if 'search_ward' in locals() and search_ward != "All":
        filtered_df = filtered_df[filtered_df["ward"] == search_ward]
    
    if 'gender_filter' in locals() and gender_filter != "All":
        filtered_df = filtered_df[filtered_df["gender"] == gender_filter]
    
    if 'search_qualification' in locals() and search_qualification:
        filtered_df = filtered_df[filtered_df["qualifications"].str.contains(search_qualification, case=False, na=False)]
    
    st.markdown(f"### 📊 Results: {len(filtered_df):,} records found")
    
    # Pagination
    page_size = st.selectbox("Records per page", [10, 25, 50, 100, 200])
    total_pages = (len(filtered_df) + page_size - 1) // page_size
    page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1)
    
    start_idx = (page_number - 1) * page_size
    end_idx = start_idx + page_size
    page_df = filtered_df.iloc[start_idx:end_idx]
    
    st.dataframe(page_df, use_container_width=True, height=400)
    st.caption(f"Page {page_number} of {total_pages}")
    
    # Export filtered data
    if not filtered_df.empty:
        csv = filtered_df.to_csv(index=False).encode('utf-8')
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                "📥 Download Filtered Data (CSV)",
                csv,
                f"staff_records_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                use_container_width=True
            )
    
    # Admin-only delete functionality
    if st.session_state.user["role"] == "Admin":
        st.markdown("---")
        st.warning("⚠️ Admin Actions - Use with caution!")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🗑️ Delete All Records", use_container_width=True):
                confirm = st.checkbox("Confirm: I understand this will delete ALL records permanently")
                if confirm:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("DELETE FROM staff")
                    conn.commit()
                    conn.close()
                    log_audit(st.session_state.user['username'], "DELETE_ALL", 0, "Deleted all staff records")
                    st.success("All records deleted successfully!")
                    st.rerun()
                else:
                    st.warning("Please confirm to delete all records")
        
        with col2:
            record_id = st.number_input("Delete specific record by ID", min_value=1, step=1)
            if st.button("Delete Record", use_container_width=True):
                conn = get_conn()
                c = conn.cursor()
                c.execute("SELECT name FROM staff WHERE id = ?", (record_id,))
                staff_name = c.fetchone()
                if staff_name:
                    c.execute("DELETE FROM staff WHERE id = ?", (record_id,))
                    conn.commit()
                    log_audit(st.session_state.user['username'], "DELETE", record_id, f"Deleted staff: {staff_name[0]}")
                    st.success(f"Record {record_id} deleted!")
                    st.rerun()
                else:
                    st.error(f"Record {record_id} not found")
                conn.close()
# =========================================================
# EDIT APPLICANT RECORD (RECRUITMENT SYSTEM)
# =========================================================
def edit_applicant():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">✏️ Edit Application</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Update applicant information and recruitment status</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Get all applicants for selection
    conn = get_conn()
    applicants_df = pd.read_sql("SELECT id, name, id_number, position_applied, application_status FROM staff ORDER BY id DESC", conn)
    conn.close()
    
    if applicants_df.empty:
        st.warning("No applicants found to edit.")
        return
    
    # Applicant selector
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_applicant = st.selectbox(
            "Select Applicant to Edit",
            applicants_df['id'].tolist(),
            format_func=lambda x: f"{x} - {applicants_df[applicants_df['id']==x]['name'].iloc[0]} ({applicants_df[applicants_df['id']==x]['position_applied'].iloc[0]})"
        )
    
    if selected_applicant:
        # Load full applicant data
        conn = get_conn()
        applicant = pd.read_sql(f"SELECT * FROM staff WHERE id = {selected_applicant}", conn)
        conn.close()
        
        if not applicant.empty:
            app = applicant.iloc[0]
            
            # Show current status banner
            status_colors = {
                "Pending": "🟡",
                "Shortlisted": "🟢",
                "Interview Scheduled": "🔵",
                "Interviewed": "🟣",
                "Recommended": "🟠",
                "Hired": "✅",
                "Rejected": "❌",
                "On Hold": "⏸️"
            }
            status_icon = status_colors.get(app['application_status'], "📋")
            st.info(f"{status_icon} **Current Status:** {app['application_status']} | **Position:** {app['position_applied']} | **Application Date:** {app['application_date']}")
            
            # Edit form tabs
            tab1, tab2, tab3, tab4, tab5 = st.tabs(["📋 Position & Status", "👤 Personal Information", "📚 Education", "📍 Location & Experience", "📎 Additional Info"])
            
            with tab1:
                st.markdown("### 📋 Application Details")
                col1, col2 = st.columns(2)
                
                with col1:
                    position_applied = st.selectbox("Position Applied For", [
                        "ECDE Teacher - Permanent",
                        "ECDE Teacher - Contract",
                        "ECDE Trainer",
                        "ECDE Supervisor",
                        "ECDE Coordinator",
                        "ECDE Curriculum Developer",
                        "ECDE Administrator",
                        "Intern ECDE Teacher",
                        "Volunteer ECDE Teacher"
                    ], index=0 if app['position_applied'] is None else [
                        "ECDE Teacher - Permanent", "ECDE Teacher - Contract", "ECDE Trainer",
                        "ECDE Supervisor", "ECDE Coordinator", "ECDE Curriculum Developer",
                        "ECDE Administrator", "Intern ECDE Teacher", "Volunteer ECDE Teacher"
                    ].index(app['position_applied']) if app['position_applied'] in [
                        "ECDE Teacher - Permanent", "ECDE Teacher - Contract", "ECDE Trainer",
                        "ECDE Supervisor", "ECDE Coordinator", "ECDE Curriculum Developer",
                        "ECDE Administrator", "Intern ECDE Teacher", "Volunteer ECDE Teacher"
                    ] else 0)
                    
                    application_status = st.selectbox("Application Status", [
                        "Pending", "Shortlisted", "Interview Scheduled", "Interviewed", 
                        "Recommended", "Hired", "Rejected", "On Hold"
                    ], index=["Pending", "Shortlisted", "Interview Scheduled", "Interviewed", "Recommended", "Hired", "Rejected", "On Hold"].index(app['application_status']) if app['application_status'] in ["Pending", "Shortlisted", "Interview Scheduled", "Interviewed", "Recommended", "Hired", "Rejected", "On Hold"] else 0)
                
                with col2:
                    interview_date = st.date_input(
                        "Interview Date",
                        value=datetime.strptime(app['interview_date'], "%Y-%m-%d") if app['interview_date'] and app['interview_date'] != "None" else datetime.now()
                    )
                    interview_score = st.number_input("Interview Score (0-100)", min_value=0.0, max_value=100.0, value=float(app['interview_score']) if app['interview_score'] else 0.0, step=5.0)
                
                # Remarks field
                remarks = st.text_area("Recruitment Remarks/Notes", value=app['remarks'] if app['remarks'] else "", height=100)
            
            with tab2:
                st.markdown("### 👤 Personal Information")
                col1, col2 = st.columns(2)
                
                with col1:
                    name = st.text_input("Full Name", value=app['name'] if app['name'] else "")
                    gender = st.selectbox("Gender", ["Male", "Female", "Other"], index=["Male", "Female", "Other"].index(app['gender']) if app['gender'] in ["Male", "Female", "Other"] else 0)
                    id_number = st.text_input("ID Number", value=app['id_number'] if app['id_number'] else "")
                    yob = st.number_input("Year of Birth", min_value=1950, max_value=2026, value=int(app['yob']) if app['yob'] else 1990)
                
                with col2:
                    age = datetime.now().year - yob if yob else 0
                    st.info(f"📊 Age: {age} years")
                    ethnicity = st.selectbox("Ethnicity", [
                        "Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii",
                        "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu",
                        "Swahili", "Samburu", "Pokot", "Other"
                    ], index=0 if app['ethnicity'] is None else [
                        "Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii",
                        "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu",
                        "Swahili", "Samburu", "Pokot", "Other"
                    ].index(app['ethnicity']) if app['ethnicity'] in [
                        "Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii",
                        "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu",
                        "Swahili", "Samburu", "Pokot", "Other"
                    ] else 0)
                    
                    disability = st.selectbox("Disability Status", [
                        "None", "Physical Disability", "Visual Impairment", 
                        "Hearing Impairment", "Learning Disability", "Albinism", "Other"
                    ], index=0 if app['disability'] is None else [
                        "None", "Physical Disability", "Visual Impairment", 
                        "Hearing Impairment", "Learning Disability", "Albinism", "Other"
                    ].index(app['disability']) if app['disability'] in [
                        "None", "Physical Disability", "Visual Impairment", 
                        "Hearing Impairment", "Learning Disability", "Albinism", "Other"
                    ] else 0)
            
            with tab3:
                st.markdown("### 📚 Education & Qualifications")
                
                col1, col2 = st.columns(2)
                with col1:
                    kcse_year = st.number_input("KCSE Year", min_value=2000, max_value=2026, value=int(app['kcse']) if app['kcse'] and str(app['kcse']).isdigit() else 2010)
                    kcse_grade = st.selectbox("KCSE Mean Grade", [
                        "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"
                    ], index=0 if app['kcse_grade'] is None else [
                        "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"
                    ].index(app['kcse_grade']) if app['kcse_grade'] in [
                        "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"
                    ] else 0)
                
                with col2:
                    qualifications = st.selectbox("Highest Qualification", [
                        "ECDE Certificate", "ECDE Diploma", "Bachelor's Degree in ECDE",
                        "Bachelor's Degree in Education", "Postgraduate Diploma in ECDE",
                        "Master's Degree in ECDE", "Master's Degree in Education",
                        "PhD in ECDE", "Other"
                    ], index=0 if app['qualifications'] is None else [
                        "ECDE Certificate", "ECDE Diploma", "Bachelor's Degree in ECDE",
                        "Bachelor's Degree in Education", "Postgraduate Diploma in ECDE",
                        "Master's Degree in ECDE", "Master's Degree in Education",
                        "PhD in ECDE", "Other"
                    ].index(app['qualifications']) if app['qualifications'] in [
                        "ECDE Certificate", "ECDE Diploma", "Bachelor's Degree in ECDE",
                        "Bachelor's Degree in Education", "Postgraduate Diploma in ECDE",
                        "Master's Degree in ECDE", "Master's Degree in Education",
                        "PhD in ECDE", "Other"
                    ] else 0)
                
                institution = st.text_input("Institution Name", value=app['institution'] if app['institution'] else "")
                graduation_year = st.number_input("Graduation Year", min_value=1980, max_value=2026, value=int(app['graduation_year']) if app['graduation_year'] else 2020)
                professional_body = st.text_input("Professional Body Registration (TSC Number)", value=app['professional_body'] if app['professional_body'] else "")
            
            with tab4:
                st.markdown("### 📍 Location & Work Experience")
                
                col1, col2 = st.columns(2)
                with col1:
                    contact = st.text_input("Phone Number", value=app['contact'] if app['contact'] else "")
                    email = st.text_input("Email Address", value=app['email'] if app['email'] else "")
                    subcounty = st.text_input("Current Sub-County", value=app['subcounty'] if app['subcounty'] else "")
                    ward = st.text_input("Current Ward", value=app['ward'] if app['ward'] else "")
                
                with col2:
                    experience_years = st.number_input("Years of Experience", min_value=0, max_value=40, value=int(app['experience_years']) if app['experience_years'] else 0)
                    current_employer = st.text_input("Current Employer", value=app['current_employer'] if app['current_employer'] else "")
                    experience_details = st.text_area("Experience Details", value=app['experience'] if app['experience'] else "", height=100)
            
            with tab5:
                st.markdown("### 📎 Additional Information")
                
                st.markdown("#### 👥 Referees")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Referee 1**")
                    referee1_name = st.text_input("Referee 1 Name", value=app['referee1_name'] if app['referee1_name'] else "", key="ref1_name")
                    referee1_contact = st.text_input("Referee 1 Contact", value=app['referee1_contact'] if app['referee1_contact'] else "", key="ref1_contact")
                
                with col2:
                    st.markdown("**Referee 2**")
                    referee2_name = st.text_input("Referee 2 Name", value=app['referee2_name'] if app['referee2_name'] else "", key="ref2_name")
                    referee2_contact = st.text_input("Referee 2 Contact", value=app['referee2_contact'] if app['referee2_contact'] else "", key="ref2_contact")
                
                # Save button
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    save_button = st.button("💾 Save Changes", use_container_width=True, type="primary")
            
            # Process save
            if save_button:
                conn = get_conn()
                c = conn.cursor()
                
                try:
                    # Build experience string
                    experience_str = f"{experience_years} years"
                    if experience_details:
                        experience_str += f" - {experience_details}"
                    
                    c.execute("""
                    UPDATE staff SET
                        position_applied = ?,
                        application_status = ?,
                        interview_date = ?,
                        interview_score = ?,
                        remarks = ?,
                        name = ?,
                        gender = ?,
                        id_number = ?,
                        yob = ?,
                        ethnicity = ?,
                        disability = ?,
                        contact = ?,
                        email = ?,
                        kcse = ?,
                        kcse_grade = ?,
                        qualifications = ?,
                        institution = ?,
                        graduation_year = ?,
                        professional_body = ?,
                        subcounty = ?,
                        ward = ?,
                        experience_years = ?,
                        current_employer = ?,
                        experience = ?,
                        referee1_name = ?,
                        referee1_contact = ?,
                        referee2_name = ?,
                        referee2_contact = ?
                    WHERE id = ?
                    """, (
                        position_applied,
                        application_status,
                        interview_date.strftime("%Y-%m-%d"),
                        interview_score,
                        remarks,
                        name,
                        gender,
                        id_number,
                        yob,
                        ethnicity,
                        disability,
                        contact,
                        email,
                        kcse_year,
                        kcse_grade,
                        qualifications,
                        institution,
                        graduation_year,
                        professional_body,
                        subcounty,
                        ward,
                        experience_years,
                        current_employer,
                        experience_str,
                        referee1_name,
                        referee1_contact,
                        referee2_name,
                        referee2_contact,
                        selected_applicant
                    ))
                    
                    conn.commit()
                    log_audit(st.session_state.user['username'], "EDIT_APPLICANT", selected_applicant, f"Updated applicant: {name}")
                    
                    st.success(f"✅ Application for {name} has been updated successfully!")
                    st.balloons()
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error updating record: {str(e)}")
                finally:
                    conn.close()
# =========================================================
# EXPORT CENTER
# =========================================================
def export_center():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Export Center</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Export data in multiple formats with custom options</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM staff", conn)
    conn.close()
    
    if df.empty:
        st.warning("No data available to export.")
        return
    
    st.subheader("📤 Export Options")
    
    export_format = st.radio("Select Export Format", ["Excel (.xlsx)", "CSV", "JSON"])
    
    # Column selection
    st.subheader("Select Columns to Export")
    all_columns = df.columns.tolist()
    selected_columns = st.multiselect("Choose columns", all_columns, default=all_columns)
    
    # Filter options
    st.subheader("Filter Data (Optional)")
    col1, col2 = st.columns(2)
    with col1:
        subcounty_export = st.multiselect("Sub-County", df['subcounty'].dropna().unique())
    with col2:
        gender_export = st.selectbox("Gender", ["All", "Male", "Female"])
    
    # Apply filters
    export_df = df[selected_columns].copy()
    if subcounty_export:
        export_df = export_df[export_df['subcounty'].isin(subcounty_export)]
    if gender_export != "All":
        export_df = export_df[export_df['gender'] == gender_export]
    
    st.info(f"📄 {len(export_df)} records will be exported")
    st.dataframe(export_df.head(), use_container_width=True)
    
    if export_format == "Excel (.xlsx)":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            export_df.to_excel(writer, sheet_name='Staff Data', index=False)
            
            # Add summary sheet
            summary = pd.DataFrame({
                'Metric': ['Total Records', 'Date Exported', 'Exported By', 'Sub-Counties', 'Gender Distribution'],
                'Value': [
                    len(export_df),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    st.session_state.user['username'],
                    export_df['subcounty'].nunique() if 'subcounty' in export_df.columns else 'N/A',
                    f"Male: {len(export_df[export_df['gender']=='Male'])} | Female: {len(export_df[export_df['gender']=='Female'])}" if 'gender' in export_df.columns else 'N/A'
                ]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
        
        st.download_button(
            "📥 Download Excel File",
            output.getvalue(),
            f"ecde_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
    
    elif export_format == "CSV":
        csv = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download CSV File",
            csv,
            f"ecde_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            "text/csv",
            use_container_width=True
        )
    
    elif export_format == "JSON":
        json_str = export_df.to_json(orient='records', indent=2)
        st.download_button(
            "📥 Download JSON File",
            json_str,
            f"ecde_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "application/json",
            use_container_width=True
        )
# =========================================================
# SHORTLIST MANAGEMENT SYSTEM (Manual + Upload)
# =========================================================

def shortlist_management():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">⭐ Shortlist Management</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Shortlist candidates manually or via bulk upload using Name & ID Number</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["📋 Manual Shortlisting", "📤 Bulk Upload Shortlist", "📊 Shortlisted Candidates"])
    
    conn = get_conn()
    
    # Get all applicants
    applicants_df = pd.read_sql("SELECT id, name, id_number, contact, email, qualifications, experience_years, application_status, subcounty FROM staff ORDER BY id DESC", conn)
    
    if applicants_df.empty:
        st.warning("No applicants found. Please import applicants first.")
        return
    
    # ==================== TAB 1: MANUAL SHORTLISTING ====================
    with tab1:
        st.subheader("✏️ Manual Shortlisting")
        st.info("Search and select candidates by Name or ID Number to add to shortlist")
        
        # Search by Name or ID
        col1, col2 = st.columns(2)
        
        with col1:
            search_by = st.radio("Search by", ["Name", "ID Number", "Both"])
        
        with col2:
            if search_by == "Name":
                search_term = st.text_input("Enter Name", placeholder="Type candidate name...")
            elif search_by == "ID Number":
                search_term = st.text_input("Enter ID Number", placeholder="Type ID number...")
            else:
                search_term = st.text_input("Search by Name or ID", placeholder="Type name or ID number...")
        
        # Additional filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_experience = st.number_input("Min Experience (Years)", min_value=0, max_value=30, value=0)
        
        with col2:
            qualification_filter = st.selectbox("Qualification", ["All", "ECDE Certificate", "ECDE Diploma", "Bachelor's Degree", "Master's Degree"])
        
        with col3:
            subcounty_filter = st.selectbox("Sub-County", ["All"] + sorted(applicants_df['subcounty'].dropna().unique().tolist()))
        
        # Filter applicants
        filtered_df = applicants_df.copy()
        
        # Apply search filters
        if search_term:
            if search_by == "Name":
                filtered_df = filtered_df[filtered_df['name'].str.contains(search_term, case=False, na=False)]
            elif search_by == "ID Number":
                filtered_df = filtered_df[filtered_df['id_number'].str.contains(search_term, na=False)]
            else:
                filtered_df = filtered_df[
                    filtered_df['name'].str.contains(search_term, case=False, na=False) |
                    filtered_df['id_number'].str.contains(search_term, na=False)
                ]
        
        # Apply other filters
        if min_experience > 0:
            filtered_df = filtered_df[filtered_df['experience_years'] >= min_experience]
        
        if qualification_filter != "All":
            filtered_df = filtered_df[filtered_df['qualifications'].str.contains(qualification_filter, case=False, na=False)]
        
        if subcounty_filter != "All":
            filtered_df = filtered_df[filtered_df['subcounty'] == subcounty_filter]
        
        # Only show non-shortlisted candidates
        filtered_df = filtered_df[filtered_df['application_status'] != 'Shortlisted']
        filtered_df = filtered_df[filtered_df['application_status'] != 'Hired']
        
        st.markdown(f"**📋 Found {len(filtered_df)} eligible candidates**")
        
        # Display candidates with selection
        if not filtered_df.empty:
            st.markdown("### ✅ Select Candidates to Shortlist")
            st.caption("Check the box next to each candidate you want to shortlist")
            
            # Create selection container
            selected_ids = []
            
            # Display as a table with checkboxes
            for idx, row in filtered_df.iterrows():
                col1, col2, col3, col4, col5, col6, col7 = st.columns([0.5, 2, 1.5, 1.5, 1.5, 1.5, 0.5])
                
                with col1:
                    selected = st.checkbox("", key=f"select_{row['id']}")
                    if selected:
                        selected_ids.append(row['id'])
                
                with col2:
                    st.write(f"**{row['name']}**")
                with col3:
                    st.write(f"🆔 {row['id_number']}")
                with col4:
                    st.write(f"📞 {row['contact']}")
                with col5:
                    st.write(f"⭐ {row['experience_years']} yrs")
                with col6:
                    qual_short = str(row['qualifications'])[:15] + "..." if len(str(row['qualifications'])) > 15 else row['qualifications']
                    st.write(f"🎓 {qual_short}")
                with col7:
                    st.write(f"📍 {row['subcounty'][:10] if row['subcounty'] else 'N/A'}")
            
            # Shortlist button
            if selected_ids:
                st.markdown("---")
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if st.button(f"⭐ Shortlist {len(selected_ids)} Selected Candidate(s)", use_container_width=True, type="primary"):
                        # Get details of selected candidates for confirmation
                        conn_local = get_conn()
                        for app_id in selected_ids:
                            c = conn_local.cursor()
                            c.execute("""
                                UPDATE staff 
                                SET application_status = 'Shortlisted',
                                    remarks = CASE 
                                        WHEN remarks IS NULL THEN 'Shortlisted on ' || datetime('now')
                                        ELSE remarks || ' | Shortlisted on ' || datetime('now')
                                    END
                                WHERE id = ?
                            """, (app_id,))
                            
                            # Also update position_applications table if exists
                            try:
                                c.execute("""
                                    UPDATE position_applications 
                                    SET status = 'Shortlisted', 
                                        status_updated_date = datetime('now')
                                    WHERE applicant_id = ? OR id_number = (SELECT id_number FROM staff WHERE id = ?)
                                """, (app_id, app_id))
                            except:
                                pass
                            
                            # Log the action
                            log_audit(st.session_state.user['username'], "SHORTLIST", app_id, f"Manually shortlisted candidate")
                        
                        conn_local.commit()
                        conn_local.close()
                        
                        st.success(f"✅ {len(selected_ids)} candidate(s) have been shortlisted successfully!")
                        st.balloons()
                        st.rerun()
            else:
                st.info("👆 Select candidates above to shortlist")
        else:
            st.info("No eligible candidates found matching your criteria")
    
    # ==================== TAB 2: BULK UPLOAD SHORTLIST ====================
    with tab2:
        st.subheader("📤 Bulk Upload Shortlist")
        st.info("Upload a file containing Names and/or ID Numbers to shortlist multiple candidates at once")
        
        col1, col2 = st.columns(2)
        
        with col1:
            upload_method = st.radio(
                "Select identifier type",
                ["ID Numbers Only", "Names Only", "Both Name and ID", "ID Numbers from Excel/CSV"]
            )
        
        with col2:
            # Get positions for context
            positions_df = pd.read_sql("SELECT id, position_title, position_code FROM advertised_positions WHERE status = 'Open'", conn)
            if not positions_df.empty:
                selected_position = st.selectbox(
                    "Position (optional context)",
                    ['Not Specified'] + positions_df['id'].tolist(),
                    format_func=lambda x: 'Not Specified' if x == 'Not Specified' else positions_df[positions_df['id']==x]['position_title'].iloc[0]
                )
        
        st.markdown("---")
        
        # Different upload methods
        if upload_method == "ID Numbers Only":
            st.markdown("### Enter ID Numbers (One per line)")
            id_numbers_input = st.text_area(
                "Paste ID Numbers",
                placeholder="12345678\n87654321\n34567890",
                height=150,
                help="Enter one ID number per line"
            )
            
            if st.button("📋 Process ID Numbers", use_container_width=True):
                if id_numbers_input:
                    id_list = [id_num.strip() for id_num in id_numbers_input.split('\n') if id_num.strip()]
                    
                    # Find matching applicants
                    conn_local = get_conn()
                    matched = []
                    not_found = []
                    
                    for id_num in id_list:
                        c = conn_local.cursor()
                        c.execute("SELECT id, name, id_number, contact, application_status FROM staff WHERE id_number = ?", (id_num,))
                        result = c.fetchone()
                        
                        if result:
                            if result[4] != 'Shortlisted':
                                matched.append({
                                    'id': result[0],
                                    'name': result[1],
                                    'id_number': result[2],
                                    'contact': result[3]
                                })
                            else:
                                not_found.append(f"{id_num} (Already shortlisted)")
                        else:
                            not_found.append(id_num)
                    
                    conn_local.close()
                    
                    # Display results
                    if matched:
                        st.success(f"✅ Found {len(matched)} matching applicants")
                        
                        # Show matched candidates
                        st.write("**Candidates to be shortlisted:**")
                        for m in matched:
                            st.write(f"- {m['name']} (ID: {m['id_number']}, Contact: {m['contact']})")
                        
                        # Confirm shortlist
                        if st.button(f"⭐ Shortlist These {len(matched)} Candidates", use_container_width=True, type="primary"):
                            conn_local = get_conn()
                            c = conn_local.cursor()
                            for m in matched:
                                c.execute("""
                                    UPDATE staff 
                                    SET application_status = 'Shortlisted',
                                        remarks = CASE 
                                            WHEN remarks IS NULL THEN 'Shortlisted via bulk upload on ' || datetime('now')
                                            ELSE remarks || ' | Shortlisted via bulk upload on ' || datetime('now')
                                        END
                                    WHERE id = ?
                                """, (m['id'],))
                                log_audit(st.session_state.user['username'], "BULK_SHORTLIST", m['id'], f"Bulk shortlisted via ID number")
                            conn_local.commit()
                            conn_local.close()
                            st.success(f"✅ {len(matched)} candidates shortlisted successfully!")
                            st.balloons()
                            st.rerun()
                    
                    if not_found:
                        st.warning(f"⚠️ {len(not_found)} ID numbers not found or already shortlisted:")
                        for nf in not_found[:10]:
                            st.write(f"- {nf}")
        
        elif upload_method == "Names Only":
            st.markdown("### Enter Names (One per line)")
            st.warning("Note: Using names only may match multiple candidates. Use ID numbers for precision.")
            
            names_input = st.text_area(
                "Paste Full Names",
                placeholder="John Doe\nJane Smith\nPeter Otieno",
                height=150,
                help="Enter one full name per line"
            )
            
            if st.button("🔍 Search by Names", use_container_width=True):
                if names_input:
                    name_list = [name.strip() for name in names_input.split('\n') if name.strip()]
                    
                    conn_local = get_conn()
                    matched = []
                    not_found = []
                    multiple_matches = []
                    
                    for name in name_list:
                        c = conn_local.cursor()
                        c.execute("SELECT id, name, id_number, contact, application_status FROM staff WHERE name LIKE ?", (f"%{name}%",))
                        results = c.fetchall()
                        
                        if len(results) == 1:
                            result = results[0]
                            if result[4] != 'Shortlisted':
                                matched.append({
                                    'id': result[0],
                                    'name': result[1],
                                    'id_number': result[2],
                                    'contact': result[3]
                                })
                            else:
                                not_found.append(f"{name} (Already shortlisted)")
                        elif len(results) > 1:
                            multiple_matches.append(f"{name} - {len(results)} matches found")
                        else:
                            not_found.append(name)
                    
                    conn_local.close()
                    
                    if matched:
                        st.success(f"✅ Found {len(matched)} matching applicants")
                        for m in matched:
                            st.write(f"- {m['name']} (ID: {m['id_number']})")
                        
                        if st.button(f"⭐ Shortlist These {len(matched)} Candidates", use_container_width=True, type="primary"):
                            conn_local = get_conn()
                            c = conn_local.cursor()
                            for m in matched:
                                c.execute("UPDATE staff SET application_status = 'Shortlisted' WHERE id = ?", (m['id'],))
                                log_audit(st.session_state.user['username'], "BULK_SHORTLIST", m['id'], f"Bulk shortlisted via name")
                            conn_local.commit()
                            conn_local.close()
                            st.success(f"✅ {len(matched)} candidates shortlisted!")
                            st.rerun()
                    
                    if multiple_matches:
                        st.warning(f"⚠️ Multiple matches found for:")
                        for mm in multiple_matches:
                            st.write(f"- {mm}")
                    
                    if not_found:
                        st.error(f"❌ {len(not_found)} names not found or already shortlisted")
        
        elif upload_method == "Both Name and ID":
            st.markdown("### Enter Name and ID Number (comma or tab separated)")
            st.info("Format: Name, ID Number (one pair per line)")
            
            pairs_input = st.text_area(
                "Paste Name, ID pairs",
                placeholder="John Doe, 12345678\nJane Smith, 87654321\nPeter Otieno, 34567890",
                height=150,
                help="Enter Name and ID Number separated by comma"
            )
            
            if st.button("🔍 Verify and Shortlist", use_container_width=True):
                if pairs_input:
                    pairs = []
                    for line in pairs_input.split('\n'):
                        if ',' in line:
                            parts = line.split(',')
                            if len(parts) >= 2:
                                name = parts[0].strip()
                                id_num = parts[1].strip()
                                pairs.append({'name': name, 'id_number': id_num})
                    
                    conn_local = get_conn()
                    verified = []
                    mismatches = []
                    
                    for pair in pairs:
                        c = conn_local.cursor()
                        c.execute("SELECT id, name, id_number, contact, application_status FROM staff WHERE id_number = ?", (pair['id_number'],))
                        result = c.fetchone()
                        
                        if result:
                            if result[1].lower() == pair['name'].lower():
                                if result[4] != 'Shortlisted':
                                    verified.append({
                                        'id': result[0],
                                        'name': result[1],
                                        'id_number': result[2],
                                        'contact': result[3]
                                    })
                                else:
                                    mismatches.append(f"{pair['name']} ({pair['id_number']}) - Already shortlisted")
                            else:
                                mismatches.append(f"{pair['name']} - Name mismatch (Found: {result[1]})")
                        else:
                            mismatches.append(f"{pair['name']} ({pair['id_number']}) - Not found")
                    
                    conn_local.close()
                    
                    if verified:
                        st.success(f"✅ Verified {len(verified)} candidates")
                        for v in verified:
                            st.write(f"- {v['name']} (ID: {v['id_number']})")
                        
                        if st.button(f"⭐ Shortlist These {len(verified)} Candidates", use_container_width=True, type="primary"):
                            conn_local = get_conn()
                            c = conn_local.cursor()
                            for v in verified:
                                c.execute("UPDATE staff SET application_status = 'Shortlisted' WHERE id = ?", (v['id'],))
                                log_audit(st.session_state.user['username'], "BULK_SHORTLIST", v['id'], f"Bulk shortlisted with verification")
                            conn_local.commit()
                            conn_local.close()
                            st.success(f"✅ {len(verified)} candidates shortlisted!")
                            st.rerun()
                    
                    if mismatches:
                        st.error(f"❌ Issues found with {len(mismatches)} entries:")
                        for mm in mismatches[:10]:
                            st.write(f"- {mm}")
        
        else:  # ID Numbers from Excel/CSV
            st.markdown("### Upload Excel/CSV File with ID Numbers")
            
            file = st.file_uploader("Upload File", type=["xlsx", "xls", "csv"])
            
            if file:
                try:
                    if file.name.endswith('.csv'):
                        df = pd.read_csv(file)
                    else:
                        df = pd.read_excel(file)
                    
                    st.write("**File Preview:**")
                    st.dataframe(df.head(), use_container_width=True)
                    
                    # Let user select the ID column
                    id_column = st.selectbox("Select column containing ID Numbers", df.columns.tolist())
                    
                    # Optional name column for verification
                    name_column = st.selectbox("Select column containing Names (optional, for verification)", ['None'] + df.columns.tolist())
                    
                    if st.button("Process File", use_container_width=True):
                        id_list = df[id_column].astype(str).str.strip().tolist()
                        id_list = list(dict.fromkeys(id_list))  # Remove duplicates
                        
                        conn_local = get_conn()
                        matched = []
                        not_found = []
                        name_mismatches = []
                        
                        for id_num in id_list:
                            c = conn_local.cursor()
                            c.execute("SELECT id, name, id_number, contact, application_status FROM staff WHERE id_number = ?", (id_num,))
                            result = c.fetchone()
                            
                            if result:
                                # If name column provided, verify name matches
                                if name_column != 'None':
                                    expected_name = str(df[df[id_column] == id_num][name_column].iloc[0])
                                    if result[1].lower() == expected_name.lower():
                                        if result[4] != 'Shortlisted':
                                            matched.append({
                                                'id': result[0],
                                                'name': result[1],
                                                'id_number': result[2],
                                                'contact': result[3]
                                            })
                                        else:
                                            not_found.append(f"{id_num} - Already shortlisted")
                                    else:
                                        name_mismatches.append(f"ID {id_num}: Name mismatch (File: {expected_name}, DB: {result[1]})")
                                else:
                                    if result[4] != 'Shortlisted':
                                        matched.append({
                                            'id': result[0],
                                            'name': result[1],
                                            'id_number': result[2],
                                            'contact': result[3]
                                        })
                                    else:
                                        not_found.append(f"{id_num} - Already shortlisted")
                            else:
                                not_found.append(id_num)
                        
                        conn_local.close()
                        
                        if matched:
                            st.success(f"✅ Found {len(matched)} valid candidates")
                            
                            # Show matched candidates in a table
                            matched_df = pd.DataFrame(matched)
                            st.dataframe(matched_df[['name', 'id_number', 'contact']], use_container_width=True)
                            
                            if st.button(f"⭐ Shortlist These {len(matched)} Candidates", use_container_width=True, type="primary"):
                                conn_local = get_conn()
                                c = conn_local.cursor()
                                for m in matched:
                                    c.execute("""
                                        UPDATE staff 
                                        SET application_status = 'Shortlisted',
                                            remarks = CASE 
                                                WHEN remarks IS NULL THEN 'Shortlisted via file upload on ' || datetime('now')
                                                ELSE remarks || ' | Shortlisted via file upload on ' || datetime('now')
                                            END
                                        WHERE id = ?
                                    """, (m['id'],))
                                    log_audit(st.session_state.user['username'], "FILE_SHORTLIST", m['id'], f"Shortlisted via file upload")
                                conn_local.commit()
                                conn_local.close()
                                st.success(f"✅ {len(matched)} candidates shortlisted successfully!")
                                st.balloons()
                                st.rerun()
                        
                        if name_mismatches:
                            st.warning(f"⚠️ Name mismatches for {len(name_mismatches)} records")
                            for nm in name_mismatches[:5]:
                                st.write(f"- {nm}")
                        
                        if not_found:
                            st.error(f"❌ {len(not_found)} ID numbers not found or already shortlisted:")
                            for nf in not_found[:10]:
                                st.write(f"- {nf}")
                                
                except Exception as e:
                    st.error(f"Error reading file: {str(e)}")
    
    # ==================== TAB 3: VIEW SHORTLISTED CANDIDATES ====================
    with tab3:
        st.subheader("📊 Shortlisted Candidates")
        
        # Get shortlisted candidates
        shortlisted_df = pd.read_sql("""
            SELECT id, name, id_number, contact, email, qualifications, experience_years, 
                   subcounty, created_at, remarks
            FROM staff 
            WHERE application_status = 'Shortlisted' 
            ORDER BY name
        """, conn)
        
        if shortlisted_df.empty:
            st.info("No candidates have been shortlisted yet. Use the tabs above to shortlist candidates.")
        else:
            st.success(f"✅ Total Shortlisted Candidates: {len(shortlisted_df)}")
            
            # Search within shortlisted
            search_shortlist = st.text_input("🔍 Search within shortlisted", placeholder="Search by name or ID...")
            
            if search_shortlist:
                shortlisted_df = shortlisted_df[
                    shortlisted_df['name'].str.contains(search_shortlist, case=False, na=False) |
                    shortlisted_df['id_number'].str.contains(search_shortlist, na=False)
                ]
            
            # Display shortlisted candidates in a clean table
            st.dataframe(
                shortlisted_df[['name', 'id_number', 'contact', 'qualifications', 'experience_years', 'subcounty']],
                use_container_width=True,
                height=400
            )
            
            # Export shortlisted candidates
            csv = shortlisted_df.to_csv(index=False).encode('utf-8')
            col1, col2 = st.columns(2)
            with col1:
                st.download_button(
                    "📥 Download Shortlist (CSV)",
                    csv,
                    f"shortlisted_candidates_{datetime.now().strftime('%Y%m%d')}.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                if st.button("📧 Send Interview Invitations", use_container_width=True):
                    st.info("Email integration coming soon. For now, you can download the contact list above.")
            
            # Option to remove from shortlist
            st.markdown("---")
            st.subheader("❌ Remove from Shortlist")
            
            remove_candidate = st.selectbox(
                "Select candidate to remove",
                shortlisted_df['id'].tolist(),
                format_func=lambda x: f"{shortlisted_df[shortlisted_df['id']==x]['name'].iloc[0]} - {shortlisted_df[shortlisted_df['id']==x]['id_number'].iloc[0]}"
            )
            
            if remove_candidate and st.button("Remove from Shortlist", use_container_width=True):
                conn_local = get_conn()
                c = conn_local.cursor()
                c.execute("UPDATE staff SET application_status = 'Pending' WHERE id = ?", (remove_candidate,))
                conn_local.commit()
                conn_local.close()
                log_audit(st.session_state.user['username'], "REMOVE_SHORTLIST", remove_candidate, "Removed from shortlist")
                st.success("Candidate removed from shortlist")
                st.rerun()
    
    conn.close()


# Helper function to shortlist candidates
def shortlist_candidates(candidate_ids, conn):
    """Helper function to shortlist multiple candidates"""
    c = conn.cursor()
    for candidate_id in candidate_ids:
        c.execute("""
            UPDATE staff 
            SET application_status = 'Shortlisted',
                remarks = CASE 
                    WHEN remarks IS NULL THEN 'Shortlisted on ' || datetime('now')
                    ELSE remarks || ' | Shortlisted on ' || datetime('now')
                END
            WHERE id = ?
        """, (candidate_id,))
        
        # Also update position_applications if exists
        try:
            c.execute("""
                UPDATE position_applications 
                SET status = 'Shortlisted', 
                    status_updated_date = datetime('now')
                WHERE applicant_id = ?
            """, (candidate_id,))
        except:
            pass
        
        log_audit(st.session_state.user['username'], "SHORTLIST", candidate_id, "Candidate shortlisted")
    conn.commit()
# =========================================================
# DATA QUALITY
# =========================================================
def data_quality():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Data Quality Report</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Monitor data quality and completeness</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    df = pd.read_sql("SELECT * FROM staff", conn)
    conn.close()
    
    if df.empty:
        st.warning("No data available.")
        return
    
    st.subheader("📊 Data Completeness Score")
    
    # Calculate completeness for each column
    completeness = {}
    for col in df.columns:
        non_null = df[col].notna().sum()
        non_empty = (df[col] != "").sum() if col in df.select_dtypes(include=['object']).columns else non_null
        completeness[col] = (non_empty / len(df)) * 100
    
    completeness_df = pd.DataFrame({
        'Column': list(completeness.keys()),
        'Completeness (%)': list(completeness.values())
    }).sort_values('Completeness (%)', ascending=False)
    
    fig = px.bar(completeness_df, x='Column', y='Completeness (%)', 
                 title="Data Completeness by Field",
                 color='Completeness (%)',
                 color_continuous_scale='RdYlGn',
                 range_color=[0, 100])
    fig.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white')
    st.plotly_chart(fig, use_container_width=True)
    
    # Data issues
    st.subheader("⚠️ Data Quality Issues")
    
    issues = []
    
    # Check for missing names
    missing_names = df['name'].isna().sum() + (df['name'] == "").sum()
    if missing_names > 0:
        issues.append(f"❌ {missing_names} records missing staff names")
    
    # Check for missing ID numbers
    missing_ids = df['id_number'].isna().sum() + (df['id_number'] == "").sum()
    if missing_ids > 0:
        issues.append(f"❌ {missing_ids} records missing ID numbers")
    
    # Check for duplicate IDs
    duplicate_ids = df[df.duplicated('id_number', keep=False)]['id_number'].nunique()
    if duplicate_ids > 0:
        issues.append(f"⚠️ {duplicate_ids} duplicate ID numbers found")
    
    # Check for invalid years
    current_year = datetime.now().year
    invalid_years = df[(df['yob'] < 1950) | (df['yob'] > current_year)].shape[0]
    if invalid_years > 0:
        issues.append(f"⚠️ {invalid_years} records with invalid year of birth")
    
    # Check for invalid phone numbers
    if 'contact' in df.columns:
        invalid_phones = df[~df['contact'].str.match(r'^07\d{8}$', na=True)].shape[0]
        if invalid_phones > 0:
            issues.append(f"⚠️ {invalid_phones} records with invalid phone numbers (should be 07XXXXXXXX)")
    
    if issues:
        for issue in issues:
            st.warning(issue)
    else:
        st.success("✅ No data quality issues found!")
    
    # Recommendations
    st.subheader("💡 Recommendations")
    col1, col2 = st.columns(2)
    with col1:
        if completeness.get('qualifications', 0) < 80:
            st.info("📚 Consider adding qualification information for staff members")
        if completeness.get('contact', 0) < 80:
            st.info("📞 Consider adding contact information for better communication")
    with col2:
        if completeness.get('subcounty', 0) < 90:
            st.info("📍 Ensure sub-county information is complete for all staff")
        if completeness.get('experience', 0) < 70:
            st.info("💼 Encourage staff to add their experience details")

# =========================================================
# AUDIT TRAIL
# =========================================================
def audit_trail():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Audit Trail</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Track all system activities</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user["role"] != "Admin":
        st.error("⛔ Access Denied. Admin privileges required.")
        return
    
    conn = get_conn()
    try:
        audit_df = pd.read_sql("SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT 500", conn)
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True)
            
            # Filter by user
            users = ['All'] + list(audit_df['user'].unique())
            selected_user = st.selectbox("Filter by User", users)
            if selected_user != "All":
                audit_df = audit_df[audit_df['user'] == selected_user]
                st.dataframe(audit_df, use_container_width=True)
            
            # Export audit log
            csv = audit_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Audit Log", csv, f"audit_log_{datetime.now().strftime('%Y%m%d')}.csv")
        else:
            st.info("No audit records found")
    except Exception as e:
        st.info(f"Audit trail feature - table exists but no records yet")
    finally:
        conn.close()

# =========================================================
# BACKUP & RESTORE
# =========================================================
def backup_restore():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">Backup & Restore</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Database backup and recovery tools</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user["role"] != "Admin":
        st.error("⛔ Access Denied. Admin privileges required.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦 Backup Database")
        st.info("Create a backup of your entire database")
        if st.button("Create Backup", use_container_width=True):
            backup_file = f"backup_ecde_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            shutil.copy("ecde.db", backup_file)
            with open(backup_file, "rb") as f:
                st.download_button("⬇️ Download Backup", f, backup_file, use_container_width=True)
            st.success("Backup created successfully!")
            log_audit(st.session_state.user['username'], "BACKUP", 0, f"Created backup: {backup_file}")
    
    with col2:
        st.subheader("🔄 Restore Database")
        st.warning("⚠️ Restoring will overwrite current data!")
        uploaded_file = st.file_uploader("Choose backup file", type=["db"])
        if uploaded_file and st.button("Restore Database", use_container_width=True):
            confirm = st.checkbox("Confirm: I understand this will overwrite ALL current data")
            if confirm:
                with open("ecde.db", "wb") as f:
                    f.write(uploaded_file.getbuffer())
                log_audit(st.session_state.user['username'], "RESTORE", 0, f"Restored database from backup")
                st.success("Database restored successfully! Please restart the app.")
                st.rerun()
            else:
                st.warning("Please confirm to restore database")

# =========================================================
# SYSTEM SETTINGS
# =========================================================
def system_settings():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">System Settings</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Configure system preferences</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user["role"] != "Admin":
        st.error("⛔ Access Denied. Admin privileges required.")
        return
    
    st.subheader("⚙️ General Settings")
    
    # Items per page
    items_per_page = st.number_input("Items per page in records view", min_value=10, max_value=200, value=50)
    
    # Default dashboard period
    default_period = st.selectbox("Default dashboard period", ["Last 30 days", "Last 90 days", "All time"])
    
    # Notification settings
    st.subheader("🔔 Notification Settings")
    email_notifications = st.checkbox("Enable email notifications")
    if email_notifications:
        admin_email = st.text_input("Admin email address", placeholder="admin@example.com")
    
    # Data retention
    st.subheader("🗄️ Data Retention")
    retention_days = st.number_input("Keep audit logs for (days)", min_value=30, max_value=730, value=365)
    
    if st.button("Save Settings", use_container_width=True):
        st.success("Settings saved successfully!")
        # In a real app, you'd save these to a config file or database
        log_audit(st.session_state.user['username'], "SETTINGS", 0, "Updated system settings")
# =========================================================
# SETTINGS MANAGEMENT SYSTEM
# =========================================================

# Create settings tables in init_db() - ADD THESE TO YOUR EXISTING init_db()
def create_settings_tables():
    """Create additional tables for settings management"""
    conn = get_conn()
    c = conn.cursor()
    
    # Table for dropdown options
    c.execute("""
    CREATE TABLE IF NOT EXISTS dropdown_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        option_value TEXT,
        option_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    # Table for advertised positions
    c.execute("""
    CREATE TABLE IF NOT EXISTS advertised_positions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_title TEXT,
        position_code TEXT,
        department TEXT,
        employment_type TEXT,
        vacancies INTEGER,
        requirements TEXT,
        responsibilities TEXT,
        salary_range TEXT,
        application_deadline TEXT,
        status TEXT DEFAULT 'Open',
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    # Table for recruitment rounds
    c.execute("""
    CREATE TABLE IF NOT EXISTS recruitment_rounds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        round_name TEXT,
        start_date TEXT,
        end_date TEXT,
        positions_available TEXT,
        status TEXT DEFAULT 'Upcoming',
        created_at TEXT,
        created_by TEXT
    )
    """)
    
    conn.commit()
    conn.close()

# Initialize default dropdown options
def init_dropdown_options():
    """Initialize default dropdown options if table is empty"""
    conn = get_conn()
    c = conn.cursor()
    
    # Check if options exist
    c.execute("SELECT COUNT(*) FROM dropdown_options")
    count = c.fetchone()[0]
    
    if count == 0:
        default_options = {
            "Ethnicity": ["Kikuyu", "Luo", "Luhya", "Kalenjin", "Kamba", "Kisii", "Meru", "Mijikenda", "Turkana", "Maasai", "Taita", "Embu", "Swahili", "Samburu", "Pokot", "Other"],
            "Disability": ["None", "Physical Disability", "Visual Impairment", "Hearing Impairment", "Learning Disability", "Albinism", "Other"],
            "KCSE_Grade": ["A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"],
            "Qualification": ["ECDE Certificate", "ECDE Diploma", "Bachelor's Degree in ECDE", "Bachelor's Degree in Education", "Postgraduate Diploma in ECDE", "Master's Degree in ECDE", "Master's Degree in Education", "PhD in ECDE", "Other"],
            "SubCounty": ["Central", "East", "North", "South", "West", "Kisumu Central", "Kisumu East", "Kisumu West", "Kisumu North", "Kisumu South", "Nairobi Central", "Nairobi North", "Nairobi South", "Nairobi West", "Nairobi East", "Mombasa Central", "Mombasa North", "Mombasa South", "Mombasa West", "Other"],
            "Ward": ["Ward 1", "Ward 2", "Ward 3", "Ward 4", "Ward 5", "Other"],
            "EmploymentType": ["Permanent", "Contract", "Temporary", "Volunteer", "Intern"],
            "SourceOfInfo": ["Newspaper Advertisement", "County Website", "Social Media", "Word of Mouth", "Job Portal", "Other"]
        }
        
        for category, options in default_options.items():
            for idx, option in enumerate(options):
                c.execute("""
                    INSERT INTO dropdown_options (category, option_value, option_order, created_at, created_by)
                    VALUES (?, ?, ?, ?, ?)
                """, (category, option, idx, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "System"))
        
        conn.commit()
    
    conn.close()

# =========================================================
# SYSTEM SETTINGS PAGE (COMPLETE WITH STATISTICS)
# =========================================================
def system_settings():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">⚙️ System Settings</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Manage dropdown options, advertised positions, and recruitment settings</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user["role"] != "Admin":
        st.error("⛔ Access Denied. Admin privileges required.")
        return
    
    # Create tabs for different settings
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Dropdown Options", 
        "📢 Advertised Positions", 
        "🔄 Recruitment Rounds",
        "📊 Application Statistics",
        "⚙️ General Settings"
    ])
    
    # ==================== TAB 1: DROPDOWN OPTIONS ====================
    with tab1:
        st.subheader("📋 Manage Dropdown Options")
        st.info("Add, edit, or remove options that appear in dropdown menus throughout the system")
        
        # Select category to manage
        categories = ["Ethnicity", "Disability", "KCSE_Grade", "Qualification", "SubCounty", "Ward", "EmploymentType", "SourceOfInfo"]
        selected_category = st.selectbox("Select Category to Manage", categories)
        
        if selected_category:
            # Display current options
            conn = get_conn()
            try:
                options_df = pd.read_sql(f"SELECT id, option_value, option_order, is_active FROM dropdown_options WHERE category = '{selected_category}' ORDER BY option_order", conn)
                conn.close()
                
                if not options_df.empty:
                    st.write(f"**Current {selected_category} Options:**")
                    
                    # Editable dataframe
                    edited_df = st.data_editor(
                        options_df[['option_value', 'option_order', 'is_active']],
                        use_container_width=True,
                        num_rows="dynamic",
                        key=f"editor_{selected_category}"
                    )
                    
                    # Save changes button
                    if st.button(f"💾 Save {selected_category} Changes", use_container_width=True):
                        conn = get_conn()
                        c = conn.cursor()
                        # Clear existing options
                        c.execute("DELETE FROM dropdown_options WHERE category = ?", (selected_category,))
                        # Insert updated options
                        for idx, row in edited_df.iterrows():
                            if row['option_value'] and row['option_value'] != "":
                                c.execute("""
                                    INSERT INTO dropdown_options (category, option_value, option_order, is_active, created_at, created_by)
                                    VALUES (?, ?, ?, ?, ?, ?)
                                """, (selected_category, row['option_value'], row['option_order'], row['is_active'], 
                                      datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.user['username']))
                        conn.commit()
                        conn.close()
                        st.success(f"{selected_category} options updated successfully!")
                        st.rerun()
                else:
                    st.info(f"No options found for {selected_category}")
                    
            except Exception as e:
                st.error(f"Error loading options: {str(e)}")
                conn.close()
    
    # ==================== TAB 2: ADVERTISED POSITIONS ====================
    with tab2:
        st.subheader("📢 Manage Advertised Positions")
        
        # Form to add new position
        with st.expander("➕ Post New Position", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                position_title = st.text_input("Position Title*", placeholder="e.g., ECDE Teacher")
                position_code = st.text_input("Position Code", placeholder="e.g., ECDE/2024/01")
                department = st.text_input("Department", placeholder="e.g., Early Childhood Education")
                employment_type = st.selectbox("Employment Type", ["Permanent", "Contract", "Temporary", "Part-time", "Internship"])
                vacancies = st.number_input("Number of Vacancies", min_value=1, max_value=100, value=1)
                
            with col2:
                salary_range = st.text_input("Salary Range", placeholder="e.g., KES 30,000 - 50,000")
                application_deadline = st.date_input("Application Deadline")
                status = st.selectbox("Position Status", ["Open", "Closed", "On Hold"])
            
            requirements = st.text_area("Requirements", placeholder="List all requirements for this position...", height=100)
            responsibilities = st.text_area("Responsibilities", placeholder="List key responsibilities...", height=100)
            
            if st.button("📢 Post Position", use_container_width=True):
                if position_title:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO advertised_positions (
                            position_title, position_code, department, employment_type, vacancies,
                            requirements, responsibilities, salary_range, application_deadline, status,
                            created_at, created_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        position_title, position_code, department, employment_type, vacancies,
                        requirements, responsibilities, salary_range, application_deadline.strftime("%Y-%m-%d"),
                        status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.user['username']
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Position '{position_title}' posted successfully!")
                    st.rerun()
                else:
                    st.error("Position Title is required")
        
        # Display existing positions
        st.markdown("---")
        st.write("**Currently Advertised Positions**")
        
        conn = get_conn()
        positions_df = pd.read_sql("SELECT * FROM advertised_positions ORDER BY id DESC", conn)
        conn.close()
        
        if not positions_df.empty:
            for idx, position in positions_df.iterrows():
                with st.expander(f"📌 {position['position_title']} - {position['status']} (Vacancies: {position['vacancies']})"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Position Code:** {position['position_code']}")
                        st.write(f"**Department:** {position['department']}")
                        st.write(f"**Employment Type:** {position['employment_type']}")
                        st.write(f"**Salary Range:** {position['salary_range']}")
                    with col2:
                        st.write(f"**Application Deadline:** {position['application_deadline']}")
                        st.write(f"**Posted By:** {position['created_by']}")
                        st.write(f"**Posted On:** {position['created_at']}")
                    
                    st.write("**Requirements:**")
                    st.write(position['requirements'])
                    st.write("**Responsibilities:**")
                    st.write(position['responsibilities'])
                    
                    # Action buttons
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        new_status = st.selectbox(f"Status", ["Open", "Closed", "On Hold"], key=f"status_{position['id']}", index=["Open", "Closed", "On Hold"].index(position['status']))
                        if st.button(f"Update", key=f"update_{position['id']}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("UPDATE advertised_positions SET status = ? WHERE id = ?", (new_status, position['id']))
                            conn.commit()
                            conn.close()
                            st.success(f"Status updated to {new_status}")
                            st.rerun()
                    with col3:
                        if st.button(f"🗑️ Delete", key=f"delete_{position['id']}"):
                            conn = get_conn()
                            c = conn.cursor()
                            c.execute("DELETE FROM advertised_positions WHERE id = ?", (position['id'],))
                            conn.commit()
                            conn.close()
                            st.warning(f"Position '{position['position_title']}' deleted")
                            st.rerun()
        else:
            st.info("No advertised positions yet. Use the form above to post a position.")
    
    # ==================== TAB 3: RECRUITMENT ROUNDS ====================
    with tab3:
        st.subheader("🔄 Manage Recruitment Rounds")
        
        # Add new recruitment round
        with st.expander("➕ Create New Recruitment Round", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                round_name = st.text_input("Round Name", placeholder="e.g., 2024 ECDE Teacher Recruitment")
                start_date = st.date_input("Start Date")
            with col2:
                end_date = st.date_input("End Date")
                round_status = st.selectbox("Status", ["Upcoming", "Active", "Closed", "Completed"])
            
            if st.button("Create Recruitment Round", use_container_width=True):
                if round_name:
                    conn = get_conn()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO recruitment_rounds (round_name, start_date, end_date, status, created_at, created_by)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        round_name, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"),
                        round_status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.user['username']
                    ))
                    conn.commit()
                    conn.close()
                    st.success(f"Recruitment round '{round_name}' created!")
                    st.rerun()
                else:
                    st.error("Round name is required")
        
        # Display existing rounds
        st.markdown("---")
        st.write("**Recruitment Rounds**")
        
        conn = get_conn()
        rounds_df = pd.read_sql("SELECT * FROM recruitment_rounds ORDER BY id DESC", conn)
        conn.close()
        
        if not rounds_df.empty:
            for idx, round_item in rounds_df.iterrows():
                with st.expander(f"🔄 {round_item['round_name']} - {round_item['status']} ({round_item['start_date']} to {round_item['end_date']})"):
                    st.write(f"**Created By:** {round_item['created_by']}")
                    st.write(f"**Created On:** {round_item['created_at']}")
                    
                    # Update status
                    new_round_status = st.selectbox("Update Round Status", ["Upcoming", "Active", "Closed", "Completed"], key=f"round_status_{round_item['id']}", index=["Upcoming", "Active", "Closed", "Completed"].index(round_item['status']))
                    if st.button(f"Update Round Status", key=f"update_round_{round_item['id']}"):
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("UPDATE recruitment_rounds SET status = ? WHERE id = ?", (new_round_status, round_item['id']))
                        conn.commit()
                        conn.close()
                        st.success(f"Round status updated to {new_round_status}")
                        st.rerun()
                    
                    if st.button(f"🗑️ Delete Round", key=f"delete_round_{round_item['id']}"):
                        conn = get_conn()
                        c = conn.cursor()
                        c.execute("DELETE FROM recruitment_rounds WHERE id = ?", (round_item['id'],))
                        conn.commit()
                        conn.close()
                        st.rerun()
        else:
            st.info("No recruitment rounds created yet.")
    
    # ==================== TAB 4: APPLICATION STATISTICS ====================
    with tab4:
        st.subheader("📊 Application Statistics Dashboard")
        
        conn = get_conn()
        
        # Get all applications
        df = pd.read_sql("SELECT * FROM staff", conn)
        conn.close()
        
        if not df.empty:
            # Top row - Key Metrics
            st.markdown("### Key Metrics")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_apps = len(df)
                st.metric("Total Applications", f"{total_apps:,}", delta="All time")
            
            with col2:
                pending = len(df[df['application_status'] == 'Pending'])
                st.metric("Pending Review", pending, delta=f"{pending/total_apps*100:.0f}%" if total_apps > 0 else "0%")
            
            with col3:
                shortlisted = len(df[df['application_status'] == 'Shortlisted'])
                st.metric("Shortlisted", shortlisted, delta=f"{shortlisted/total_apps*100:.0f}%" if total_apps > 0 else "0%")
            
            with col4:
                hired = len(df[df['application_status'] == 'Hired'])
                st.metric("Hired", hired, delta=f"{hired/total_apps*100:.0f}%" if total_apps > 0 else "0%")
            
            st.markdown("---")
            
            # Status Distribution Chart
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 📊 Applications by Status")
                status_counts = df['application_status'].value_counts()
                fig = px.pie(values=status_counts.values, names=status_counts.index, title="Status Distribution")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 📅 Applications Over Time")
                if 'created_at' in df.columns:
                    df['created_date'] = pd.to_datetime(df['created_at']).dt.date
                    daily_apps = df.groupby('created_date').size().reset_index(name='count')
                    fig = px.line(daily_apps, x='created_date', y='count', title="Daily Applications")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
            
            # Position Analysis
            st.markdown("#### 💼 Applications by Position")
            position_counts = df['position_applied'].value_counts().head(10)
            fig = px.bar(x=position_counts.values, y=position_counts.index, orientation='h', title="Top 10 Positions Applied")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Demographics
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### 👥 Gender Distribution")
                gender_counts = df['gender'].value_counts()
                fig = px.pie(values=gender_counts.values, names=gender_counts.index, title="Gender Ratio")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("#### 🌍 Top 10 Sub-Counties")
                subcounty_counts = df['subcounty'].value_counts().head(10)
                fig = px.bar(x=subcounty_counts.values, y=subcounty_counts.index, orientation='h', title="Applications by Sub-County")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            
            # Qualification Analysis
            st.markdown("#### 🎓 Qualification Levels")
            qual_counts = df['qualifications'].value_counts().head(10)
            fig = px.bar(x=qual_counts.values, y=qual_counts.index, orientation='h', title="Qualifications Distribution")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Export Statistics
            st.markdown("---")
            st.subheader("📥 Export Statistics")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Export Full Statistics Report", use_container_width=True):
                    # Create comprehensive report
                    stats_report = pd.DataFrame({
                        'Metric': ['Total Applications', 'Pending Review', 'Shortlisted', 'Interviewed', 'Recommended', 'Hired', 'Rejected'],
                        'Count': [
                            len(df),
                            len(df[df['application_status'] == 'Pending']),
                            len(df[df['application_status'] == 'Shortlisted']),
                            len(df[df['application_status'] == 'Interviewed']),
                            len(df[df['application_status'] == 'Recommended']),
                            len(df[df['application_status'] == 'Hired']),
                            len(df[df['application_status'] == 'Rejected'])
                        ]
                    })
                    csv = stats_report.to_csv(index=False).encode('utf-8')
                    st.download_button("Download Report", csv, f"recruitment_stats_{datetime.now().strftime('%Y%m%d')}.csv")
        else:
            st.info("No application data available to display statistics.")
    
    # ==================== TAB 5: GENERAL SETTINGS ====================
    with tab5:
        st.subheader("⚙️ General System Settings")
        
        # Load saved settings (from a settings table or config file)
        st.info("Configure system-wide preferences")
        
        # System Preferences
        st.markdown("### 🎨 System Preferences")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Theme selection
            theme = st.selectbox("Dashboard Theme", ["Light", "Dark", "Auto"], help="Select your preferred theme")
            
            # Items per page
            items_per_page = st.number_input("Records Per Page", min_value=10, max_value=200, value=50, step=10)
            
            # Date format
            date_format = st.selectbox("Date Format", ["DD/MM/YYYY", "MM/DD/YYYY", "YYYY-MM-DD"])
        
        with col2:
            # Default dashboard period
            dashboard_period = st.selectbox("Default Dashboard Period", ["Last 7 Days", "Last 30 Days", "Last 90 Days", "All Time"])
            
            # Notification settings
            email_notifications = st.checkbox("Enable Email Notifications", value=True)
            if email_notifications:
                admin_email = st.text_input("Admin Email Address", placeholder="admin@ecde.go.ke")
            
            # Auto-refresh
            auto_refresh = st.checkbox("Auto-refresh Dashboard", value=False)
            if auto_refresh:
                refresh_interval = st.number_input("Refresh Interval (seconds)", min_value=30, max_value=300, value=60)
        
        st.markdown("---")
        
        # Recruitment Settings
        st.markdown("### 📋 Recruitment Settings")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Default application status
            default_status = st.selectbox("Default Application Status", ["Pending", "Received", "Under Review"])
            
            # Application deadline buffer
            deadline_buffer = st.number_input("Days Before Deadline Reminder", min_value=1, max_value=30, value=7)
        
        with col2:
            # Interview score pass mark
            pass_mark = st.number_input("Interview Pass Mark (%)", min_value=50, max_value=90, value=70, step=5)
            
            # Maximum applications per position
            max_applications = st.number_input("Max Applications Per Position", min_value=100, max_value=5000, value=1000, step=100)
        
        st.markdown("---")
        
        # Data Management
        st.markdown("### 🗄️ Data Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Auto-delete old applications
            auto_delete = st.checkbox("Auto-delete Old Applications", value=False)
            if auto_delete:
                retention_days = st.number_input("Retention Period (Days)", min_value=30, max_value=730, value=365)
        
        with col2:
            # Backup settings
            auto_backup = st.checkbox("Auto-backup Database", value=True)
            if auto_backup:
                backup_frequency = st.selectbox("Backup Frequency", ["Daily", "Weekly", "Monthly"])
        
        st.markdown("---")
        
        # Save Settings Button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("💾 Save All Settings", use_container_width=True, type="primary"):
                # Here you would save to a settings table or config file
                st.success("✅ Settings saved successfully!")
                st.balloons()
                
                # Log the change
                log_audit(st.session_state.user['username'], "SETTINGS_UPDATE", 0, "System settings updated")
        
        # System Information
        st.markdown("---")
        st.markdown("### ℹ️ System Information")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("System Version", "2.0.0")
        with col2:
            st.metric("Last Backup", "Not configured")
        with col3:
            conn = get_conn()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM staff")
            total = c.fetchone()[0]
            conn.close()
            st.metric("Database Records", f"{total:,}")
# =========================================================
# REPORTS FUNCTION
# =========================================================
def reports():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📈 Reports & Analytics</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Generate comprehensive recruitment reports</p>
    </div>
    """, unsafe_allow_html=True)
    
    conn = get_conn()
    
    # Check if staff table exists and has data
    try:
        df = pd.read_sql("SELECT * FROM staff", conn)
    except:
        st.warning("Database not properly initialized. Please restart the application.")
        conn.close()
        return
    
    conn.close()
    
    if df.empty:
        st.warning("No data available to generate reports. Please import applicant data first.")
        return
    
    # Report type selector
    report_type = st.selectbox(
        "Select Report Type",
        ["📊 Applicant Summary Report", "📋 Shortlisted Candidates Report", "🎓 Qualifications Analysis", 
         "📍 Geographic Distribution", "📅 Application Timeline", "📑 Complete Export"]
    )
    
    # ==================== APPLICANT SUMMARY REPORT ====================
    if report_type == "📊 Applicant Summary Report":
        st.subheader("Applicant Summary Report")
        
        # Summary statistics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total = len(df)
            st.metric("Total Applicants", total)
        
        with col2:
            shortlisted = len(df[df['application_status'] == 'Shortlisted']) if 'application_status' in df.columns else 0
            st.metric("Shortlisted", shortlisted, delta=f"{shortlisted/total*100:.0f}%" if total > 0 else "0%")
        
        with col3:
            interviewed = len(df[df['application_status'] == 'Interviewed']) if 'application_status' in df.columns else 0
            st.metric("Interviewed", interviewed)
        
        with col4:
            hired = len(df[df['application_status'] == 'Hired']) if 'application_status' in df.columns else 0
            st.metric("Hired", hired)
        
        # Status distribution
        if 'application_status' in df.columns:
            st.subheader("Application Status Distribution")
            status_counts = df['application_status'].value_counts()
            fig = px.pie(values=status_counts.values, names=status_counts.index, title="Applications by Status")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Gender distribution
        if 'gender' in df.columns:
            st.subheader("Gender Distribution")
            col1, col2 = st.columns(2)
            with col1:
                gender_counts = df['gender'].value_counts()
                fig = px.pie(values=gender_counts.values, names=gender_counts.index, title="Gender Ratio")
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.dataframe(gender_counts.reset_index().rename(columns={'index': 'Gender', 'gender': 'Count'}), use_container_width=True)
        
        # Export button
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Full Report (CSV)", csv, f"applicant_report_{datetime.now().strftime('%Y%m%d')}.csv", use_container_width=True)
    
    # ==================== SHORTLISTED CANDIDATES REPORT ====================
    elif report_type == "📋 Shortlisted Candidates Report":
        st.subheader("Shortlisted Candidates Report")
        
        if 'application_status' in df.columns:
            shortlisted_df = df[df['application_status'] == 'Shortlisted']
            
            if shortlisted_df.empty:
                st.info("No shortlisted candidates found.")
            else:
                st.success(f"Total Shortlisted: {len(shortlisted_df)}")
                
                # Display shortlisted candidates
                display_cols = ['name', 'id_number', 'contact', 'qualifications', 'experience_years', 'subcounty']
                available_cols = [col for col in display_cols if col in shortlisted_df.columns]
                st.dataframe(shortlisted_df[available_cols], use_container_width=True)
                
                # Export shortlist
                csv = shortlisted_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download Shortlist (CSV)", csv, f"shortlist_{datetime.now().strftime('%Y%m%d')}.csv", use_container_width=True)
        else:
            st.warning("Application status data not available")
    
    # ==================== QUALIFICATIONS ANALYSIS ====================
    elif report_type == "🎓 Qualifications Analysis":
        st.subheader("Qualifications Analysis")
        
        if 'qualifications' in df.columns:
            qual_counts = df['qualifications'].value_counts().head(15)
            
            col1, col2 = st.columns(2)
            with col1:
                fig = px.bar(x=qual_counts.values, y=qual_counts.index, orientation='h', 
                            title="Top Qualifications", labels={'x': 'Count', 'y': 'Qualification'})
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.dataframe(qual_counts.reset_index().rename(columns={'index': 'Qualification', 'qualifications': 'Count'}), use_container_width=True)
        else:
            st.warning("Qualifications data not available")
    
    # ==================== GEOGRAPHIC DISTRIBUTION ====================
    elif report_type == "📍 Geographic Distribution":
        st.subheader("Geographic Distribution of Applicants")
        
        if 'subcounty' in df.columns:
            subcounty_counts = df['subcounty'].value_counts().head(15)
            
            fig = px.bar(x=subcounty_counts.values, y=subcounty_counts.index, orientation='h',
                        title="Applications by Sub-County", labels={'x': 'Number of Applicants', 'y': 'Sub-County'})
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(subcounty_counts.reset_index().rename(columns={'index': 'Sub-County', 'subcounty': 'Count'}), use_container_width=True)
        else:
            st.warning("Location data not available")
    
    # ==================== APPLICATION TIMELINE ====================
    elif report_type == "📅 Application Timeline":
        st.subheader("Application Timeline")
        
        if 'created_at' in df.columns:
            df['created_date'] = pd.to_datetime(df['created_at']).dt.date
            timeline = df.groupby('created_date').size().reset_index(name='count')
            timeline = timeline.sort_values('created_date')
            
            fig = px.line(timeline, x='created_date', y='count', 
                         title="Applications Over Time", labels={'count': 'Number of Applications', 'created_date': 'Date'})
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
            
            # Cumulative applications
            timeline['cumulative'] = timeline['count'].cumsum()
            fig2 = px.area(timeline, x='created_date', y='cumulative',
                           title="Cumulative Applications", labels={'cumulative': 'Total Applications', 'created_date': 'Date'})
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.warning("Date data not available")
    
    # ==================== COMPLETE EXPORT ====================
    elif report_type == "📑 Complete Export":
        st.subheader("Complete Data Export")
        
        st.info("Export all applicant data in various formats")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Column selection
            all_columns = df.columns.tolist()
            selected_columns = st.multiselect("Select columns to export", all_columns, default=all_columns)
        
        with col2:
            # Format selection
            export_format = st.selectbox("Export format", ["CSV", "Excel", "JSON"])
        
        if selected_columns:
            export_df = df[selected_columns]
            
            if export_format == "CSV":
                csv = export_df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 Download CSV", csv, f"complete_export_{datetime.now().strftime('%Y%m%d')}.csv", use_container_width=True)
            
            elif export_format == "Excel":
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    export_df.to_excel(writer, sheet_name='Applicants', index=False)
                    
                    # Add summary sheet
                    summary = pd.DataFrame({
                        'Metric': ['Total Records', 'Export Date', 'Exported By', 'Columns Exported'],
                        'Value': [len(export_df), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 
                                 st.session_state.user['username'], ', '.join(selected_columns)]
                    })
                    summary.to_excel(writer, sheet_name='Summary', index=False)
                
                st.download_button("📥 Download Excel", output.getvalue(), f"complete_export_{datetime.now().strftime('%Y%m%d')}.xlsx", 
                                  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
            elif export_format == "JSON":
                json_str = export_df.to_json(orient='records', indent=2)
                st.download_button("📥 Download JSON", json_str, f"complete_export_{datetime.now().strftime('%Y%m%d')}.json", use_container_width=True)
# =========================================================
# USER MANAGEMENT
# =========================================================
def users():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">User Management</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Manage system users and permissions</p>
    </div>
    """, unsafe_allow_html=True)
    
    if st.session_state.user["role"] != "Admin":
        st.error("⛔ Access Denied. Admin privileges required.")
        return
    
    # Display existing users
    conn = get_conn()
    users_df = pd.read_sql("SELECT id, username, role, created_at FROM users", conn)
    conn.close()
    
    st.subheader("📋 Existing Users")
    st.dataframe(users_df, use_container_width=True)
    
    st.markdown("---")
    st.subheader("➕ Create New User")
    
    col1, col2 = st.columns(2)
    with col1:
        new_username = st.text_input("Username", placeholder="Choose a username")
        new_password = st.text_input("Password", type="password", placeholder="Choose a password")
    
    with col2:
        new_role = st.selectbox("Role", ["User", "Admin"])
        confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password")
    
    if st.button("👤 Create User", use_container_width=True):
        if not new_username or not new_password:
            st.error("Username and password are required")
        elif new_password != confirm_password:
            st.error("Passwords do not match")
        else:
            if create_user(new_username, new_password, new_role):
                log_audit(st.session_state.user['username'], "CREATE_USER", 0, f"Created user: {new_username}")
                st.success(f"User {new_username} created successfully!")
                st.rerun()
            else:
                st.error(f"Username {new_username} already exists")

# =========================================================
# IMPORT EXCEL WITH FLEXIBLE COLUMN MAPPING
# =========================================================
def import_excel():
    st.markdown("""
    <div class="main-header">
        <h1 style="color: white; margin: 0;">📥 Import Applicant Data</h1>
        <p style="color: rgba(255,255,255,0.8); margin-top: 0.5rem;">Import job applications based on advertised positions</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Step 1: Select the advertised position
    st.subheader("Step 1: Select Advertised Position")
    
    conn = get_conn()
    positions_df = pd.read_sql("SELECT * FROM advertised_positions WHERE status = 'Open' ORDER BY id DESC", conn)
    conn.close()
    
    if positions_df.empty:
        st.warning("⚠️ No open advertised positions found. Please create a position in Settings > Advertised Positions first.")
        
        # Link to settings
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Go to Settings to Create Position", use_container_width=True):
                st.session_state.page = "⚙️ Settings"
                st.rerun()
        with col2:
            # Allow import without position (generic)
            import_without_position = st.checkbox("Import without position (generic)")
            if import_without_position:
                selected_position = None
                st.info("Importing as generic applicants without specific position")
        return
    
    # Position selection
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_position = st.selectbox(
            "Select Position",
            positions_df['id'].tolist(),
            format_func=lambda x: f"{positions_df[positions_df['id']==x]['position_title'].iloc[0]} - {positions_df[positions_df['id']==x]['position_code'].iloc[0]}"
        )
    
    if selected_position:
        selected_position_data = positions_df[positions_df['id'] == selected_position].iloc[0]
        
        with col2:
            st.info(f"""
            **Position Details:**
            - Title: {selected_position_data['position_title']}
            - Code: {selected_position_data['position_code']}
            - Vacancies: {selected_position_data['vacancies']}
            """)
    
    st.markdown("---")
    
    # Step 2: Download Template
    st.subheader("Step 2: Download Excel Template")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("📥 Download the template with the correct column format")
        
        # Create comprehensive template
        template_data = {
            'full_name': ['John Doe', 'Jane Smith', 'Example Name'],
            'id_number': ['12345678', '87654321', '34567890'],
            'phone_number': ['0712345678', '0723456789', '0734567890'],
            'email': ['john@example.com', 'jane@example.com', 'example@email.com'],
            'gender': ['Male', 'Female', 'Male'],
            'year_of_birth': [1990, 1992, 1988],
            'ethnicity': ['Kikuyu', 'Luo', 'Luhya'],
            'disability': ['None', 'None', 'None'],
            'kcse_year': [2008, 2010, 2006],
            'kcse_grade': ['B+', 'A-', 'B'],
            'highest_qualification': ['Diploma in ECDE', 'Degree in ECDE', 'Certificate in ECDE'],
            'institution': ['Kenyatta University', 'Moi University', 'ECDETC'],
            'graduation_year': [2012, 2015, 2010],
            'years_experience': [5, 3, 8],
            'current_employer': ['ABC School', 'XYZ Academy', 'DEF School'],
            'subcounty': ['Nairobi Central', 'Kisumu Central', 'Mombasa Central'],
            'ward': ['Ward A', 'Ward B', 'Ward C'],
            'heard_about': ['Newspaper', 'Social Media', 'County Website'],
            'additional_notes': ['Available immediately', 'Need relocation', 'Has own accommodation']
        }
        
        template_df = pd.DataFrame(template_data)
        csv = template_df.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            "📥 Download Excel Template (CSV)",
            csv,
            "applicant_import_template.csv",
            "text/csv",
            use_container_width=True
        )
    
    with col2:
        st.markdown("""
        **Required Columns in Template:**
        - `full_name` - Applicant's full name
        - `id_number` - National ID number
        - `phone_number` - Contact phone number
        - `email` - Email address
        - `gender` - Male/Female
        - `year_of_birth` - Year of birth
        - `highest_qualification` - ECDE Certificate/Diploma/Degree
        
        **Optional Columns:**
        - ethnicity, disability, kcse_year, kcse_grade
        - institution, graduation_year, years_experience
        - current_employer, subcounty, ward
        - heard_about, additional_notes
        """)
    
    st.markdown("---")
    
    # Step 3: Upload File
    st.subheader("Step 3: Upload Your Data File")
    
    file = st.file_uploader("Choose Excel/CSV File", type=["xlsx", "xls", "csv"])
    
    if file is not None:
        try:
            # Read the file
            if file.name.endswith('.csv'):
                df = pd.read_csv(file)
            else:
                df = pd.read_excel(file)
            
            # Show original column names
            st.subheader("📋 File Structure Detected")
            st.write("**Columns in your file:**", list(df.columns))
            
            # Step 4: Column Mapping
            st.subheader("Step 4: Map Columns to System Fields")
            st.info("Match your file columns to the system fields")
            
            # Define system fields and their possible column name variations
            column_mapping_options = {
                'name': ['name', 'full_name', 'fullname', 'applicant_name', 'candidate_name', 'Name', 'FULL NAME'],
                'id_number': ['id_number', 'idnumber', 'id_no', 'national_id', 'id', 'ID Number', 'ID', 'National ID'],
                'contact': ['contact', 'phone', 'phone_number', 'mobile', 'telephone', 'Phone', 'CONTACT', 'Phone Number'],
                'email': ['email', 'e-mail', 'email_address', 'Email', 'EMAIL'],
                'gender': ['gender', 'sex', 'Gender', 'SEX'],
                'yob': ['yob', 'year_of_birth', 'birth_year', 'dob_year', 'Year of Birth', 'YOB'],
                'ethnicity': ['ethnicity', 'tribe', 'ethnic', 'Ethnicity'],
                'disability': ['disability', 'special_needs', 'Disability'],
                'kcse_year': ['kcse_year', 'kcse', 'kcse_year', 'KCSE Year'],
                'kcse_grade': ['kcse_grade', 'kcse_grade', 'grade', 'KCSE Grade'],
                'qualification': ['qualification', 'qualifications', 'highest_qualification', 'education', 'Qualification'],
                'institution': ['institution', 'school', 'university', 'college', 'Institution'],
                'graduation_year': ['graduation_year', 'grad_year', 'year_graduated', 'Graduation Year'],
                'experience_years': ['experience_years', 'years_experience', 'exp_years', 'experience', 'Years Experience'],
                'current_employer': ['current_employer', 'employer', 'current_workplace', 'Employer'],
                'subcounty': ['subcounty', 'sub_county', 'sub-county', 'location', 'Subcounty'],
                'ward': ['ward', 'Ward', 'sub_location'],
                'heard_about': ['heard_about', 'source', 'how_did_you_hear', 'Source']
            }
            
            # Create mapping interface
            col1, col2 = st.columns(2)
            
            mapping_dict = {}
            
            with col1:
                st.markdown("**Core Fields (Required)**")
                for field in ['name', 'id_number', 'contact']:
                    current_col = st.selectbox(
                        f"Select column for {field.upper()}",
                        ['None'] + list(df.columns),
                        key=f"map_{field}",
                        help=f"Map your file's column to {field}"
                    )
                    if current_col != 'None':
                        mapping_dict[field] = current_col
            
            with col2:
                st.markdown("**Additional Fields (Optional)**")
                for field in ['email', 'gender', 'yob', 'qualification']:
                    current_col = st.selectbox(
                        f"Select column for {field.upper()}",
                        ['None'] + list(df.columns),
                        key=f"map_{field}_opt"
                    )
                    if current_col != 'None':
                        mapping_dict[field] = current_col
            
            # Show advanced mapping in expander
            with st.expander("🔧 Map Additional Fields (Optional)"):
                for field in ['ethnicity', 'disability', 'kcse_year', 'kcse_grade', 'institution', 
                             'graduation_year', 'experience_years', 'current_employer', 'subcounty', 'ward', 'heard_about']:
                    current_col = st.selectbox(
                        f"Map {field.replace('_', ' ').title()}",
                        ['None'] + list(df.columns),
                        key=f"map_{field}_adv"
                    )
                    if current_col != 'None':
                        mapping_dict[field] = current_col
            
            # Check if required fields are mapped
            if 'name' not in mapping_dict or 'id_number' not in mapping_dict or 'contact' not in mapping_dict:
                st.error("❌ Please map the required fields: name, id_number, and contact")
                return
            
            # Create mapped dataframe
            mapped_df = pd.DataFrame()
            for system_field, file_column in mapping_dict.items():
                if file_column in df.columns:
                    mapped_df[system_field] = df[file_column]
                else:
                    mapped_df[system_field] = ""
            
            # Show preview of mapped data
            st.subheader("Step 5: Preview Mapped Data")
            st.write("**First 10 rows after mapping:**")
            st.dataframe(mapped_df.head(10), use_container_width=True)
            
            # Validation settings
            st.subheader("Step 6: Validation Rules (Optional)")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                enable_validation = st.checkbox("Enable validation rules", value=False)
            
            if enable_validation:
                with col1:
                    min_experience = st.number_input("Min Experience (Years)", min_value=0, max_value=20, value=2)
                with col2:
                    min_qualification = st.selectbox("Min Qualification", 
                        ['Any', 'Certificate', 'Diploma', "Bachelor's Degree", "Master's Degree"],
                        index=0)
                with col3:
                    max_age = st.number_input("Max Age", min_value=20, max_value=65, value=45)
            else:
                min_experience = 0
                min_qualification = 'Any'
                max_age = 65
            
            # Import button
            st.markdown("---")
            if st.button("🚀 Import Data", type="primary", use_container_width=True):
                conn = get_conn()
                c = conn.cursor()
                
                inserted = 0
                skipped = 0
                errors = []
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                current_year = datetime.now().year
                
                for idx, row in mapped_df.iterrows():
                    try:
                        name = str(row.get('name', '')).strip()
                        id_number = str(row.get('id_number', '')).strip()
                        contact = str(row.get('contact', '')).strip()
                        
                        # Basic validation
                        if not name or name == 'nan':
                            errors.append(f"Row {idx+2}: Name is empty")
                            skipped += 1
                            continue
                        
                        if not id_number or id_number == 'nan':
                            errors.append(f"Row {idx+2}: ID Number is empty")
                            skipped += 1
                            continue
                        
                        if not contact or contact == 'nan':
                            errors.append(f"Row {idx+2}: Contact is empty")
                            skipped += 1
                            continue
                        
                        # Check for duplicate ID
                        c.execute("SELECT id FROM staff WHERE id_number = ?", (id_number,))
                        if c.fetchone():
                            errors.append(f"Row {idx+2}: ID {id_number} already exists")
                            skipped += 1
                            continue
                        
                        # Optional validation
                        validation_passed = True
                        validation_notes = []
                        
                        if enable_validation:
                            # Experience validation
                            exp_years = row.get('experience_years', 0)
                            try:
                                exp_years = float(exp_years) if exp_years and exp_years != 'nan' else 0
                            except:
                                exp_years = 0
                            
                            if exp_years < min_experience:
                                validation_passed = False
                                validation_notes.append(f"Experience ({exp_years} yrs) below minimum")
                            
                            # Age validation
                            yob = row.get('yob', current_year)
                            try:
                                yob = int(yob) if yob and yob != 'nan' else current_year
                            except:
                                yob = current_year
                            
                            age = current_year - yob
                            if age > max_age:
                                validation_passed = False
                                validation_notes.append(f"Age ({age}) exceeds maximum")
                        
                        # Determine status
                        if enable_validation and not validation_passed:
                            status = 'Rejected'
                            remarks = f"Validation failed: {'; '.join(validation_notes)}"
                            skipped += 1
                        else:
                            status = 'Pending' if not enable_validation else 'Shortlisted'
                            remarks = f"Imported from file. {'All validation passed' if enable_validation else 'No validation applied'}"
                            inserted += 1
                        
                        # Insert into database
                        c.execute("""
                            INSERT INTO staff (
                                name, id_number, contact, email, gender, yob, ethnicity, disability,
                                kcse, qualifications, institution, subcounty, ward, experience,
                                position_applied, application_status, remarks, created_at, created_by,
                                experience_years, kcse_grade, graduation_year
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            name,
                            id_number,
                            contact,
                            row.get('email', ''),
                            row.get('gender', ''),
                            row.get('yob', 0),
                            row.get('ethnicity', ''),
                            row.get('disability', ''),
                            row.get('kcse_year', ''),
                            row.get('qualification', ''),
                            row.get('institution', ''),
                            row.get('subcounty', ''),
                            row.get('ward', ''),
                            row.get('experience_years', 0),
                            selected_position_data['position_title'] if selected_position else 'General',
                            status,
                            remarks,
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            st.session_state.user['username'],
                            row.get('experience_years', 0),
                            row.get('kcse_grade', ''),
                            row.get('graduation_year', 0)
                        ))
                        
                        progress_bar.progress((idx + 1) / len(mapped_df))
                        status_text.text(f"Processing: {idx+1}/{len(mapped_df)} | ✅ Imported: {inserted} | ⚠️ Skipped: {skipped}")
                        
                    except Exception as e:
                        skipped += 1
                        errors.append(f"Row {idx+2}: {str(e)}")
                
                conn.commit()
                conn.close()
                
                # Show results
                st.success("✅ Import Completed!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Records", len(mapped_df))
                with col2:
                    st.metric("Successfully Imported", inserted)
                with col3:
                    st.metric("Skipped/Failed", skipped)
                
                if inserted > 0:
                    st.balloons()
                    st.success(f"🎉 {inserted} applicants successfully imported!")
                
                if errors:
                    with st.expander(f"⚠️ Error Details ({len(errors)} issues - showing first 10)"):
                        for err in errors[:10]:
                            st.write(f"- {err}")
                
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")# =========================================================
# MAIN
# =========================================================
def main():
    apply_theme()
    
    # System initialization
    init_db()
    migrate_database()
    ensure_database_columns()  # ← ADD THIS LINE
    init_dropdown_options()
    create_default_admin()
    
    # Login gate
    if not st.session_state.user:
        login()
        return
    
    # Sidebar navigation
    menu = sidebar()
    
    # Router
    if menu == "📊 Dashboard":
        dashboard()
    elif menu == "👥 Staff Profile":
        staff_profile()
    elif menu == "📝 Applicant Registration":
        data_entry()
    elif menu == "✏️ Edit Application":
        edit_applicant()
    elif menu == "📊 Position Dashboard":
        position_dashboard()
    elif menu == "📥 Import Excel":
        import_excel()
    elif menu == "📋 Records":
        records()
    elif menu == "📈 Reports":
        reports()
    elif menu == "📤 Export Center":
        export_center()
    elif menu == "⭐ Shortlist Management":
        shortlist_management()
    elif menu == "✅ Data Quality":
        data_quality()
    elif menu == "🔒 Audit Trail":
        audit_trail()
    elif menu == "💾 Backup & Restore":
        backup_restore()
    elif menu == "⚙️ Settings":
        system_settings()
    elif menu == "👤 Users":
        users()
# =========================================================
# RUN APP
# =========================================================
if __name__ == "__main__":
    main()