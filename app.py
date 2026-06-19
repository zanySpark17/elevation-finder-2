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
def load_county_epsg_codes() -> Dict[str, str]:
    """Load Indiana County EPSG codes robustly from CSV file"""
    csv_path = 'indiana_county_epsg.csv'
    try:
        df = pd.read_csv(csv_path)
        # Strip invisible whitespace from columns and data
        df.columns = df.columns.str.strip()
        return dict(zip(df['County'].astype(str).str.strip(), df['EPSG_Code']))
    except Exception as e:
        st.error(f"❌ CRITICAL: '{csv_path}' error! Please ensure the file is valid. ({e})")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

INDIANA_STATE_PLANE = {
    'EAST': 2965,   # NAD83 / Indiana East (ftUS)
    'WEST': 2966    # NAD83 / Indiana West (ftUS)
}

def get_robust_session() -> requests.Session:
    """Creates a requests session with automatic retries for API stability"""
    session = requests.Session()
    retry = Retry(total=4, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def clean_county_name(raw_name: str) -> str:
    """Strictly normalizes county names to match the exact keys in the CSV."""
    if not raw_name or pd.isna(raw_name):
        return ""
    
    # Remove any trailing " County" variations
    name = re.sub(r'(?i)[_\s-]*county$', '', str(raw_name))
    
    # Uppercase, remove periods and quotes
    name = name.upper().replace('.', '').replace("'", "").strip()
    
    # Replace remaining spaces/hyphens with underscores
    name = re.sub(r'[\s-]+', '_', name)
    
    # Indiana specific fixes to match the exact CSV keys
    fixes = {
        'LAPORTE': 'LA_PORTE',
        'DEKALB': 'DEKALB',
        'DE_KALB': 'DEKALB',
        'ST_JOSEPH': 'ST_JOSEPH',
        'SAINT_JOSEPH': 'ST_JOSEPH',
        'VANDERBURG': 'VANDERBURGH'
    }
    return fixes.get(name, name)

# ============================================================================
# API DATA FETCHING (COUNTY & ELEVATION)
# ============================================================================

def fetch_point_data(lat: float, lon: float, session: requests.Session) -> Tuple[Optional[str], Optional[float]]:
    """
    Fetches County (US Census API) and Elevation (USGS EPQS) reliably.
    """
    county_name = None
    elevation_feet = None
    
    # 1. Detect County via US Census Geocoder (Highly Accurate Legal Boundaries)
    try:
        census_url = f"https://geocoding.geo.census.gov/geocoder/geographies/coordinates?x={lon}&y={lat}&benchmark=Public_AR_Current&vintage=Current_Current&format=json"
        census_resp = session.get(census_url, timeout=15)
        if census_resp.status_code == 200:
            data = census_resp.json()
            counties = data.get('result', {}).get('geographies', {}).get('Counties', [])
            if counties:
                raw_county = counties[0].get('BASENAME', '')
                if raw_county:
                    county_name = clean_county_name(raw_county)
    except Exception:
        pass

    # Fallback to FCC Block API if Census API drops the ball
    if not county_name:
        try:
            fcc_url = f"https://geo.fcc.gov/api/census/block/find?latitude={lat}&longitude={lon}&format=json"
            fcc_resp = session.get(fcc_url, timeout=10)
            if fcc_resp.status_code == 200:
                data = fcc_resp.json()
                raw_county = data.get('County', {}).get('name', '')
                if raw_county:
                    county_name = clean_county_name(raw_county)
        except Exception:
            pass

    # 2. Fetch Elevation via modern USGS EPQS (Point Query Service)
    try:
        usgs_url_1 = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&wkid=4326&includeDate=false"
        resp_1 = session.get(usgs_url_1, timeout=10)
        if resp_1.status_code == 200:
            val = resp_1.json().get('value')
            if val is not None and str(val).strip() != '' and str(val).lower() != 'nodata':
                elevation_feet = round(float(val), 2)
    except Exception:
        pass
        
    # Fallback to ArcGIS ImageServer if EPQS fails
    if elevation_feet is None:
        try:
            usgs_url_2 = "https://elevation.nationalmap.gov/arcgis/rest/services/3DEPElevation/ImageServer/identify"
            params = {
                'geometry': json.dumps({'x': lon, 'y': lat}),
                'geometryType': 'esriGeometryPoint',
                'returnGeometry': 'false',
                'f': 'json'
            }
            resp_2 = session.get(usgs_url_2, params=params, timeout=10)
            if resp_2.status_code == 200:
                val = resp_2.json().get('value')
                if val is not None and str(val).lower() != 'nodata':
                    elevation_feet = round(float(val) * 3.28084, 2) # ImageServer returns meters
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
        
        if c_epsg and pd.notna(c_epsg):
            try:
                gdf_county = gdf.to_crs(f'EPSG:{int(float(c_epsg))}')
                easting_county.append(gdf_county.geometry.x.values[0])
                northing_county.append(gdf_county.geometry.y.values[0])
                epsg_county.append(int(float(c_epsg)))
            except Exception:
                easting_county.append(None); northing_county.append(None); epsg_county.append(None)
        else:
            easting_county.append(None); northing_county.append(None); epsg_county.append(None)
            
    output_df['Easting_State_Plane_ft'] = [round(x, 2) if x is not None else None for x in easting_state]
    output_df['Northing_State_Plane_ft'] = [round(y, 2) if y is not None else None for y in northing_state]
    output_df['State_Plane_Zone'] = ['East' if e == INDIANA_STATE_PLANE['EAST'] else 'West' for e in epsg_state]
    output_df['State_Plane_EPSG'] = epsg_state
    
    output_df['Easting_County_ft'] = [round(x, 2) if x is not None else None for x in easting_county]
    output_df['Northing_County_ft'] = [round(y, 2) if y is not None else None for y in northing_county]
    output_df['County_EPSG'] = epsg_county
    
    return output_df

# ============================================================================
# STREAMLIT UI
