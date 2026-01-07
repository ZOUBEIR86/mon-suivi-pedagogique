import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from passlib.hash import pbkdf2_sha256
from streamlit_option_menu import option_menu
from streamlit_lottie import st_lottie
import requests
import datetime
import time

# --- CONSTANTS & CONFIG ---
DB_FILE = "edtech.db"
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"

st.set_page_config(
    page_title="EdTech Master Tracker",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ADVANCED CSS & STYLING (Glassmorphism) ---
st.markdown("""
    <style>
    /* Global Background */
    .stApp {
        background-image: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Glassmorphism Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.7);
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        backdrop-filter: blur(4px);
        -webkit-backdrop-filter: blur(4px);
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.18);
        padding: 20px;
        margin-bottom: 20px;
        transition: transform 0.2s;
    }
    .glass-card:hover {
        transform: translateY(-5px);
    }

    /* Custom Titles */
    h1, h2, h3 {
        color: #2c3e50;
        font-family: 'Helvetica Neue', sans-serif;
    }
    
    /* Metrics customization */
    .css-1r6slb0 { 
        background-color: transparent !important; 
        box-shadow: none !important;
    }
    
    /* Sidebar customization */
    section[data-testid="stSidebar"] {
        background-color: #2c3e50; 
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE MANAGEMENT (SQLite3) ---

def init_db():
    """Initialize the SQLite database with 3 tables."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # 1. Users Table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
    
    # 2. Progress Table
    c.execute('''CREATE TABLE IF NOT EXISTS progress (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    subject TEXT,
                    chapter_name TEXT,
                    component TEXT, -- cours, td, tp
                    status TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    
    # 3. Audit Trails Table
    c.execute('''CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    action TEXT,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )''')
    
    # Create Default Admin if empty
    c.execute("SELECT count(*) FROM users")
    if c.fetchone()[0] == 0:
        hashed_pw = pbkdf2_sha256.hash(DEFAULT_ADMIN_PASS)
        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                  (DEFAULT_ADMIN_USER, hashed_pw, 'admin'))
        print(f"Default admin created: {DEFAULT_ADMIN_USER} / {DEFAULT_ADMIN_PASS}")
    
    conn.commit()
    conn.close()

def run_query(query, params=(), fetch=True):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    if fetch:
        data = c.fetchall()
        conn.close()
        return data
    else:
        conn.commit()
        conn.close()
        return None

def log_audit(user_id, action, details):
    run_query(
        "INSERT INTO audit_logs (user_id, action, details) VALUES (?, ?, ?)",
        (user_id, action, details),
        fetch=False
    )

# --- AUTHENTICATION ---

def login_user(username, password):
    user = run_query("SELECT id, username, password, role FROM users WHERE username = ?", (username,))
    if user:
        user_id, db_user, db_pass, role = user[0]
        if pbkdf2_sha256.verify(password, db_pass):
            return {"id": user_id, "username": db_user, "role": role}
    return None

def create_user(username, password, role="student"):
    try:
        hashed = pbkdf2_sha256.hash(password)
        run_query("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", 
                  (username, hashed, role), fetch=False)
        return True
    except sqlite3.IntegrityError:
        return False

# --- UTILS & DATA STRUCTURE ---

DEFAULT_SUBJECTS = {
    "Mathématiques": [
        "Algèbre Linéaire", "Analyse Réelle", "Probabilités"
    ],
    "Physique": [
        "Mécanique du Point", "Thermodynamique", "Électromagnétisme"
    ],
    "Informatique": [
        "Python Intro", "Structures de Données", "Algorithmes"
    ]
}

def load_lottieurl(url: str):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

# --- APP VIEWS ---

def view_login():
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.title("🔐 Connexion")
        st.write("Bienvenue sur le tracker pédagogique.")
        
        username = st.text_input("Nom d'utilisateur")
        password = st.text_input("Mot de passe", type="password")
        
        if st.button("Se connecter", use_container_width=True):
            user = login_user(username, password)
            if user:
                st.session_state['user'] = user
                st.success(f"Bienvenue, {user['username']}!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Identifiants incorrects.")
        
        st.info(f"**Admin par défaut** : {DEFAULT_ADMIN_USER} / {DEFAULT_ADMIN_PASS}")
        st.markdown("</div>", unsafe_allow_html=True)

def view_dashboard():
    user = st.session_state['user']
    
    st.markdown(f"# 👋 Bonjour, {user['username']}")
    st.markdown("---")
    
    # 1. KPIs
    # Calculate progress for this user (or all if admin? let's stick to personal focused dashboard)
    # We'll just count 'Fait' (100%) status
    progress_data = run_query("SELECT count(*) FROM progress WHERE user_id = ? AND status = 'Fait'", (user['id'],))
    completed_tasks = progress_data[0][0]
    
    # Total possible actions (Subjects * Chapters * 3)
    total_ops = sum(len(chaps)*3 for chaps in DEFAULT_SUBJECTS.values())
    global_rate = (completed_tasks / total_ops) * 100 if total_ops > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Matières Actives", len(DEFAULT_SUBJECTS))
    col2.metric("Taux d'Achèvement", f"{global_rate:.1f} %")
    col3.metric("Tâches Terminées", completed_tasks)
    
    # 2. Charts
    st.markdown("### 📊 Analyse de la Progression")
    
    c1, c2 = st.columns(2)
    
    with c1:
        # Pull detailed progress for chart
        rows = run_query("SELECT subject, status, count(*) FROM progress WHERE user_id = ? GROUP BY subject, status", (user['id'],))
        if rows:
            df = pd.DataFrame(rows, columns=['Matière', 'Statut', 'Compte'])
            fig = px.sunburst(df, path=['Matière', 'Statut'], values='Compte', color='Statut',
                              color_discrete_map={'Fait':'#00cc96', 'En cours':'#ffa15a', 'Non fait':'#ef553b'})
            fig.update_layout(margin=dict(t=0, l=0, r=0, b=0), paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Aucune donnée de progression pour le moment.")
            
    with c2:
        # Load an animation
        lottie_chart = load_lottieurl("https://assets4.lottiefiles.com/packages/lf20_qp1q7mct.json")
        if lottie_chart:
            st_lottie(lottie_chart, height=300)

    # 3. Recent Activity (Audit for self)
    st.markdown("### 🕒 Activité Récente")
    logs = run_query("SELECT action, details, timestamp FROM audit_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT 5", (user['id'],))
    if logs:
        for action, details, ts in logs:
            st.markdown(f"**{ts}** : {action} - *{details}*")
    else:
        st.caption("Aucune activité récente.")


def view_subjects():
    user = st.session_state['user']
    st.title("📚 Mes Matières")
    
    # Status options
    STATUS_OPTS = ["Non fait", "En cours", "Fait"]
    
    # Iterate over subjects
    for subj, chapters in DEFAULT_SUBJECTS.items():
        with st.container():
            st.markdown(f"<div class='glass-card'><h3>{subj}</h3>", unsafe_allow_html=True)
            
            # Create an expander per chapter
            for chap in chapters:
                with st.expander(f"📖 {chap}"):
                    cols = st.columns(3)
                    components = ["Cours", "TD", "TP"]
                    
                    for idx, comp in enumerate(components):
                        # Fetch current status
                        res = run_query(
                            "SELECT status FROM progress WHERE user_id=? AND subject=? AND chapter_name=? AND component=?", 
                            (user['id'], subj, chap, comp)
                        )
                        current_status = res[0][0] if res else "Non fait"
                        current_idx = STATUS_OPTS.index(current_status) if current_status in STATUS_OPTS else 0
                        
                        # Widget
                        new_status = cols[idx].selectbox(
                            f"{comp}", 
                            STATUS_OPTS, 
                            index=current_idx,
                            key=f"{subj}_{chap}_{comp}"
                        )
                        
                        # Update DB if changed
                        if new_status != current_status:
                            # 1. Upsert into Progress
                            # Check if exists
                            exists = run_query(
                                "SELECT id FROM progress WHERE user_id=? AND subject=? AND chapter_name=? AND component=?",
                                (user['id'], subj, chap, comp)
                            )
                            if exists:
                                run_query(
                                    "UPDATE progress SET status=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                                    (new_status, exists[0][0]), fetch=False
                                )
                            else:
                                run_query(
                                    "INSERT INTO progress (user_id, subject, chapter_name, component, status) VALUES (?,?,?,?,?)",
                                    (user['id'], subj, chap, comp, new_status), fetch=False
                                )
                            
                            # 2. Audit Log
                            log_audit(user['id'], "UPDATE_PROGRESS", f"{subj} > {chap} > {comp} : {new_status}")
                            st.toast(f"Mise à jour enregistrée : {comp} -> {new_status}")
                            time.sleep(0.5)
                            st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


def view_admin():
    st.title("🛠️ Interface Administrateur")
    
    tab1, tab2 = st.tabs(["👥 Gestion Utilisateurs", "📜 Audit Global"])
    
    with tab1:
        st.subheader("Créer un nouvel utilisateur")
        with st.form("create_user"):
            new_user = st.text_input("Nom d'utilisateur")
            new_pass = st.text_input("Mot de passe", type="password")
            role = st.selectbox("Rôle", ["student", "admin"])
            submit = st.form_submit_button("Créer")
            
            if submit:
                if create_user(new_user, new_pass, role):
                    st.success(f"Utilisateur {new_user} créé avec succès !")
                    log_audit(st.session_state['user']['id'], "CREATE_USER", f"Created user {new_user} ({role})")
                else:
                    st.error("Erreur : Ce nom d'utilisateur existe déjà.")
                    
        st.markdown("---")
        st.subheader("Utilisateurs existants")
        users = run_query("SELECT id, username, role, created_at FROM users")
        st.dataframe(pd.DataFrame(users, columns=["ID", "Username", "Role", "Created At"]), use_container_width=True)

    with tab2:
        st.subheader("Journal d'Audit Complet")
        logs = run_query("""
            SELECT audit_logs.timestamp, users.username, audit_logs.action, audit_logs.details 
            FROM audit_logs 
            JOIN users ON audit_logs.user_id = users.id 
            ORDER BY audit_logs.timestamp DESC
        """)
        df_logs = pd.DataFrame(logs, columns=["Date/Heure", "Utilisateur", "Action", "Détails"])
        st.dataframe(df_logs, use_container_width=True)

# --- MAIN CONTROLLER ---

def main():
    init_db()
    
    if 'user' not in st.session_state:
        view_login()
    else:
        # Sidebar with OptionMenu
        with st.sidebar:
            st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
            st.markdown(f"### {st.session_state['user']['username']}")
            
            menu_options = ["Dashboard", "Matières"]
            icons = ["speedometer2", "journal-bookmark"]
            
            if st.session_state['user']['role'] == 'admin':
                menu_options.append("Admin Panel")
                icons.append("gear")
                
            selected = option_menu(
                "Menu Principal",
                menu_options,
                icons=icons,
                menu_icon="cast",
                default_index=0,
                styles={
                    "container": {"padding": "5px", "background-color": "#2c3e50"},
                    "icon": {"color": "orange", "font-size": "25px"}, 
                    "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
                    "nav-link-selected": {"background-color": "#00cc96"},
                }
            )
            
            st.markdown("---")
            if st.button("Se déconnecter"):
                del st.session_state['user']
                st.rerun()

        # Routing
        if selected == "Dashboard":
            view_dashboard()
        elif selected == "Matières":
            view_subjects()
        elif selected == "Admin Panel":
            if st.session_state['user']['role'] == 'admin':
                view_admin()
            else:
                st.error("Accès non autorisé.")

if __name__ == "__main__":
    main()
