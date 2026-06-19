import streamlit as st
import pandas as pd
import geopandas as gpd
from typing import Dict, Optional, Tuple, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIGURATION & BRANDING
# ============================================================================
st.set_page_config(
    page_title="Indiana Coordinates and Elevation Finder",
    page_icon="📍",
    layout="centered"
)

st.markdown("""
    <style>
        .main { background-color: #f8fafc; }
        .main-header {
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            text-align: center;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            border: 1px solid #334155;
        }
        .main-header h1 { margin: 0; font-size: 2.2rem; font-weight: 800; color: white; letter-spacing: -0.5px; }
        .main-header p { margin: 0.5rem 0 0 0; font-size: 1.2rem; color: #94a3b8; font-weight: 500; }
        .stSelectbox label, .stNumberInput label, .stTextInput label { font-weight: 600; color: #334155; }
        .stTabs [data-baseweb="tab-list"] { gap: 2rem; }
        .stTabs [data-baseweb="tab"] { height: 3.5rem; white-space: pre-wrap; font-weight: 600; }
        hr { border-color: #e2e8f0; }
        .section-title { font-size: 1.25rem; font-weight: 700; color: #0f172a; margin-top: 1.5rem; margin-bottom: 1rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem;}
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA LOAD & SETUP
# ============================================================================
@st.cache_data
def load_county_epsg_codes() -> Dict[str, int]:
    try:
        df = pd.read_csv('indiana_county_epsg.csv')
        df.columns = df.columns.str.strip()
        epsg_dict = {}
        for _, row in df.iterrows():
            county = str(row['County']).strip().upper()
            code = str(row['EPSG_Code']).strip()
            if code.replace('.', '', 1).isdigit():
                epsg_dict[county] = int(float(code))
        return epsg_dict
    except Exception as e:
        st.error(f"❌ Error loading indiana_county_epsg.csv: {e}")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

def get_robust_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ============================================================================
# CORE GEOSPATIAL & API FUNCTIONS
# ============================================================================
def fetch_elevation_usgs(lat: float, lon: float, session: requests.Session) -> Optional[float]:
    try:
        url = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&wkid=4326&includeDate=false"
        resp = session.get(url, timeout=12)
        if resp.status_code == 200:
            val = resp.json().get('value')
            if val is not None and str(val).strip() != '' and str(val).lower() != 'nodata':
                return round(float(val), 2)
    except:
        pass
    return None

def latlon_to_county(lat: float, lon: float, epsg: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        gdf_proj = gdf.to_crs(f'EPSG:{epsg}')
        return round(gdf_proj.geometry.x.iloc[0], 3), round(gdf_proj.geometry.y.iloc[0], 3)
    except:
        return None, None

def county_to_latlon(easting: float, northing: float, epsg: int) -> Tuple[Optional[float], Optional[float]]:
    try:
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([easting], [northing]), crs=f'EPSG:{epsg}')
        gdf_wgs = gdf.to_crs('EPSG:4326')
        return round(gdf_wgs.geometry.y.iloc[0], 6), round(gdf_wgs.geometry.x.iloc[0], 6)
    except:
        return None, None

# ============================================================================
# BATCH PROCESSOR WITH PROGRESS BAR
# ============================================================================
def process_dataframe(df: pd.DataFrame, operation: str, epsg: Optional[int], 
                      col_x: str, col_y: str, progress_bar, status_text) -> pd.DataFrame:
    out_df = df.copy()
    session = get_robust_session()
    total_rows = len(df)
    
    if total_rows == 0:
        return out_df

    # Task 1: Elevation Only
    if operation == "Elevation Only (USA Coverage)":
        status_text.text("📡 Fetching Elevation Data from USGS...")
        points = list(zip(df[col_y], df[col_x])) # col_y is Lat, col_x is Lon
        elevs = [None] * total_rows
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {executor.submit(fetch_elevation_usgs, p[0], p[1], session): i for i, p in enumerate(points)}
            completed = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                elevs[idx] = future.result()
                completed += 1
                progress_bar.progress(completed / total_rows)
        
        out_df['Elevation_Feet'] = elevs

    # Task 2: Lat/Lon -> Indiana
    elif operation == "Lat/Lon ➔ Indiana County Coordinates":
        status_text.text("🗺️ Transforming Coordinates...")
        eastings, northings = [], []
        for i, row in df.iterrows():
            e, n = latlon_to_county(row[col_y], row[col_x], epsg)
            eastings.append(e); northings.append(n)
            progress_bar.progress((i + 1) / total_rows)
            
        out_df['Easting_ft'] = eastings
        out_df['Northing_ft'] = northings
        out_df['County_EPSG'] = epsg

    # Task 3: Indiana -> Lat/Lon
    elif operation == "Indiana County ➔ Lat/Lon":
        status_text.text("🗺️ Reversing Coordinates to Lat/Lon...")
        lats, lons = [], []
        for i, row in df.iterrows():
            lat, lon = county_to_latlon(row[col_x], row[col_y], epsg) # col_x is East, col_y is North
            lats.append(lat); lons.append(lon)
            progress_bar.progress((i + 1) / total_rows)
            
        out_df['Latitude_WGS84'] = lats
        out_df['Longitude_WGS84'] = lons
        out_df['Source_EPSG'] = epsg

    # Task 4: Lat/Lon -> Indiana + Elevation
    elif operation == "Lat/Lon ➔ Indiana County + Elevation":
        status_text.text("🗺️ Step 1: Transforming Coordinates...")
        eastings, northings = [], []
        for i, row in df.iterrows():
            e, n = latlon_to_county(row[col_y], row[col_x], epsg)
            eastings.append(e); northings.append(n)
            progress_bar.progress(((i + 1) / total_rows) * 0.5) # First 50%
            
        out_df['Easting_ft'] = eastings
        out_df['Northing_ft'] = northings
        out_df['County_EPSG'] = epsg
        
        status_text.text("📡 Step 2: Fetching Elevation Data...")
        points = list(zip(df[col_y], df[col_x]))
        elevs = [None] * total_rows
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_to_idx = {executor.submit(fetch_elevation_usgs, p[0], p[1], session): i for i, p in enumerate(points)}
            completed = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                elevs[idx] = future.result()
                completed += 1
                progress_bar.progress(0.5 + ((completed / total_rows) * 0.5)) # Last 50%
                
        out_df['Elevation_Feet'] = elevs

    status_text.text("✅ Processing Complete!")
    progress_bar.progress(1.0)
    return out_df

# ============================================================================
# MAIN UI
# ============================================================================
def main():
    st.markdown("""
        <div class="main-header">
            <h1>📍 Indiana Coordinates and Elevation Finder</h1>
            <p>Laith Sadik, PhD, PE</p>
        </div>
    """, unsafe_allow_html=True)
    
    if not INDIANA_COUNTY_EPSG:
        st.stop()

    # --- SETTINGS / OPERATION SELECTION ---
    st.markdown("<div class='section-title'>⚙️ Workflow Settings</div>", unsafe_allow_html=True)
    
    col_op, col_county = st.columns([3, 2])
    operations = [
        "Elevation Only (USA Coverage)",
        "Lat/Lon ➔ Indiana County Coordinates",
        "Indiana County ➔ Lat/Lon",
        "Lat/Lon ➔ Indiana County + Elevation"
    ]
    
    with col_op:
        selected_operation = st.selectbox("Select Target Operation", operations)
    
    selected_county = None
    epsg_code = None
    
    with col_county:
        if "Indiana" in selected_operation:
            selected_county = st.selectbox("Select Target County", sorted(INDIANA_COUNTY_EPSG.keys()))
            epsg_code = INDIANA_COUNTY_EPSG[selected_county]
            st.caption(f"**EPSG Code:** `{epsg_code}`")
        else:
            st.selectbox("Select Target County", ["N/A (USA Wide)"], disabled=True)
            st.caption("Elevation uses standard WGS84")

    st.markdown("<hr>", unsafe_allow_html=True)

    # --- INPUT METHODS (TABS) ---
    tab1, tab2 = st.tabs(["✍️ Spreadsheet Entry (Manual)", "📁 Bulk Processing (CSV Upload)"])

    is_reverse = (selected_operation == "Indiana County ➔ Lat/Lon")

    # ---------------------------------------------------------
    # TAB 1: DATA EDITOR (SPREADSHEET MANUAL ENTRY)
    # ---------------------------------------------------------
    with tab1:
        st.markdown("**Enter points directly into the grid below. You can copy/paste from Excel and add up to 500+ rows dynamically.**")
        
        # Initialize an empty dataframe based on operation type
        if is_reverse:
            default_df = pd.DataFrame({"Point_ID": ["Pt_1", "Pt_2", "Pt_3"], "Easting": [0.0, 0.0, 0.0], "Northing": [0.0, 0.0, 0.0]})
            col_x, col_y = "Easting", "Northing"
        else:
            default_df = pd.DataFrame({"Point_ID": ["Pt_1", "Pt_2", "Pt_3"], "Latitude": [39.7684, 0.0, 0.0], "Longitude": [-86.1581, 0.0, 0.0]})
            col_x, col_y = "Longitude", "Latitude"

        # Display the interactive data editor
        edited_df = st.data_editor(default_df, num_rows="dynamic", use_container_width=True)
        
        if st.button("🚀 Process Grid Data", type="primary", use_container_width=True):
            # Filter out empty/zero rows to save processing time
            clean_df = edited_df[(edited_df[col_x] != 0.0) | (edited_df[col_y] != 0.0)].copy()
            
            if clean_df.empty:
                st.warning("⚠️ Please enter valid coordinates before running.")
            else:
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                res_manual = process_dataframe(clean_df, selected_operation, epsg_code, col_x, col_y, progress_bar, status_text)
                
                st.success(f"✅ Successfully transformed {len(res_manual)} points.")
                st.dataframe(res_manual, use_container_width=True)
                
                st.download_button(
                    label="💾 Download Results (CSV)",
                    data=res_manual.to_csv(index=False),
                    file_name="manual_spatial_results.csv",
                    mime="text/csv",
                    type="secondary",
                    use_container_width=True
                )

    # ---------------------------------------------------------
    # TAB 2: CSV UPLOAD (WITH COLUMN MAPPING)
    # ---------------------------------------------------------
    with tab2:
        st.markdown("**Upload a CSV file and map your columns.**")
        
        if is_reverse:
            template_df = pd.DataFrame({'ID': ['A1', 'A2'], 'Easting': [200000.5, 200500.2], 'Northing': [150000.1, 150500.9]})
        else:
            template_df = pd.DataFrame({'ID': ['A1', 'A2'], 'Latitude': [39.768412, 40.443105], 'Longitude': [-86.158068, -85.352410]})
            
        st.download_button("📥 Download Example CSV Template", data=template_df.to_csv(index=False), file_name="template.csv", mime="text/csv")
        
        uploaded_file = st.file_uploader("Upload your CSV data", type=['csv'])
        
        if uploaded_file is not None:
            df_upload = pd.read_csv(uploaded_file)
            st.markdown("**Column Mapping Configuration:**")
            
            cols = df_upload.columns.tolist()
            cols_lower = [c.lower() for c in cols]
            
            # Smart defaults
            if is_reverse:
                def_x = cols[cols_lower.index(next((c for c in cols_lower if 'east' in c or c == 'x'), cols_lower[0]))] if cols else None
                def_y = cols[cols_lower.index(next((c for c in cols_lower if 'north' in c or c == 'y'), cols_lower[0]))] if len(cols) > 1 else None
                
                col1, col2 = st.columns(2)
                with col1: col_x = st.selectbox("Easting (X) Column", cols, index=cols.index(def_x) if def_x else 0)
                with col2: col_y = st.selectbox("Northing (Y) Column", cols, index=cols.index(def_y) if def_y else 0)
            else:
                def_y = cols[cols_lower.index(next((c for c in cols_lower if 'lat' in c), cols_lower[0]))] if cols else None
                def_x = cols[cols_lower.index(next((c for c in cols_lower if 'lon' in c), cols_lower[0]))] if len(cols) > 1 else None
                
                col1, col2 = st.columns(2)
                with col1: col_y = st.selectbox("Latitude Column", cols, index=cols.index(def_y) if def_y else 0)
                with col2: col_x = st.selectbox("Longitude Column", cols, index=cols.index(def_x) if def_x else 0)

            st.markdown("**Preview:**")
            st.dataframe(df_upload.head(3), use_container_width=True)
            
            if st.button("🚀 Process CSV Data", type="primary", use_container_width=True):
                progress_bar = st.progress(0.0)
                status_text = st.empty()
                
                res_batch = process_dataframe(df_upload, selected_operation, epsg_code, col_x, col_y, progress_bar, status_text)
                
                st.success(f"✅ Successfully processed {len(res_batch)} points.")
                st.dataframe(res_batch, use_container_width=True)
                
                st.download_button(
                    label="💾 Download Batch Results (CSV)",
                    data=res_batch.to_csv(index=False),
                    file_name="batch_spatial_results.csv",
                    mime="text/csv",
                    type="secondary",
                    use_container_width=True
                )

if __name__ == "__main__":
    main()
