import streamlit as st
import pandas as pd
import geopandas as gpd
from typing import Dict, Optional, Tuple, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================
st.set_page_config(
    page_title="Indiana Coordinate & Elevation Transformer",
    page_icon="🗺️",
    layout="wide"
)

# ============================================================================
# DATA LOAD
# ============================================================================
def load_county_epsg_codes() -> Dict[str, str]:
    """Load Indiana County EPSG codes robustly from CSV file"""
    csv_path = 'indiana_county_epsg.csv'
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
        # Ensure clean strings mapping to clean strings
        keys = df['County'].astype(str).str.strip().tolist()
        vals = df['EPSG_Code'].astype(str).str.strip().tolist()
        return dict(zip(keys, vals))
    except Exception as e:
        st.error(f"❌ CRITICAL ERROR reading CSV: {e}")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

INDIANA_STATE_PLANE = {
    'EAST': 2965,
    'WEST': 2966
}

def get_robust_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def clean_county_name(raw_name: str) -> str:
    if not raw_name or pd.isna(raw_name): return ""
    name = re.sub(r'(?i)[_\s-]*county$', '', str(raw_name))
    name = name.upper().replace('.', '').replace("'", "").strip()
    name = re.sub(r'[\s-]+', '_', name)
    fixes = {'LAPORTE': 'LA_PORTE', 'DEKALB': 'DEKALB', 'DE_KALB': 'DEKALB', 'ST_JOSEPH': 'ST_JOSEPH'}
    return fixes.get(name, name)

# ============================================================================
# API DATA FETCHING
# ============================================================================
def fetch_point_data(lat: float, lon: float, session: requests.Session) -> Tuple[Optional[str], Optional[float]]:
    county_name, elevation_feet = None, None
    
    # 1. Census Geocoder
    try:
        census_url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
        census_resp = session.get(census_url, timeout=10)
        if census_resp.status_code == 200:
            counties = census_resp.json().get('result', {}).get('geographies', {}).get('Counties', [])
            if counties:
                county_name = clean_county_name(counties[0].get('BASENAME', ''))
    except Exception:
        pass

    # 2. USGS EPQS
    try:
        usgs_url_1 = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&wkid=4326&includeDate=false"
        resp_1 = session.get(usgs_url_1, timeout=10)
        if resp_1.status_code == 200:
            val = resp_1.json().get('value')
            if val is not None and str(val).strip() != '' and str(val).lower() != 'nodata':
                elevation_feet = round(float(val), 2)
    except Exception:
        pass

    return county_name, elevation_feet

def get_batch_data(points: List[Tuple[float, float]]) -> List[Tuple[Optional[str], Optional[float]]]:
    results = []
    session = get_robust_session()
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {executor.submit(fetch_point_data, lat, lon, session): i for i, (lat, lon) in enumerate(points)}
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results.append((idx, future.result()))
            except Exception:
                results.append((idx, (None, None)))
    results.sort(key=lambda x: x[0])
    return [res for _, res in results]

# ============================================================================
# TRANSFORMATION
# ============================================================================
def get_state_plane_zone(county_name: str) -> int:
    if not county_name: return INDIANA_STATE_PLANE['EAST']
    east_counties = {'ADAMS', 'ALLEN', 'BARTHOLOMEW', 'BLACKFORD', 'BROWN', 'CASS', 'CLARK', 'DEKALB', 'DEARBORN', 'DECATUR', 'DELAWARE', 'ELKHART', 'FAYETTE', 'FLOYD', 'FRANKLIN', 'FULTON', 'GRANT', 'HAMILTON', 'HANCOCK', 'HARRISON', 'HENRY', 'HOWARD', 'HUNTINGTON', 'JACKSON', 'JAY', 'JEFFERSON', 'JENNINGS', 'JOHNSON', 'KOSCIUSKO', 'LAGRANGE', 'MADISON', 'MARION', 'MARSHALL', 'MIAMI', 'NOBLE', 'OHIO', 'RANDOLPH', 'RIPLEY', 'RUSH', 'SCOTT', 'SHELBY', 'ST_JOSEPH', 'STEUBEN', 'SWITZERLAND', 'TIPTON', 'UNION', 'WABASH', 'WASHINGTON', 'WAYNE', 'WELLS', 'WHITLEY'}
    return INDIANA_STATE_PLANE['EAST'] if county_name in east_counties else INDIANA_STATE_PLANE['WEST']

