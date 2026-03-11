import streamlit as st
import pandas as pd
import datetime
import altair as alt
import io
import json
from supabase import create_client, Client
import os
# --- INITIALISATION SUPABASE ---
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erreur de connexion à Supabase. Vérifiez votre fichier secrets.toml.")
# --- CHARGEMENT DES DONNÉES DEPUIS SUPABASE ---
if 'db_entries' not in st.session_state:
    st.session_state.db_entries = []
    try:
        # On interroge la base de données
        response = supabase.table("co2_flux_carbone").select("*").execute()
        
        # On remet les données au bon format pour l'application
        for row in response.data:
            st.session_state.db_entries.append({
                "Catégorie": row["categorie"],
                "Item": row["item"],
                "Quantité": row["quantite"],
                "Impact_kgCO2": row["impact_kgco2"],
                "Incertitude": row["incertitude"],
                "Marge": row["marge"],
                "Détail": row["detail"],
                "Date": row["date_saisie"]
            })
    except Exception as e:
        st.warning("Erreur lors de la récupération des données historiques.")

# ==============================================================================
# 1. CONFIGURATION & STYLE
# ==============================================================================
st.set_page_config(
    page_title="MSCAL Carbon ERP",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)
# Style CSS Amélioré
st.markdown("""
    <style>
        /* Style général */
        .block-container {padding-top: 1rem;}
        h1 {color: #2c3e50;}
        h2 {color: #34495e;}
        h3 {color: #16a085;} /* Un joli vert pour les sous-titres */
        
        /* Style des "Cartes" de chiffres (Metrics) */
        [data-testid="stMetric"] {
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 2px 2px 5px rgba(0,0,0,0.05); /* Petite ombre douce */
            text-align: center;
        }
        
        /* Style des Onglets */
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] {
            height: 45px;
            background-color: white;
            border-radius: 5px;
            border: 1px solid #ddd;
            font-weight: 600;
        }
        .stTabs [aria-selected="true"] {
            background-color: #e8f5e9; /* Vert très clair quand sélectionné */
            color: #1e8449;
            border: 1px solid #1e8449;
        }

        /* Footer et Impression (inchangé) */
        .footer {
            position: fixed; bottom: 0; left: 0; width: 20%;
            background-color: #f0f2f6; color: #555;
            text-align: center; padding: 10px; font-size: 11px;
            border-top: 1px solid #ddd; z-index: 999;
        }
        @media print {
            [data-testid="stSidebar"], .stButton, header {display: none;}
            .block-container {padding-top: 0 !important;}
        }
    </style>
""", unsafe_allow_html=True)

# --- SÉCURITÉ : MOT DE PASSE et GESTION DES RÔLES ---

def check_password():
    """Gère l'authentification Admin vs Visiteur."""
    if "user_role" not in st.session_state:
        st.session_state.user_role = None

    if st.session_state.user_role:
        return True  # Déjà connecté

    # Espace pour le titre
    st.markdown("<br><br><br>", unsafe_allow_html=True)
    
    st.markdown("### 🔒 Accès Sécurisé MSCAL ERP")
    st.caption("Connectez-vous pour accéder à l'outil.")
    
    pwd = st.text_input("Mot de passe :", type="password")
    
    if st.button("Se connecter"):
        if pwd == "MSCAL2026":  # <--- MOT DE PASSE ADMIN
            st.session_state.user_role = "admin"
            st.success("Connexion Admin réussie !")
            st.rerun()
        elif pwd == "GUEST":    # <--- MOT DE PASSE VISITEUR
            st.session_state.user_role = "guest"
            st.info("Connexion Visiteur (Accès limité).")
            st.rerun()
        else:
            st.error("❌ Mot de passe incorrect")
            
    return False

if not check_password():
    st.stop()


