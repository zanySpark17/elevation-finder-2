import streamlit as st
import pandas as pd
import geopandas as gpd
from typing import Dict, Optional, Tuple, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# PAGE CONFIGURATION & STYLING
# ============================================================================

st.set_page_config(
    page_title="Indiana Coordinate & Elevation Transformer",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
        .main { padding-top: 0rem; }
        .header-container {
            background: linear-gradient(135deg, #2b5876 0%, #4e4376 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header-container h1 { margin: 0; font-size: 2.5rem; }
        .header-container p { margin: 0.5rem 0 0 0; font-size: 1rem; opacity: 0.9; }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# DATA & SESSION MANAGEMENT
# ============================================================================

@st.cache_data
def load_county_epsg_codes():
    """Load Indiana County EPSG codes from CSV file"""
    csv_path = 'indiana_county_epsg.csv'
    try:
        df = pd.read_csv(csv_path)
        return dict(zip(df['County'], df['EPSG_Code']))
    except FileNotFoundError:
        st.error(f"❌ CRITICAL: '{csv_path}' not found! Please upload this file.")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

INDIANA_STATE_PLANE = {
    'EAST': 2965,   # NAD83 / Indiana East (ftUS)
    'WEST': 2966    # NAD83 / Indiana West (ftUS)
}

def get_robust_session():
    """Creates a requests session with automatic retries for API stability"""
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# ============================================================================
# API DATA FETCHING (COUNTY & ELEVATION)
# ============================================================================

def fetch_point_data(lat: float, lon: float, session: requests.Session) -> Tuple[Optional[str], Optional[float]]:
    """
    Fetches both County (via FCC API) and Elevation (via USGS 3DEP API) reliably.
    """
    county_name = None
    elevation_feet = None
    
    # 1. Detect County via FCC Census Block API (Highly Accurate)
    try:
        fcc_url = f"https://geo.fcc.gov/api/census/block/find?latitude={lat}&longitude={lon}&format=json"
        fcc_resp = session.get(fcc_url, timeout=10)
        if fcc_resp.status_code == 200:
            data = fcc_resp.json()
            raw_county = data.get('County', {}).get('name', '')
            if raw_county:
                # Normalize string to match CSV (e.g., "St. Joseph" -> "ST_JOSEPH")
                clean_name = raw_county.upper().replace('.', '').replace(' ', '_')
                name_fixes = {'LAPORTE': 'LA_PORTE', 'DE_KALB': 'DEKALB'}
                county_name = name_fixes.get(clean_name, clean_name)
    except Exception:
        pass

    # 2. Fetch Elevation via USGS 3DEP
    try:
        usgs_url = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/identify"
        params = {
            'geometry': json.dumps({'x': lon, 'y': lat}),
            'geometryType': 'esriGeometryPoint',
            'returnGeometry': 'false',
            'f': 'json'
        }
        usgs_resp = session.get(usgs_url, params=params, timeout=10)
        if usgs_resp.status_code == 200:
            val = usgs_resp.json().get('value')
            if val is not None and str(val).lower() != 'nodata':
                elevation_feet = round(float(val) * 3.28084, 2) # Convert meters to feet
    except Exception:
        pass

    return county_name, elevation_feet

def get_batch_data(points: List[Tuple[float, float]], max_workers: int = 5) -> List[Tuple[Optional[str], Optional[float]]]:
    """Fetch county and elevation for multiple points concurrently"""
    results = []
    session = get_robust_session()
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(fetch_point_data, lat, lon, session): i 
            for i, (lat, lon) in enumerate(points)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results.append((idx, future.result()))
            except Exception:
                results.append((idx, (None, None)))
    
    results.sort(key=lambda x: x[0])
    return [res for _, res in results]

# ============================================================================
# COORDINATE TRANSFORMATION
# ============================================================================

def get_state_plane_zone(county_name: str) -> int:
    """Determine which Indiana State Plane zone a county belongs to"""
    if not county_name:
        return INDIANA_STATE_PLANE['EAST'] # Default fallback
        
    east_counties = {
        'ADAMS', 'ALLEN', 'BARTHOLOMEW', 'BLACKFORD', 'BROWN', 'CASS', 'CLARK',
        'DEKALB', 'DEARBORN', 'DECATUR', 'DELAWARE', 'ELKHART', 'FAYETTE', 'FLOYD',
        'FRANKLIN', 'FULTON', 'GRANT', 'HAMILTON', 'HANCOCK', 'HARRISON', 'HENRY',
        'HOWARD', 'HUNTINGTON', 'JACKSON', 'JAY', 'JEFFERSON', 'JENNINGS', 'JOHNSON',
        'KOSCIUSKO', 'LAGRANGE', 'MADISON', 'MARION', 'MARSHALL', 'MIAMI', 'NOBLE',
        'OHIO', 'RANDOLPH', 'RIPLEY', 'RUSH', 'SCOTT', 'SHELBY', 'ST_JOSEPH',
        'STEUBEN', 'SWITZERLAND', 'TIPTON', 'UNION', 'WABASH', 'WASHINGTON',
        'WAYNE', 'WELLS', 'WHITLEY'
    }
    return INDIANA_STATE_PLANE['EAST'] if county_name in east_counties else INDIANA_STATE_PLANE['WEST']

def transform_coordinates_complete(df: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    """Complete transformation pipeline generating all features reliably."""
    output_df = pd.DataFrame()
    output_df['ID'] = df.iloc[:, 0] if len(df.columns) > 0 else range(1, len(df) + 1)
    output_df['Latitude_WGS84'] = df[lat_col].round(6)
    output_df['Longitude_WGS84'] = df[lon_col].round(6)
    
    points = list(zip(df[lat_col], df[lon_col]))
    
    # 1 & 2: Get Counties and Elevations
    api_results = get_batch_data(points)
    detected_counties = [res[0] for res in api_results]
    elevations = [res[1] for res in api_results]
    
    output_df['County_Detected'] = [c if c else 'UNKNOWN' for c in detected_counties]
    output_df['Elevation_Feet'] = elevations
    
    # 3 & 4: Transform Coordinates
    easting_state, northing_state, epsg_state = [], [], []
    easting_county, northing_county, epsg_county = [], [], []
    
    for idx, row in df.iterrows():
        lat, lon = row[lat_col], row[lon_col]
        county = detected_counties[idx]
        
        # Base Geometry
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        
        # State Plane Projection
        state_epsg = get_state_plane_zone(county)
        try:
            gdf_state = gdf.to_crs(f'EPSG:{state_epsg}')
            easting_state.append(gdf_state.geometry.x.values[0])
            northing_state.append(gdf_state.geometry.y.values[0])
            epsg_state.append(state_epsg)
        except Exception:
            easting_state.append(None); northing_state.append(None); epsg_state.append(None)
            
        # County Coordinate Projection
        c_epsg = INDIANA_COUNTY_EPSG.get(county) if county else None
        if c_epsg:
            try:
                gdf_county = gdf.to_crs(f'EPSG:{int(c_epsg)}')
                easting_county.append(gdf_county.geometry.x.values[0])
                northing_county.append(gdf_county.geometry.y.values[0])
                epsg_county.append(c_epsg)
            except Exception:
                easting_county.append(None); northing_county.append(None); epsg_county.append(None)
        else:
            easting_county.append(None); northing_county.append(None); epsg_county.append(None)
            
    output_df['Easting_State_Plane_ft'] = [round(x, 2) if x else None for x in easting_state]
    output_df['Northing_State_Plane_ft'] = [round(y, 2) if y else None for y in northing_state]
    output_df['State_Plane_Zone'] = ['East' if e == INDIANA_STATE_PLANE['EAST'] else 'West' for e in epsg_state]
    output_df['State_Plane_EPSG'] = epsg_state
    
    output_df['Easting_County_ft'] = [round(x, 2) if x else None for x in easting_county]
    output_df['Northing_County_ft'] = [round(y, 2) if y else None for y in northing_county]
    output_df['County_EPSG'] = epsg_county
    
    return output_df

# ============================================================================
# STREAMLIT UI - MAIN APP
# ============================================================================

def main():
    st.markdown("""
        <div class="header-container">
            <h1>🗺️ Indiana Coordinate & Elevation Transformer</h1>
            <p>Automatic county detection • State Plane conversion • USGS elevation data</p>
        </div>
    """, unsafe_allow_html=True)
    
    if not INDIANA_COUNTY_EPSG:
        st.error("❌ CRITICAL ERROR: indiana_county_epsg.csv not found or empty!")
        st.info("Please ensure indiana_county_epsg.csv is in the same directory as app.py")
        return
    
    with st.sidebar:
        st.header("⚙️ Settings")
        mode = st.radio("Select Input Mode:", ["📁 Upload CSV", "✍️ Manual Entry"], index=0)
        st.markdown("---")
        st.info("""
        **This app automatically:**
        ✅ Detects exact Indiana county (via FCC API)
        ✅ Converts to State Plane coordinates
        ✅ Converts to county-specific coordinates
        ✅ Fetches elevation (via USGS 3DEP)
        """)
    
    if "📁 Upload CSV" in mode:
        show_csv_mode()
    else:
        show_manual_mode()

def show_csv_mode():
    st.subheader("📂 Upload CSV File")
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("""
        **Requirements:**
        - Column with latitude (name contains 'lat')
        - Column with longitude (name contains 'lon' or 'long')
        - Optional: ID column
        """)
    with col2:
        st.download_button(
            label="📥 Download Template",
            data=pd.DataFrame({'ID': ['Point1', 'Point2'], 'Latitude': [39.7684, 39.1653], 'Longitude': [-86.1581, -86.5264]}).to_csv(index=False),
            file_name="template.csv", mime="text/csv"
        )
    
    uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.success(f"✅ Loaded: {len(df)} rows, {len(df.columns)} columns")
            
            df_cols = df.columns.tolist()
            lat_candidates = [col for col in df_cols if 'lat' in col.lower()]
            lon_candidates = [col for col in df_cols if any(k in col.lower() for k in ['long', 'lon'])]
            
            if not lat_candidates or not lon_candidates:
                st.error("❌ Could not find latitude/longitude columns")
                return
            
            lat_col, lon_col = lat_candidates[0], lon_candidates[0]
            
            with st.expander("👁️ Preview Data", expanded=False):
                st.dataframe(df.head(), use_container_width=True)
            
            if st.button("🚀 Process & Transform", type="primary", use_container_width=True):
                df_clean = df.copy()
                df_clean[lat_col] = pd.to_numeric(df_clean[lat_col].astype(str).str.replace('°', '').str.strip(), errors='coerce')
                df_clean[lon_col] = pd.to_numeric(df_clean[lon_col].astype(str).str.replace('°', '').str.strip(), errors='coerce')
                df_clean = df_clean.dropna(subset=[lat_col, lon_col])
                
                if len(df_clean) == 0:
                    st.error("❌ No valid coordinates found!")
                    return
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("🔄 Communicating with APIs and Transforming Coordinates..."):
                    status_text.text("📡 Fetching precise County and Elevation via FCC & USGS...")
                    progress_bar.progress(30)
                    
                    result_df = transform_coordinates_complete(df_clean, lat_col, lon_col)
                    
                    status_text.text("✅ Transformation complete!")
                    progress_bar.progress(100)
                
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                st.markdown("---")
                st.subheader("📊 Transformation Results")
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Points", len(result_df))
                col2.metric("Counties Detected", result_df['County_Detected'].apply(lambda x: x != 'UNKNOWN').sum())
                col3.metric("Elevations Found", result_df['Elevation_Feet'].notna().sum())
                col4.metric("County Coords Generated", result_df['County_EPSG'].notna().sum())
                
                st.dataframe(result_df, use_container_width=True)
                
                st.download_button(
                    label="💾 Download Results (CSV)",
                    data=result_df.to_csv(index=False),
                    file_name="indiana_transformation_results.csv",
                    mime="text/csv", type="primary", use_container_width=True
                )
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

def show_manual_mode():
    st.subheader("✍️ Manual Coordinate Entry")
    num_points = st.number_input("Number of points:", min_value=1, max_value=20, value=1)
    data = []
    
    for i in range(int(num_points)):
        st.markdown(f"**Point {i+1}**")
        col1, col2, col3 = st.columns(3)
        with col1: point_id = st.text_input("ID", value=f"Point_{i+1}", key=f"id_{i}")
        with col2: lat = st.number_input("Latitude", value=39.7684 if i == 0 else 0.0, format="%.6f", key=f"lat_{i}")
        with col3: lon = st.number_input("Longitude", value=-86.1581 if i == 0 else 0.0, format="%.6f", key=f"lon_{i}")
        if lat != 0.0 or lon != 0.0:
            data.append({'ID': point_id, 'Latitude': lat, 'Longitude': lon})
            
    if st.button("🚀 Process & Transform", type="primary", use_container_width=True):
        if not data:
            st.warning("⚠️ Please enter at least one coordinate pair")
            return
        
        with st.spinner("🔄 Processing via FCC and USGS APIs..."):
            df_manual = pd.DataFrame(data)
            result_df = transform_coordinates_complete(df_manual, 'Latitude', 'Longitude')
        
        st.markdown("---")
        st.subheader("📊 Transformation Results")
        st.dataframe(result_df, use_container_width=True)
        st.download_button("💾 Download Results", result_df.to_csv(index=False), "indiana_manual_transformation.csv", "text/csv", type="primary", use_container_width=True)

if __name__ == "__main__":
    main()