def transform_coordinates_complete(df: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    output_df = pd.DataFrame()
    output_df['ID'] = df.iloc[:, 0] if len(df.columns) > 0 else range(1, len(df) + 1)
    output_df['Latitude_WGS84'] = df[lat_col].round(6)
    output_df['Longitude_WGS84'] = df[lon_col].round(6)
    
    points = list(zip(df[lat_col], df[lon_col]))
    api_results = get_batch_data(points)
    
    output_df['County_Detected'] = [res[0] if res[0] else 'UNKNOWN' for res in api_results]
    output_df['Elevation_Feet'] = [res[1] for res in api_results]
    
    easting_state, northing_state, epsg_state = [], [], []
    easting_county, northing_county, epsg_county = [], [], []
    
    for idx, row in df.iterrows():
        lat, lon, county = row[lat_col], row[lon_col], output_df['County_Detected'].iloc[idx]
        gdf = gpd.GeoDataFrame([1], geometry=gpd.points_from_xy([lon], [lat]), crs='EPSG:4326')
        
        # State Plane
        state_epsg = get_state_plane_zone(county)
        try:
            gdf_state = gdf.to_crs(f'EPSG:{state_epsg}')
            easting_state.append(gdf_state.geometry.x.values[0])
            northing_state.append(gdf_state.geometry.y.values[0])
            epsg_state.append(state_epsg)
        except:
            easting_state.append(None); northing_state.append(None); epsg_state.append(None)
            
        # County
        c_epsg = INDIANA_COUNTY_EPSG.get(county) if county != 'UNKNOWN' else None
        if c_epsg and str(c_epsg).isdigit():
            try:
                gdf_county = gdf.to_crs(f'EPSG:{int(c_epsg)}')
                easting_county.append(gdf_county.geometry.x.values[0])
                northing_county.append(gdf_county.geometry.y.values[0])
                epsg_county.append(int(c_epsg))
            except:
                easting_county.append(None); northing_county.append(None); epsg_county.append(None)
        else:
            easting_county.append(None); northing_county.append(None); epsg_county.append(None)
            
    output_df['Easting_State_Plane_ft'] = [round(x, 2) if x else None for x in easting_state]
    output_df['Northing_State_Plane_ft'] = [round(y, 2) if y else None for y in northing_state]
    output_df['State_Plane_Zone'] = ['East' if e == 2965 else 'West' for e in epsg_state]
    output_df['State_Plane_EPSG'] = epsg_state
    
    output_df['Easting_County_ft'] = [round(x, 2) if x else None for x in easting_county]
    output_df['Northing_County_ft'] = [round(y, 2) if y else None for y in northing_county]
    output_df['County_EPSG'] = epsg_county
    
    return output_df

# ============================================================================
# MAIN UI
# ============================================================================
def main():
    st.title("🗺️ Indiana Coordinate & Elevation Transformer")
    
    if not INDIANA_COUNTY_EPSG:
        st.error("❌ indiana_county_epsg.csv is missing or broken.")
        return
        
    mode = st.radio("Select Input Mode:", ["✍️ Manual Entry", "📁 Upload CSV"], index=0)
    
    if "Manual Entry" in mode:
        st.subheader("✍️ Manual Coordinate Entry")
        lat = st.number_input("Latitude", value=40.4431, format="%.6f")
        lon = st.number_input("Longitude", value=-85.3524, format="%.6f")
        
        if st.button("🚀 Process & Transform", type="primary"):
            with st.spinner("Processing..."):
                df_manual = pd.DataFrame([{'ID': 'Point_1', 'Latitude': lat, 'Longitude': lon}])
                result_df = transform_coordinates_complete(df_manual, 'Latitude', 'Longitude')
                st.dataframe(result_df, use_container_width=True)
    else:
        uploaded_file = st.file_uploader("Choose CSV file", type=['csv'])
        if uploaded_file and st.button("🚀 Process & Transform", type="primary"):
            df = pd.read_csv(uploaded_file)
            lat_col = [c for c in df.columns if 'lat' in c.lower()][0]
            lon_col = [c for c in df.columns if 'lon' in c.lower()][0]
            with st.spinner("Processing..."):
                result_df = transform_coordinates_complete(df, lat_col, lon_col)
                st.dataframe(result_df, use_container_width=True)

if __name__ == "__main__":
    main()