# Style CSS (Signature + Titres + Ajustements)
st.markdown("""
    <style>
        .footer {
            position: fixed; bottom: 0; left: 0; width: 20%;
            background-color: #f0f2f6; color: #555;
            text-align: center; padding: 10px; font-size: 11px;
            border-top: 1px solid #ddd; z-index: 999;
        }
        .block-container {padding-top: 1rem;}
        h3 {color: #2c3e50; font-weight: 600;}
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 5px; }
        .stTabs [aria-selected="true"] { background-color: #e8f0fe; color: #1a73e8; }
        .stDataFrame {border: 1px solid #ddd; border-radius: 5px;}
    </style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. INITIALISATION MÉMOIRE & PARAMÈTRES (AUTO-RÉPARATION)
# ==============================================================================
DEFAULT_PARAMS = {
    'entity_name': 'Promo MSCAL 2026',
    'pop_etu': 20, 
    'pop_alt': 5, 
    'pop_prof': 2,
    'jours_ouverture': 160,
    'budget_co2': 3.5,
    'country_choice': "France 🇫🇷",
    
    # --- FINANCE ---
    'shadow_price': 100.0,
    
    # --- ÉNERGIE & EAU ---
    'fe_elec': 0.060,       # Mix France
    'fe_gaz': 0.227,        # Gaz naturel
    'fe_eau': 0.132,        # Eau potable (m3)
    'fe_dechet': 0.200,     # Déchets moyens
    
    # --- MOBILITÉ ---
    'fe_voit': 0.190,       # Voiture thermique
    'fe_voit_elec': 0.060,  # Voiture élec
    'fe_avion_court': 0.258,
    'fe_avion_long': 0.230,
    'fe_tgv': 0.002,        # TGV
    'fe_ter': 0.030,        # Train classique
    'fe_bus': 0.100,        # Bus urbain
    'fe_autocar': 0.030,    # Autocar
    
    # --- VIE & ACHATS ---
    'fe_boeuf': 7.0,        # Repas Bœuf
    'fe_volaille': 1.6,     # Repas Poulet
    'fe_vege': 0.5,         # Repas Végétarien
    'fe_cafe': 5.0,         # Café (kg)
    
    # --- NUMÉRIQUE (IT) ---
    'fe_it_laptop': 156.0,  # PC Portable
    'fe_it_desktop': 350.0, # PC Fixe
    'fe_it_screen': 200.0,  # Écran 24"
    'fe_it_smartphone': 60.0
}

# Initialisation des paramètres avec Sécurité
if 'params' not in st.session_state:
    st.session_state.params = DEFAULT_PARAMS.copy()
else:
    # Réparation : on injecte les clés manquantes
    for key, value in DEFAULT_PARAMS.items():
        if key not in st.session_state.params:
            st.session_state.params[key] = value

# Initialisation de la base de données des flux
if 'db_entries' not in st.session_state:
    st.session_state.db_entries = []

# Base de données des Pays
COUNTRY_DATA = {
    "France 🇫🇷": {"val": 0.060, "info": "Mix Nucléaire (Bas carbone)"},
    "Allemagne 🇩🇪": {"val": 0.380, "info": "Mix Charbon/Renouvelable"},
    "Europe (Moy) 🇪🇺": {"val": 0.255, "info": "Moyenne continentale"},
    "USA 🇺🇸": {"val": 0.370, "info": "Mix Fossile prédominant"},
    "Chine 🇨🇳": {"val": 0.550, "info": "Dominante Charbon"}
}

# Fonction de sauvegarde standardisée (Connectée à Supabase)
def save_flux(cat, item, val, unit, fe, incertitude, detail):
    impact = val * fe
    marge = impact * (incertitude / 100.0)
    date_jour = str(datetime.date.today())

    # 1. On prépare la ligne pour l'affichage local
    nouvelle_ligne = {
        "Catégorie": cat,
        "Item": item,
        "Quantité": f"{val} {unit}",
        "Impact_kgCO2": float(impact),
        "Incertitude": int(incertitude),
        "Marge": float(marge),
        "Détail": detail,
        "Date": date_jour
    }
    
    # 2. On envoie les données vers Supabase
    try:
        # On récupère le nom de la promo tapé à la page 1 (ex: "Promo MSCAL 2026")
        nom_promo = st.session_state.params.get('entity_name', 'Promo Inconnue')
        
        data_db = {
            "promotion": nom_promo,      # <--- La fameuse étiquette !
            "categorie": cat,
            "item": item,
            "quantite": f"{val} {unit}",
            "impact_kgco2": float(impact),
            "incertitude": int(incertitude),
            "marge": float(marge),
            "detail": detail,
            "date_saisie": date_jour
        }
        supabase.table("co2_flux_carbone").insert(data_db).execute()
    except Exception as e:
        st.error(f"❌ Erreur d'envoi vers la base de données : {e}")

    # 3. On ajoute à la session pour que le tableau se mette à jour direct sous tes yeux
    st.session_state.db_entries.append(nouvelle_ligne)

# ==============================================================================
# 3. BARRE LATÉRALE
# ==============================================================================
with st.sidebar:
    
    try:
        st.image("logo.png", use_container_width=True)
    except:
        st.header("🌍 MSCAL ERP")
    # --- ZONE DE SAUVEGARDE/CHARGEMENT (Optimisée) ---
    st.sidebar.divider() # Une ligne de séparation propre
    

    st.markdown("### 🧭 Menu de Navigation")
    # --- DÉFINITION DU MENU SELON LE RÔLE ---
    if st.session_state.user_role == "admin":
        # L'Admin voit tout
        menu_options = [
            "0. 📘 GUIDE & DÉFINITIONS",
            "1. ⚙️ DÉFINIR & PARAMÉTRER", 
            "2. 📝 MESURER (Saisie Flux)", 
            "3. 📊 ANALYSER (Cockpit & KPIs)",
            "4. 🚀 AMÉLIORER (Simulateur)",
            "5. 📄 CONTRÔLER (Rapport Final)"
        ]
    else:
        # Le Visiteur/Étudiant voit une version simplifiée
        menu_options = [
            "0. 📘 GUIDE & DÉFINITIONS",
            "2. 📝 MESURER (Saisie Flux)", 
            "3. 📊 ANALYSER (Cockpit & KPIs)",
            "4. 🚀 AMÉLIORER (Simulateur)"
        ]
        st.info(f"👤 Mode Visiteur")

    nav = st.radio("Séquence de travail", menu_options)
    
    st.divider()
    
    # Indicateur Ambition
    st.markdown("🎯 **Objectif Cible**")
    # Sécurité anti-crash pour le budget
    try:
        b_val = float(st.session_state.params.get('budget_co2', 3.5))
    except:
        b_val = 3.5
        st.session_state.params['budget_co2'] = 3.5
    
    if b_val <= 2.5: color = "green"
    elif b_val <= 5.0: color = "blue"
    elif b_val <= 9.0: color = "orange"
    else: color = "red"
    st.markdown(f":{color}[**{b_val:.1f} Tonnes / pers**]")



   
# --- PIED DE PAGE (SIGNATURE & LOGO CÔTE À CÔTE) ---
    st.sidebar.markdown("---") # Ligne de séparation fine
    
    # On crée 2 colonnes : Petite à gauche (logo), plus large à droite (texte)
    c_logo_footer, c_text_footer = st.sidebar.columns([1, 3])
    
    with c_logo_footer:
        # Affiche le logo en petit (comme une icône).
        # Ajuste "width=60" si tu le veux un peu plus grand ou plus petit.
        st.image("logo_acs.png", width=60) 
        
    with c_text_footer:
        # Le texte de signature, aligné à gauche pour coller au logo
        st.markdown(
            """
            <div style="text-align: left; font-size: 11px; color: #888; line-height: 1.4; padding-top: 5px;">
                <b>© 2026 MSCAL CARBON ERP</b><br>
                Dev by <b>ACS Engineering Solutions</b><br>
                <span style="font-size: 10px;">Contact us : mscal.ensaia@gmail.com</span>
            </div>
            """,
            unsafe_allow_html=True
        )
 
# ==============================================================================
# PAGE 0 : GUIDE & DÉFINITIONS
# ==============================================================================
if "0." in nav:
    st.title("📘 Guide Utilisateur & Méthodologie")
    st.markdown("Bienvenue dans le **MSCAL Carbon ERP**. Ce guide vous explique les concepts clés et comment utiliser l'outil.")

    with st.expander("📖 Mode d'Emploi Rapide", expanded=True):
        st.markdown("""
        1.  **DÉFINIR :** Configurez les paramètres de votre école (nombre d'élèves, pays, calendrier).
        2.  **MESURER :** Saisissez vos équipements (inventaire) et les déplacements (flux).
        3.  **ANALYSER :** Visualisez vos impacts et identifiez les points critiques (Hotspots).
        4.  **AMÉLIORER :** Simulez des scénarios de réduction (ex: Télétravail, Isolation) pour 2030.
        5.  **CONTRÔLER :** Éditez le rapport officiel PDF/Excel pour la direction.
        """)

    with st.expander("🧐 Comprendre les Scopes (1, 2, 3)", expanded=True):
        st.info("""
        **Scope 1 (Direct) :** Émissions directes sur le site.  
        *Ex : Gaz brûlé par la chaudière, Carburant des véhicules de service.*
        
        **Scope 2 (Énergie Indirecte) :** Émissions liées à la production de l'électricité que vous consommez.  
        *Ex : L'électricité pour l'éclairage et les ordinateurs.*
        
        **Scope 3 (Autres Indirects) :** Tout le reste ! C'est souvent 80% du bilan.  
        *Ex : Déplacements domicile-travail, achats de PC, nourriture, déchets...*
        """)

    with st.expander("🧠 Définitions des KPIs & Termes Techniques"):
        st.markdown("""
        * **kgCO2e (Équivalent CO2) :** Unité de mesure universelle qui regroupe tous les gaz à effet de serre (CO2, Méthane, etc.).
        * **Facteur d'Émission (FE) :** Le coefficient qui transforme une donnée physique en CO2. *Ex: 1 kWh d'élec en France = 0.060 kgCO2e.*
        * **Shadow Price (Coût Fantôme) :** On donne un prix fictif à la tonne de CO2 (ex: 100€/T) pour visualiser le risque financier futur (taxe carbone).
        * **Incertitude :** Marge d'erreur de la donnée. Si vous estimez un kilométrage "à la louche", l'incertitude est haute (30-50%).
        * **Pareto (80/20) :** Principe selon lequel 20% des causes font 80% des dégâts. On cherche ces 20% pour agir vite.
        """)
# ==============================================================================
# PAGE 1 : DÉFINIR (CONFIGURATION)
# ==============================================================================

if "1." in nav:
    st.title("⚙️ Paramétrage du Projet")
    st.markdown("Définissez le contexte, la population et les hypothèses techniques.")

    # --- A. IDENTITÉ & POPULATION ---
    with st.container(border=True):
        st.subheader("1. Identité & Population")
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.session_state.params['entity_name'] = st.text_input(
                "Nom de l'entité", 
                value=st.session_state.params['entity_name']
            )
            
            st.markdown("**Taille de la promotion :**")

            promo_size = st.number_input(
             "Nombre d'étudiants",
             min_value=0,
             max_value=500,
             value=int(st.session_state.params.get('pop_etu', 20))
            )

            st.session_state.params['pop_etu'] = promo_size
            st.session_state.params['pop_alt'] = 0
            st.session_state.params['pop_prof'] = 0

            st.metric("Taille de la promo", f"{promo_size} étudiants")

        with c2:
            st.markdown("**🎯 Ambition Climatique**")
            # Utilisation de slider simple (plus robuste que select_slider pour les conflits de mémoire)
            budget = st.slider(
                "Objectif cible (Tonnes CO2e/an/personne)",
                min_value=1.0, max_value=15.0, 
                value=float(st.session_state.params.get('budget_co2', 3.5)),
                step=0.5
            )
            st.session_state.params['budget_co2'] = budget
            
            if budget <= 2.0: 
                st.success("🏆 **Obj. 2050 (Accords de Paris)** - Idéal mais difficile")
            elif budget <= 5.0: 
                st.info("👍 **Transition Mondiale** - Moyenne Mondiale")
            elif budget <= 9.0: 
                st.warning("🇫🇷 **Moyenne Française** - Business as usual")
            else: 
                st.error("🚨 **Critique** - Niveau USA/Qatar")

   # --- B. CALENDRIER ---
    with st.container(border=True):
        st.subheader("2. Gestion du Temps (Calendrier)")
        
        st.info("Calculez les jours ouvrés en soustrayant les vacances.")
        c_dates, c_result = st.columns(2)
        with c_dates:
            d_start = st.date_input("Date de Rentrée", datetime.date(2025, 9, 1))
            d_end = st.date_input("Fin d'année", datetime.date(2026, 6, 30))
            
            # Modification ici : on passe en jours (ex: 20 jours = 4 semaines de 5 jours)
            nb_jours_vac = st.number_input("Jours de vacances (hors week-ends)", 0, 150, 20)
            jours_par_semaine = st.slider("Jours de cours / semaine", 1, 6, 5)
        
        with c_result:
            total_days = (d_end - d_start).days
            if total_days > 0:
                total_weeks = total_days / 7
                
                # Nouveau calcul : on calcule le total de jours de cours potentiels, puis on enlève les jours de vacances
                jours_cours_bruts = total_weeks * jours_par_semaine
                jours_presence_estimes = int(max(0, jours_cours_bruts - nb_jours_vac)) # max(0, ...) empêche d'avoir un chiffre négatif
                
                st.write(f"• Période Totale : **{total_weeks:.1f} sem.**")
                st.write(f"• Vacances : **-{nb_jours_vac} jours**")
                st.metric("Jours de Présence Estimés", f"{jours_presence_estimes} jours")
                
                if st.button("✅ Valider ce calcul"):
                    st.session_state.params['jours_ouverture'] = jours_presence_estimes
                    st.toast(f"Calendrier mis à jour : {jours_presence_estimes} jours")
            else:
                st.error("La date de fin doit être après la date de début.")
    
    # --- C. CONFIGURATION TECHNIQUE (VERSION FRANCE) ---
    with st.container(border=True):
        st.subheader("3. Facteurs d'Émission (Base France)")
        st.caption("Valeurs par défaut mises à jour pour votre projet.")
        
        # On garde le prix du carbone pour l'analyse financière
        st.session_state.params['shadow_price'] = st.number_input("💶 Prix du Carbone (€/T)", value=float(st.session_state.params.get('shadow_price', 100.0)), step=10.0)

        # NOUVEAUX ONGLETS RÉORGANISÉS
        t_mob, t_cons, t_it, t_bat = st.tabs(["🚗 Mobilité", "☕ Consommables", "💻 Numérique", "⚡ Bâtiment"])
        
        with t_mob:
            c1, c2 = st.columns(2)
            st.session_state.params['fe_voit'] = c1.number_input("Voiture Thermique (kgCO2/km)", value=0.190, format="%.3f")
            st.session_state.params['fe_voit_elec'] = c2.number_input("Voiture Électrique (kgCO2/km)", value=0.060, format="%.3f")
            st.session_state.params['fe_bus'] = c1.number_input("Bus (kgCO2/km)", value=0.100, format="%.3f")
            st.session_state.params['fe_tram'] = c2.number_input("Tram (kgCO2/km)", value=0.003, format="%.3f")
            st.session_state.params['fe_velo'] = c1.number_input("Vélo/Marche (kgCO2/km)", value=0.000, format="%.3f")
            st.session_state.params['fe_tgv'] = c2.number_input("TGV (kgCO2/km)", value=0.003, format="%.3f")
            st.session_state.params['fe_ter'] = c1.number_input("TER/Train (kgCO2/km)", value=0.030, format="%.3f")
            st.session_state.params['fe_avion'] = c2.number_input("Avion (kgCO2/km)", value=0.240, format="%.3f")

        with t_cons:
            c1, c2 = st.columns(2)
            st.session_state.params['fe_micro_ondes'] = c1.number_input("Micro-ondes (kgCO2/min)", value=0.0028, format="%.4f")
            st.session_state.params['fe_cafe'] = c2.number_input("1 Tasse de café (kgCO2/tasse)", value=0.0043, format="%.4f")
            st.session_state.params['fe_the'] = c1.number_input("1 Tasse de thé (kgCO2/tasse)", value=0.0018, format="%.4f")
            st.session_state.params['fe_papier'] = c2.number_input("Papier (kgCO2 / 15 feuilles)", value=0.075, format="%.3f")

        with t_it:
            c1, c2 = st.columns(2)
            st.session_state.params['fe_it_laptop'] = c1.number_input("Ordinateur portable (kgCO2/h)", value=0.045, format="%.3f")
            st.session_state.params['fe_it_desktop'] = c2.number_input("Ordinateur fixe (kgCO2/h)", value=0.070, format="%.3f")
            st.session_state.params['fe_it_smart'] = c1.number_input("Smartphone (kgCO2/h)", value=0.018, format="%.3f")
            st.session_state.params['fe_it_tab'] = c2.number_input("Tablette (kgCO2/h)", value=0.045, format="%.3f")
            st.session_state.params['fe_it_vp'] = c1.number_input("Vidéoprojecteur (kgCO2/h)", value=0.095, format="%.3f")
            
        with t_bat:
            st.caption("Constantes conservées pour le calcul global du bâtiment.")
            c1, c2 = st.columns(2)
            st.session_state.params['fe_gaz'] = c1.number_input("Gaz (kgCO2/kWh)", value=float(st.session_state.params.get('fe_gaz', 0.227)), format="%.3f")
            st.session_state.params['fe_eau'] = c2.number_input("Eau (kgCO2/m3)", value=float(st.session_state.params.get('fe_eau', 0.132)), format="%.3f")
            st.session_state.params['fe_dechet'] = c1.number_input("Déchets (kgCO2/kg)", value=float(st.session_state.params.get('fe_dechet', 0.200)), format="%.3f")


# ==============================================================================
# PAGE 2 : MESURER (SAISIE DES FLUX SIMPLIFIÉE & AUTO-CALCULÉE)
# ==============================================================================
elif "2." in nav:
    st.title("📝 Mesure des Flux (Saisie des données)")
    st.markdown("Saisissez les quantités consommées, les temps d'utilisation et votre inventaire.")

    tab_inv, tab_mob, tab_cons, tab_it, tab_bat = st.tabs([
        "🪑 Inventaire Salle",
        "🚗 Mobilité", 
        "☕ Consommables", 
        "💻 Numérique",
        "⚡ Bâtiment"
    ])

    # 0. INVENTAIRE DE LA SALLE MSCAL 310
    with tab_inv:
        st.subheader("🪑 Inventaire Physique (Salle MSCAL 310)")
        st.info("💡 **Astuce :** Le tableau est pré-rempli. Vous pouvez taper n'importe quelle nouvelle famille (ex: Matériel TP, Décoration...) librement !")

        if 'inventory_mscal' not in st.session_state:
            st.session_state.inventory_mscal = pd.DataFrame([
                {"Catégorie": "Mobilier", "Équipement": "Chaise étudiante", "Quantité": 30},
                {"Catégorie": "Mobilier", "Équipement": "Table étudiante", "Quantité": 15},
                {"Catégorie": "Mobilier", "Équipement": "Bureau Professeur", "Quantité": 1},
                {"Catégorie": "Mobilier", "Équipement": "Placard de rangement", "Quantité": 2},
                {"Catégorie": "Électroménager", "Équipement": "Petit Frigo", "Quantité": 1}
            ])

        edited_inv = st.data_editor(
            st.session_state.inventory_mscal,
            num_rows="dynamic",
            column_config={
                # CHANGEMENT ICI : TextColumn au lieu de SelectboxColumn pour une liberté totale
                "Catégorie": st.column_config.TextColumn("Famille / Catégorie", required=True),
                "Équipement": st.column_config.TextColumn("Nom de l'objet", required=True),
                "Quantité": st.column_config.NumberColumn("Combien ?", min_value=0, step=1, required=True)
            },
            use_container_width=True,
            hide_index=True
        )
        st.session_state.inventory_mscal = edited_inv

        if st.button("💾 Enregistrer cet inventaire au bilan"):
            for i, row in edited_inv.iterrows():
                if row["Quantité"] > 0:
                    fe_estime = 20.0 
                    texte = str(row["Équipement"]).lower()
                    if "frigo" in texte: fe_estime = 150.0
                    elif "placard" in texte or "armoire" in texte: fe_estime = 50.0
                    elif "table" in texte or "bureau" in texte: fe_estime = 25.0
                    elif "chaise" in texte: fe_estime = 10.0

                    save_flux("Inventaire Salle", row["Équipement"], row["Quantité"], "u", fe_estime, 10, f"Catégorie: {row['Catégorie']}")
            st.success("✅ Inventaire de la salle MSCAL enregistré avec succès !")

    # 1. MOBILITÉ (AUTO-CALCULÉE)
    with tab_mob:
        st.subheader("🚗 Logistique Humaine & Déplacements")
        
        type_trajet = st.selectbox("Catégorie de déplacement", [
            "🎓 Étudiants (Initiale) - Domicile/Campus",
            "💼 Étudiants (Alternance) - Trajets vers l'entreprise",
            "🏛️ Double Cursus Master (Trajets Metz)",
            "🌍 Voyage d'études",
            "👨‍🏫 Professeurs - Domicile/Campus",
            "🎤 Intervenants extérieurs ponctuels"
        ])
        
        c1, c2 = st.columns(2)
        mode = c1.selectbox("Moyen de transport principal", [
            "Voiture Thermique", "Voiture Électrique", "Bus", "Tram", 
            "Vélo/Marche", "TER/Train", "TGV", "Avion"
        ])
        nb_personnes = c2.number_input("Nombre de personnes concernées", min_value=1, value=1)
        
        dist_ar = st.number_input("Distance d'un Aller-Retour (km)", min_value=1, value=20)
        
        # MOTEUR DE CALCUL DU RYTHME (Remplace la saisie manuelle quand c'est possible)
        jours_ouv = st.session_state.params.get('jours_ouverture', 160)
        
        if "Initiale" in type_trajet or "Professeurs" in type_trajet:
            nb_trajets = jours_ouv
            st.info(f"🔄 **Calcul automatique :** {nb_trajets} trajets A/R (1 par jour de présence à l'école).")
        
        elif "Alternance" in type_trajet:
            # Si rythme 2sem/2sem : 1 aller-retour vers l'entreprise par bloc de 4 semaines.
            # Jours présence = temps à l'école (la moitié du temps). 
            # Donc (jours_ouv / 10) donne le nombre de rotations.
            nb_trajets = max(1, int(jours_ouv / 10))
            st.info(f"🔄 **Calcul automatique :** {nb_trajets} trajets A/R vers l'entreprise (Basé sur un rythme 2 sem. / 2 sem. sur l'année).")
            
        else:
            # Pour les intervenants, Metz ou les voyages, on laisse la main car c'est du sur-mesure
            nb_trajets = st.number_input("Nombre de trajets A/R par an et par personne", min_value=1, value=1)
        
        if st.button("➕ Ajouter ce groupe de déplacements"):
            fe = 0.0
            if mode == "Voiture Thermique": fe = st.session_state.params['fe_voit']
            elif mode == "Voiture Électrique": fe = st.session_state.params['fe_voit_elec']
            elif mode == "Bus": fe = st.session_state.params['fe_bus']
            elif mode == "Tram": fe = st.session_state.params['fe_tram']
            elif mode == "Vélo/Marche": fe = st.session_state.params['fe_velo']
            elif mode == "TER/Train": fe = st.session_state.params['fe_ter']
            elif mode == "TGV": fe = st.session_state.params['fe_tgv']
            elif mode == "Avion": fe = st.session_state.params['fe_avion']

            distance_totale = dist_ar * nb_trajets * nb_personnes
            titre_propre = type_trajet.split(" - ")[0].replace("🎓 ", "").replace("💼 ", "").replace("🏛️ ", "").replace("🌍 ", "").replace("👨‍🏫 ", "").replace("🎤 ", "")
            
            save_flux("Mobilité", f"{titre_propre} ({mode})", distance_totale, "km.pax", fe, 10, f"{dist_ar}km x {nb_trajets} trajets")
            st.success(f"Déplacements ajoutés pour : {titre_propre}")

    # 2. CONSOMMABLES
    with tab_cons:
        st.subheader("☕ Vie de Campus (Repas, Papier, Micro-ondes)")
        
        c1, c2 = st.columns(2)
        item = c1.selectbox("Élément consommé", [
            "1 Tasse de café", "1 Tasse de thé", 
            "Ramette (15 feuilles de papier)", "Micro-ondes (Utilisation)"
        ])
        
        qte_label = "Temps d'utilisation (Minutes)" if "Micro-ondes" in item else "Quantité totale"
        qte = c2.number_input(qte_label, min_value=1, value=50)
        
        if st.button("➕ Ajouter la consommation"):
            fe = 0.0
            unit = "u"
            if "café" in item: fe = st.session_state.params['fe_cafe']
            elif "thé" in item: fe = st.session_state.params['fe_the']
            elif "papier" in item: 
                fe = st.session_state.params['fe_papier']
                unit = "paquets de 15f"
            elif "Micro-ondes" in item: 
                fe = st.session_state.params['fe_micro_ondes']
                unit = "min"

            # CHANGEMENT ICI : "Consommables" au lieu de "Achats"
            save_flux("Consommables", item, qte, unit, fe, 10, "Conso courante")
            st.success(f"Consommation ajoutée : {item}")

    # 3. NUMÉRIQUE 
    with tab_it:
        st.subheader("💻 Utilisation du Parc Numérique")
        st.caption("Calculez l'impact lié au temps d'utilisation des écrans.")
        
        with st.form("form_it"):
            c1, c2 = st.columns(2)
            appareil = c1.selectbox("Appareil", [
                "Ordinateur portable", "Ordinateur fixe", 
                "Smartphone", "Tablette", "Vidéoprojecteur"
            ])
            nb_appareils = c2.number_input("Nombre d'appareils", min_value=1, value=25)
            heures_utilisation = st.number_input("Temps d'utilisation total par appareil (Heures)", min_value=1, value=100)
            
            if st.form_submit_button("➕ Ajouter l'usage IT"):
                fe = 0.0
                if appareil == "Ordinateur portable": fe = st.session_state.params['fe_it_laptop']
                elif appareil == "Ordinateur fixe": fe = st.session_state.params['fe_it_desktop']
                elif appareil == "Smartphone": fe = st.session_state.params['fe_it_smart']
                elif appareil == "Tablette": fe = st.session_state.params['fe_it_tab']
                elif appareil == "Vidéoprojecteur": fe = st.session_state.params['fe_it_vp']
                
                total_heures = nb_appareils * heures_utilisation
                save_flux("Numérique", appareil, total_heures, "heures", fe, 10, f"{nb_appareils} appareils")
                st.success(f"Usage Numérique ajouté : {appareil}")

    # 4. BÂTIMENT
    with tab_bat:
        st.subheader("⚡ Consommation des Locaux")
        c1, c2 = st.columns(2)
        type_conso = c1.selectbox("Type d'énergie / Flux", ["Électricité", "Chauffage (Gaz)", "Consommation Eau", "Production Déchets"])
        
        label_unite = "kWh" if ("Gaz" in type_conso or "Électricité" in type_conso) else "m3" if "Eau" in type_conso else "kg"
        valeur = c2.number_input(f"Volume total consommé sur l'année ({label_unite})", min_value=1, value=1000)
        
        if st.button("➕ Ajouter au Bâtiment"):
            fe = 0.0
            if "Électricité" in type_conso: fe = 0.060
            elif "Gaz" in type_conso: fe = st.session_state.params['fe_gaz']
            elif "Eau" in type_conso: fe = st.session_state.params['fe_eau']
            elif "Déchets" in type_conso: fe = st.session_state.params['fe_dechet']
            
            save_flux("Bâtiment", type_conso, valeur, label_unite, fe, 10, "Bâtiment global")
            st.success(f"Flux Bâtiment ajouté : {type_conso}")

    # --- TABLEAU DE CONTRÔLE FINAL ---
    st.divider()
    st.markdown("### 🔍 Journal des Saisies")
    
    if st.session_state.db_entries:
        df_flux = pd.DataFrame(st.session_state.db_entries)
        colonnes_a_afficher = ["Catégorie", "Item", "Quantité", "Impact_kgCO2", "Détail"]
        df_propre = df_flux[colonnes_a_afficher].copy()
        
        st.dataframe(
            df_propre,
            column_config={
                "Impact_kgCO2": st.column_config.NumberColumn("Impact (kgCO2e)", format="%.2f kg"),
            },
            use_container_width=True
        )
        
        tot = df_flux["Impact_kgCO2"].sum()
        st.metric("Total de l'empreinte saisie", f"{tot/1000:.3f} Tonnes")
    else:
        st.info("Aucune donnée saisie pour le moment. Remplissez les formulaires ou validez l'inventaire.")

# ==============================================================================
# PAGE 3 : ANALYSER (TABLEAU DE BORD DÉCISIONNEL & SCOPES)
# ==============================================================================
elif "3." in nav:
    import altair as alt 
    
    st.title("📊 Cockpit de Performance & Analyse")
    st.markdown("Analyse fine des impacts, identification des leviers et contrôle de la qualité de donnée.")

    current_promo = st.session_state.params.get('entity_name', 'Promo Inconnue')
    
    if not st.session_state.db_entries:
        st.warning("⚠️ Aucune donnée disponible. Veuillez remplir l'étape 2 'MESURER' d'abord.")
    else:
        # 1. PRÉPARATION DE LA DATA
        df_all = pd.DataFrame(st.session_state.db_entries)
        
        # Nettoyage des types de données
        df_all["Impact_kgCO2"] = pd.to_numeric(df_all["Impact_kgCO2"], errors='coerce').fillna(0)
        df_all["Marge"] = pd.to_numeric(df_all["Marge"], errors='coerce').fillna(0)
        df = df_all.copy() 
        
        if df.empty or df["Impact_kgCO2"].sum() == 0:
            st.warning("⚠️ Aucune émission calculée pour le moment.")
        else:
            # --- CALCUL DES SCOPES ISO ---
            def get_scope(row):
                cat = str(row.get("Catégorie", ""))
                item = str(row.get("Item", ""))
                if cat == "Bâtiment":
                    if "Gaz" in item: return "Scope 1 (Direct)"
                    if "Électricité" in item: return "Scope 2 (Énergie)"
                    return "Scope 3 (Autres)"
                return "Scope 3 (Autres)"

            df["Scope"] = df.apply(get_scope, axis=1)

            # --- CALCUL DES KPIs ---
            total_co2_t = df["Impact_kgCO2"].sum() / 1000.0
            total_marge_t = df["Marge"].sum() / 1000.0
            pop_totale = st.session_state.params.get('pop_etu', 1) + st.session_state.params.get('pop_alt', 0)
            ratio_pers = total_co2_t / pop_totale if pop_totale > 0 else total_co2_t
            cout_carbone = total_co2_t * float(st.session_state.params.get('shadow_price', 100.0))
            
            # --- ZONE 1 : CONTROL TOWER ---
            st.markdown("### 🎛️ Control Tower")
            k1, k2, k3, k4 = st.columns(4)
            
            # KPI en GRAS
            k1.metric("**Impact Total**", f"{total_co2_t:.2f} T CO2e", f"± {total_marge_t:.2f} T")
            k2.metric("**Ratio / Personne**", f"{ratio_pers:.2f} T/pers", f"Objectif: {st.session_state.params.get('budget_co2', 3.5)}T")
            k3.metric("**Risque Financier**", f"{cout_carbone:,.0f} €", "Shadow Price valorisé")
            k4.metric("**Lignes Saisies**", len(df), "Flux enregistrés")

            st.divider()

            # --- ZONE 2 : VISUALISATION AVANCÉE ---
            st.markdown("### 🔭 Analyse Visuelle & Stratégique")
            
            t_rep, t_scope, t_pareto, t_pop, t_bench = st.tabs([
                "🍩 Répartition", "🏗️ Scopes (ISO)", "📉 Pareto (80/20)", "👥 Mobilité", "🏆 Benchmark"
            ])

            with t_rep:
                c1, c2 = st.columns([2, 1])
                with c1:
                    df_cat = df.groupby("Catégorie")["Impact_kgCO2"].sum().reset_index()
                    chart_donut = alt.Chart(df_cat).mark_arc(innerRadius=60).encode(
                        theta=alt.Theta(field="Impact_kgCO2", type="quantitative"),
                        color=alt.Color(field="Catégorie", type="nominal", scale=alt.Scale(scheme='tableau10')),
                        tooltip=["Catégorie", alt.Tooltip("Impact_kgCO2", format=".1f", title="kg CO2e")]
                    ).properties(title="Répartition par Grand Poste")
                    st.altair_chart(chart_donut, use_container_width=True)
                with c2:
                    st.markdown("**Top 3 Contributeurs :**")
                    top3 = df.groupby("Catégorie")["Impact_kgCO2"].sum().sort_values(ascending=False).head(3)
                    for cat, val in top3.items():
                        st.write(f"• **{cat}** : {val/1000:.1f} T")

            with t_scope:
                st.caption("Norme ISO 14064.")
                bar_scope = alt.Chart(df).mark_bar(cornerRadius=5).encode(
                    x=alt.X('Scope', sort=['Scope 1 (Direct)', 'Scope 2 (Énergie)', 'Scope 3 (Autres)'], title=None),
                    y=alt.Y('sum(Impact_kgCO2)', title='kg CO2e'),
                    color=alt.Color('Scope', scale=alt.Scale(domain=['Scope 1 (Direct)', 'Scope 2 (Énergie)', 'Scope 3 (Autres)'], range=['#ff6b6b', '#feca57', '#54a0ff']))
                ).properties(height=350)
                st.altair_chart(bar_scope, use_container_width=True)

            with t_pareto:
                st.caption("Diagramme de Pareto identifiant les postes prioritaires.")
                df_p = df.groupby("Item")["Impact_kgCO2"].sum().reset_index().sort_values("Impact_kgCO2", ascending=False)
                df_p["Cumul"] = df_p["Impact_kgCO2"].cumsum() / df_p["Impact_kgCO2"].sum()
                base = alt.Chart(df_p.head(10)).encode(x=alt.X('Item', sort=None, axis=alt.Axis(labelAngle=-45)))
                bars = base.mark_bar().encode(y='Impact_kgCO2')
                line = base.mark_line(color='red', point=True).encode(y='Cumul')
                st.altair_chart((bars + line).resolve_scale(y='independent'), use_container_width=True)

            with t_pop:
                df_hum = df[df['Catégorie'] == 'Mobilité']
                if not df_hum.empty:
                    st.bar_chart(df_hum.set_index("Item")["Impact_kgCO2"])
                else:
                    st.info("Aucune donnée de mobilité disponible.")

            with t_bench:
                st.subheader("🏁 Comparaison Inter-Promotions")
                st.caption("Comparaison avec l'historique Supabase (votre promotion est en bleu foncé).")
                try:
                    # Récupération de Supabase
                    res_bench = supabase.table("co2_flux_carbone").select("promotion, impact_kgco2").execute()
                    df_all_promos = pd.DataFrame(res_bench.data)
                    
                    if not df_all_promos.empty:
                        # Calcul par promo
                        df_compare = df_all_promos.groupby("promotion")["impact_kgco2"].sum().reset_index()
                        df_compare["Tonnes"] = df_compare["impact_kgco2"] / 1000.0
                        
                        # Graphique BENCHMARK (Couleurs mises à jour)
                        c_bench = alt.Chart(df_compare).mark_bar(cornerRadius=5).encode(
                            x=alt.X('promotion:N', title="Promotions", sort='-y'),
                            y=alt.Y('Tonnes:Q', title="Total (Tonnes CO2e)"),
                            # Bleu profond pour la promo actuelle, gris clair pour les autres
                            color=alt.condition(
                                alt.datum.promotion == current_promo,
                                alt.value('#1e3a8a'), # Corporate Deep Blue
                                alt.value('#d1d5db')  # Gris clair/neutre
                            ),
                            tooltip=['promotion', alt.Tooltip('Tonnes', format=".2f")]
                        ).properties(height=350)
                        st.altair_chart(c_bench, use_container_width=True)
                    else:
                        st.info("Historique Supabase vide pour le moment.")
                except Exception as e:
                    st.error(f"Erreur technique lors de la comparaison : {e}")

            # --- ZONE 3 : EXPORT ---
            st.divider()
            col_ex1, col_ex2 = st.columns(2)
            with col_ex1:
                st.info("💡 **Export PDF :** Utilisez `Ctrl + P` sur votre navigateur.")
            with col_ex2:
                # Création de la date actuelle
                import datetime
                date_str = datetime.date.today().strftime("%Y-%m-%d")
                
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='Bilan')
                st.download_button(
                    "📥 Télécharger Rapport (.xlsx)", 
                    data=buffer, 
                    file_name=f"Bilan_{current_promo}_{date_str}.xlsx",
                    mime="application/vnd.ms-excel"
                )
# ==============================================================================
# PAGE 4 : SIMULER (LEVIERS BASÉS SUR L'INVENTAIRE RÉEL)
# ==============================================================================
elif "4." in nav:
    import altair as alt
    st.title("🎯 Simulateur de Stratégies MSCAL")
    st.markdown("Agissez directement sur les quantités et les temps d'utilisation saisis.")

    if not st.session_state.db_entries:
        st.warning("⚠️ Saisissez d'abord des données à l'étape 2 pour pouvoir simuler.")
    else:
        df = pd.DataFrame(st.session_state.db_entries)
        df["Impact_kgCO2"] = pd.to_numeric(df["Impact_kgCO2"], errors='coerce').fillna(0)
        impact_init_kg = df["Impact_kgCO2"].sum()

        # --- FONCTIONS DE FILTRAGE PAR MOT-CLÉ ---
        def get_data(keyword):
            return df[df['Item'].str.contains(keyword, case=False, na=False)]

        # --- INTERFACE DE SIMULATION ---
        col_sliders, col_results = st.columns([1.5, 1])

        with col_sliders:
            # GROUPE 1 : MOBILITÉ (En jours et en personnes)
            with st.expander("🚗 Mobilité (Trajets & Covoiturage)", expanded=True):
                st.write("Calcul basé sur vos trajets Domicile-Campus et Metz.")
                s_covoit = st.slider("Covoiturage (Nombre de personnes par voiture)", 1.0, 4.0, 1.0, 0.5)
                s_distanciel = st.slider("Nombre de jours de Télétravail / semaine", 0, 5, 0)

            # GROUPE 2 : VIE DE CAMPUS (En unités concrètes)
            with st.expander("☕ Consommables & Équipements", expanded=True):
                # On regarde combien de cafés ont été saisis au total
                total_cafes = get_data("café")["Impact_kgCO2"].count() # Juste pour info
                s_cafe = st.slider("Réduction du nombre de cafés/thés (tasses/an)", 0, 2000, 0, 50)
                
                s_micro = st.slider("Réduction du temps de Micro-ondes (minutes/an)", 0, 5000, 0, 100)
                s_papier = st.slider("Nombre de ramettes de papier économisées", 0, 100, 0)

            # GROUPE 3 : NUMÉRIQUE (En heures et en années)
            with st.expander("💻 Numérique (Usage & Matériel)", expanded=True):
                s_it_heures = st.slider("Réduction du temps d'usage par ordi (heures/an)", 0, 500, 0, 10)
                s_duree = st.slider("Allongement durée de vie du parc (Années sup.)", 0, 5, 0)

            # GROUPE 4 : BÂTIMENT (En degrés)
            with st.expander("🔥 Énergie", expanded=True):
                s_chauff = st.slider("Baisse de la température de consigne (°C)", 0, 5, 0)

        # --- MOTEUR DE CALCUL DES ÉCONOMIES (BASÉ SUR LES FE DE L'ÉTAPE 1) ---
        eco_totale = 0.0

        # 1. Calcul Mobilité
        imp_voit = get_data("Voiture")["Impact_kgCO2"].sum()
        # Gain covoiturage
        eco_totale += (imp_voit - (imp_voit / s_covoit))
        # Gain distanciel (on réduit l'impact des trajets réguliers au prorata des 5 jours ouvrés)
        imp_commute = get_data("Étudiants")["Impact_kgCO2"].sum() + get_data("Professeurs")["Impact_kgCO2"].sum()
        eco_totale += (imp_commute * (s_distanciel / 5.0))

        # 2. Calcul Consommables (Unités x FE)
        eco_totale += (s_cafe * st.session_state.params['fe_cafe'])
        eco_totale += (s_micro * st.session_state.params['fe_micro_ondes'])
        eco_totale += (s_papier * st.session_state.params['fe_papier'])

        # 3. Calcul Numérique
        # Heures : (Nb appareils estimé à 25) * heures * FE moyen IT
        eco_totale += (25 * s_it_heures * 0.045) 
        # Durée de vie : Impact fabrication (70%) amorti sur plus longtemps
        imp_it_total = df[df['Catégorie'] == 'Numérique']["Impact_kgCO2"].sum()
        eco_totale += (imp_it_total * 0.7 * (s_duree / (4 + s_duree)))

        # 4. Calcul Bâtiment
        imp_gaz = get_data("Gaz")["Impact_kgCO2"].sum()
        eco_totale += (imp_gaz * (s_chauff * 0.07))

        # --- RÉSULTATS ---
        final_t = max(0, (impact_init_kg - eco_totale) / 1000.0)

        with col_results:
            st.markdown("### 📊 Résultats")
            st.metric("Nouvel Impact", f"{final_t:.2f} T", f"-{eco_totale:.1f} kgCO2e", delta_color="inverse")
            
            # Graphique avec AXES NOMMÉS
            df_chart = pd.DataFrame({
                "Scénario": ["Actuel (Réel)", "Simulé (Projet)"],
                "Valeur": [impact_init_kg/1000, final_t]
            })
            
            chart = alt.Chart(df_chart).mark_bar(size=60).encode(
                x=alt.X('Scénario', title='Type de Scénario', axis=alt.Axis(labelAngle=0)),
                y=alt.Y('Valeur', title='Empreinte Carbone (Tonnes CO2e)'),
                color=alt.Color('Scénario', scale=alt.Scale(range=['#e74c3c', '#2ecc71']), legend=None)
            ).properties(height=400)
            
            st.altair_chart(chart, use_container_width=True)
            
            pct_red = (eco_totale / impact_init_kg * 100) if impact_init_kg > 0 else 0
            st.write(f"Réduction : **{pct_red:.1f}%**")

    st.divider()
    st.caption("Simulation basée sur vos facteurs d'émission de l'étape 1.")

# ==============================================================================
# PAGE 5 : RAPPORT & EXPORT (OFFICIAL REPORTING - VERSION FINALE SANS ASTUCE AU PRINT)
# ==============================================================================
elif "5." in nav:
    st.markdown('<div class="no-print"><h1>📄 Édition du Rapport Officiel</h1></div>', unsafe_allow_html=True)
    
    # --- CSS ULTRA-STRICT ---
    st.markdown("""
<style>
    @media print {
        /* Cache tout ce qui n'est pas le rapport */
        section[data-testid="stSidebar"], header, footer, .stButton, 
        [data-testid="stExpander"], .stDownloadButton, [data-testid="stHeader"],
        .no-print, .print-tip {
            display: none !important;
        }
        .main .block-container { padding: 0 !important; margin: 0 !important; }
        .report-body {
            position: absolute !important;
            left: 0 !important;
            top: 0 !important;
            width: 100% !important;
            border: none !important;
            box-shadow: none !important;
        }
    }

    /* Style Écran */
    .report-body {
        background-color: white;
        padding: 40px;
        color: #2c3e50;
        font-family: 'Segoe UI', Tahoma, sans-serif;
        max-width: 800px;
        margin: 20px auto;
        border: 1px solid #ddd;
        box-shadow: 0 0 10px rgba(0,0,0,0.1);
    }
    .print-tip {
        background-color: #e8f4f8; 
        padding: 15px; 
        border-radius: 5px; 
        border-left: 5px solid #29b5e8; 
        margin: 20px auto;
        max-width: 800px;
        color: #005a87;
        font-size: 14px;
    }
    .title-h1 { text-align: center; font-size: 28px; margin-bottom: 5px; font-weight: bold; }
    .subtitle-h2 { text-align: center; font-size: 20px; color: #7f8c8d; margin-bottom: 20px; }
    .section-head { background: #f8f9fa; padding: 10px; border-left: 5px solid #2ecc71; font-weight: bold; margin-top: 25px; }
    .grid-container { display: flex; justify-content: space-between; margin: 20px 0; }
    .card { width: 30%; text-align: center; padding: 15px; background: #fafafa; border: 1px solid #eee; border-radius: 5px; }
    .report-table { width: 100%; border-collapse: collapse; margin-top: 10px; }
    .report-table th { background: #34495e; color: white; padding: 10px; text-align: left; }
    .report-table td { padding: 8px; border-bottom: 1px solid #eee; }
    .sig-row { display: flex; justify-content: space-between; margin-top: 60px; }
    .sig-box { width: 40%; border-top: 1px solid #000; text-align: center; padding-top: 10px; font-weight: bold; }
</style>
    """, unsafe_allow_html=True)

    if not st.session_state.db_entries:
        st.warning("⚠️ Aucune donnée disponible.")
    else:
        # Données
        df = pd.DataFrame(st.session_state.db_entries)
        df["Impact_kgCO2"] = pd.to_numeric(df["Impact_kgCO2"], errors='coerce').fillna(0)
        tot_co2 = df["Impact_kgCO2"].sum() / 1000
        pop = st.session_state.params['pop_etu'] + st.session_state.params['pop_alt'] + st.session_state.params['pop_prof']
        ratio = (tot_co2 * 1000) / (pop if pop > 0 else 1)

        # Config (no-print)
        with st.expander("🛠️ Configuration du Rapport", expanded=True):
            col_a, col_b = st.columns(2)
            auteur = col_a.text_input("Auteur", st.session_state.get('rep_auteur', "Direction MSCAL"))
            version = col_b.text_input("Réf / Version", st.session_state.get('rep_ver', f"DOC-{datetime.date.today().year}"))
            if st.button("✨ Générer l'analyse auto"):
                top_cat = df.groupby("Catégorie")["Impact_kgCO2"].sum().idxmax()
                st.session_state['report_txt'] = f"Bilan global : {tot_co2:.2f} T CO2e. Poste majeur : {top_cat}. Ratio : {ratio:.0f} kg/pers."
            commentaires = st.text_area("Analyse Expert", value=st.session_state.get('report_txt', ""), height=100)
            st.session_state['rep_auteur'], st.session_state['rep_ver'], st.session_state['report_txt'] = auteur, version, commentaires

        # Tableaux
        df_cat = df.groupby("Catégorie")["Impact_kgCO2"].sum().reset_index()
        df_cat["T"] = (df_cat["Impact_kgCO2"]/1000).round(2)
        rows_cat = "".join([f"<tr><td>{r['Catégorie']}</td><td>{r['T']}</td></tr>" for _, r in df_cat.iterrows()])
        
        df_top = df.sort_values("Impact_kgCO2", ascending=False).head(5)
        df_top["T"] = (df_top["Impact_kgCO2"]/1000).round(3)
        rows_top = "".join([f"<tr><td>{r['Catégorie']}</td><td>{r['Item']}</td><td>{r['T']}</td></tr>" for _, r in df_top.iterrows()])

        # RAPPORT HTML
        report_html = f"""<div class="report-body">
<div class="title-h1">RAPPORT DE BILAN CARBONE</div>
<div class="subtitle-h2">{st.session_state.params['entity_name']}</div>
<hr style="border:1px solid #2c3e50;">
<p style="text-align:center;">Date : {datetime.date.today()} | Auteur : {auteur} | Réf : {version}</p>
<div class="section-head">1. Synthèse des Indicateurs</div>
<div class="grid-container">
<div class="card"><small>EMPREINTE TOTALE</small><br><b style="font-size:20px; color:#e74c3c;">{tot_co2:.2f} T CO2e</b></div>
<div class="card"><small>INTENSITÉ / PERS</small><br><b style="font-size:20px;">{ratio:.0f} kg</b></div>
<div class="card"><small>COÛT RISQUE</small><br><b style="font-size:20px;">{tot_co2 * st.session_state.params['shadow_price']:,.0f} €</b></div>
</div>
<div class="section-head">2. Analyse & Recommandations</div>
<div style="padding:15px; border:1px dashed #7f8c8d; font-style:italic; margin:10px 0;">{commentaires if commentaires else "Analyse en attente..."}</div>
<div class="section-head">3. Répartition par Catégorie</div>
<table class="report-table"><thead><tr><th>Catégorie</th><th>Impact (T CO2e)</th></tr></thead><tbody>{rows_cat}</tbody></table>
<div class="section-head">4. Top 5 des Émissions</div>
<table class="report-table"><thead><tr><th>Catégorie</th><th>Élément</th><th>Impact (T)</th></tr></thead><tbody>{rows_top}</tbody></table>
<div class="sig-row"><div class="sig-box">Visa Responsable RSE</div><div class="sig-box">Visa Direction</div></div>
</div>"""
        st.markdown(report_html, unsafe_allow_html=True)

        # ASTUCE (HTML pur pour pouvoir la cacher)
        st.markdown("""
            <div class="print-tip">
                💡 <b>POUR LE PDF :</b> Faites <code>Ctrl + P</code>, Mode <b>Portrait</b>, cochez <b>'Graphiques d'arrière-plan'</b>.
            </div>
        """, unsafe_allow_html=True)

        # Actions (no-print)
        st.markdown('<div class="no-print"><br>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            if st.button("💾 Sauvegarder"): st.success("Enregistré !")
        with c2:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='xlsxwriter') as wr:
                df.to_excel(wr, index=False, sheet_name='Audit')
            st.download_button("📥 Télécharger Excel", buf, f"Audit_{st.session_state.params['entity_name']}.xlsx")
        st.markdown('</div>', unsafe_allow_html=True)