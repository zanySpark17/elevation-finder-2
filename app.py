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
@st.cache_data
def load_county_epsg_codes() -> Dict[str, str]:
    """Load Indiana County EPSG codes robustly from CSV file"""
    csv_path = 'indiana_county_epsg.csv'
    try:
        df = pd.read_csv(csv_path)
        df.columns = df.columns.str.strip()
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

# ============================================================================
# ORIGINAL COUNTY DETECTION LOGIC
# ============================================================================
def detect_county_simple(lat: float, lon: float) -> Optional[str]:
    """
    User's original simple county detection using coordinate ranges
    """
    county_bounds = {
        'LAKE': {'lat': (41.4, 41.8), 'lon': (-87.6, -87.2)},
        'PORTER': {'lat': (41.3, 41.7), 'lon': (-87.2, -86.8)},
        'LA_PORTE': {'lat': (41.3, 41.8), 'lon': (-86.8, -86.4)},
        'ST_JOSEPH': {'lat': (41.5, 41.8), 'lon': (-86.5, -86.1)},
        'ELKHART': {'lat': (41.4, 41.8), 'lon': (-86.1, -85.6)},
        'LAGRANGE': {'lat': (41.5, 41.8), 'lon': (-85.6, -85.2)},
        'STEUBEN': {'lat': (41.5, 41.8), 'lon': (-85.2, -84.8)},
        'ALLEN': {'lat': (40.9, 41.4), 'lon': (-85.3, -84.8)},
        'MARION': {'lat': (39.6, 40.0), 'lon': (-86.3, -85.9)},
        'HAMILTON': {'lat': (39.9, 40.2), 'lon': (-86.2, -85.8)},
        'HENDRICKS': {'lat': (39.7, 40.0), 'lon': (-86.7, -86.3)},
        'FRANKLIN': {'lat': (39.4, 39.7), 'lon': (-85.3, -84.9)},
        'HANCOCK': {'lat': (39.9, 40.2), 'lon': (-85.5, -85.1)},
        'JOHNSON': {'lat': (39.4, 39.7), 'lon': (-86.2, -85.8)},
        'SHELBY': {'lat': (39.5, 39.8), 'lon': (-85.8, -85.4)},
        'DECATUR': {'lat': (39.1, 39.4), 'lon': (-85.4, -85.0)},
        'RUSH': {'lat': (39.0, 39.3), 'lon': (-85.6, -85.2)},
        'FAYETTE': {'lat': (39.7, 40.0), 'lon': (-84.9, -84.5)},
        'UNION': {'lat': (39.7, 40.0), 'lon': (-85.0, -84.6)},
        'WAYNE': {'lat': (40.5, 40.8), 'lon': (-85.0, -84.6)},
        'RANDOLPH': {'lat': (40.2, 40.5), 'lon': (-85.2, -84.8)},
        'DELAWARE': {'lat': (40.1, 40.4), 'lon': (-85.2, -84.8)},
        'MADISON': {'lat': (40.2, 40.5), 'lon': (-85.6, -85.2)},
        'GRANT': {'lat': (40.3, 40.6), 'lon': (-85.8, -85.4)},
        'HOWARD': {'lat': (40.4, 40.7), 'lon': (-86.0, -85.6)},
        'TIPTON': {'lat': (40.2, 40.5), 'lon': (-85.8, -85.4)},
        'CASS': {'lat': (40.8, 41.1), 'lon': (-86.4, -86.0)},
        'CARROLL': {'lat': (40.5, 40.8), 'lon': (-86.4, -86.0)},
        'FULTON': {'lat': (41.0, 41.3), 'lon': (-86.5, -86.1)},
        'PULASKI': {'lat': (40.9, 41.2), 'lon': (-86.8, -86.4)},
        'MARSHALL': {'lat': (41.1, 41.4), 'lon': (-86.5, -86.1)},
        'KOSCIUSKO': {'lat': (41.0, 41.3), 'lon': (-85.8, -85.4)},
        'WHITLEY': {'lat': (41.1, 41.4), 'lon': (-85.5, -85.1)},
        'NOBLE': {'lat': (41.0, 41.3), 'lon': (-85.3, -84.9)},
        'DEKALB': {'lat': (41.2, 41.5), 'lon': (-85.2, -84.8)},
        'CLARK': {'lat': (38.3, 38.6), 'lon': (-85.8, -85.4)},
        'FLOYD': {'lat': (38.1, 38.4), 'lon': (-85.8, -85.4)},
        'JEFFERSON': {'lat': (38.6, 38.9), 'lon': (-85.7, -85.3)},
        'JENNINGS': {'lat': (38.6, 38.9), 'lon': (-85.5, -85.1)},
        'SCOTT': {'lat': (38.5, 38.8), 'lon': (-85.5, -85.1)},
        'WASHINGTON': {'lat': (38.5, 38.8), 'lon': (-86.0, -85.6)},
        'JACKSON': {'lat': (38.7, 39.0), 'lon': (-86.0, -85.6)},
        'LAWRENCE': {'lat': (38.9, 39.2), 'lon': (-86.6, -86.2)},
        'ORANGE': {'lat': (38.7, 39.0), 'lon': (-86.4, -86.0)},
        'MONROE': {'lat': (39.0, 39.3), 'lon': (-86.5, -86.1)},
        'BROWN': {'lat': (39.2, 39.5), 'lon': (-86.4, -86.0)},
        'MORGAN': {'lat': (39.5, 39.8), 'lon': (-86.5, -86.1)},
        'OWEN': {'lat': (39.1, 39.4), 'lon': (-86.8, -86.4)},
        'GREENE': {'lat': (38.9, 39.2), 'lon': (-87.0, -86.6)},
        'SULLIVAN': {'lat': (38.7, 39.0), 'lon': (-87.2, -86.8)},
        'KNOX': {'lat': (38.4, 38.7), 'lon': (-87.3, -86.9)},
        'GIBSON': {'lat': (38.1, 38.4), 'lon': (-87.5, -87.1)},
        'POSEY': {'lat': (37.9, 38.2), 'lon': (-87.8, -87.4)},
        'VANDERBURGH': {'lat': (37.8, 38.1), 'lon': (-87.6, -87.2)},
        'WARRICK': {'lat': (37.9, 38.2), 'lon': (-87.3, -86.9)},
        'DAVIESS': {'lat': (38.4, 38.7), 'lon': (-87.6, -87.2)},
        'MARTIN': {'lat': (38.5, 38.8), 'lon': (-87.3, -86.9)},
        'PIKE': {'lat': (38.3, 38.6), 'lon': (-87.5, -87.1)},
        'DUBOIS': {'lat': (38.4, 38.7), 'lon': (-86.8, -86.4)},
        'PERRY': {'lat': (37.9, 38.2), 'lon': (-86.5, -86.1)},
        'CRAWFORD': {'lat': (38.2, 38.5), 'lon': (-86.4, -86.0)},
        'HARRISON': {'lat': (38.3, 38.6), 'lon': (-85.8, -85.4)},
        'OHIO': {'lat': (38.5, 38.8), 'lon': (-84.8, -84.4)},
        'DEARBORN': {'lat': (39.0, 39.3), 'lon': (-85.0, -84.6)},
        'RIPLEY': {'lat': (38.8, 39.1), 'lon': (-85.2, -84.8)},
        'SWITZERLAND': {'lat': (38.8, 39.1), 'lon': (-84.9, -84.5)},
        'BARTHOLOMEW': {'lat': (39.1, 39.4), 'lon': (-85.6, -85.2)},
        'TIPPECANOE': {'lat': (40.3, 40.6), 'lon': (-86.9, -86.5)},
        'WARREN': {'lat': (40.5, 40.8), 'lon': (-87.2, -86.8)},
        'WHITE': {'lat': (40.4, 40.7), 'lon': (-87.2, -86.8)},
        'BENTON': {'lat': (40.6, 40.9), 'lon': (-87.6, -87.2)},
        'NEWTON': {'lat': (40.9, 41.2), 'lon': (-87.2, -86.8)},
        'JASPER': {'lat': (41.0, 41.3), 'lon': (-87.2, -86.8)},
        'STARKE': {'lat': (41.2, 41.5), 'lon': (-86.8, -86.4)},
        'CLAY': {'lat': (39.2, 39.5), 'lon': (-87.3, -86.9)},
        'PARKE': {'lat': (39.8, 40.1), 'lon': (-87.2, -86.8)},
        'VERMILLION': {'lat': (39.8, 40.1), 'lon': (-87.5, -87.1)},
        'VIGO': {'lat': (39.4, 39.7), 'lon': (-87.6, -87.2)},
        'FOUNTAIN': {'lat': (39.9, 40.2), 'lon': (-87.4, -87.0)},
        'CLINTON': {'lat': (40.1, 40.4), 'lon': (-86.6, -86.2)},
        'BOONE': {'lat': (39.9, 40.2), 'lon': (-86.7, -86.3)},
        'WABASH': {'lat': (40.7, 41.0), 'lon': (-85.8, -85.4)},
        'HUNTINGTON': {'lat': (40.8, 41.1), 'lon': (-85.5, -85.1)},
        'WELLS': {'lat': (40.7, 41.0), 'lon': (-85.1, -84.7)},
        'JAY': {'lat': (40.5, 40.8), 'lon': (-84.9, -84.5)},
        'ADAMS': {'lat': (40.6, 40.9), 'lon': (-84.8, -84.4)},
        'BLACKFORD': {'lat': (40.2, 40.5), 'lon': (-85.0, -84.6)},
        'HENRY': {'lat': (39.9, 40.2), 'lon': (-85.4, -85.0)}
    }
    
    for county, bounds in county_bounds.items():
        if (bounds['lat'][0] <= lat <= bounds['lat'][1] and 
            bounds['lon'][0] <= lon <= bounds['lon'][1]):
            return county
    
    return None

# ============================================================================
# FIXED USGS ELEVATION API
# ============================================================================
def get_robust_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def fetch_elevation_usgs(lat: float, lon: float, session: requests.Session) -> Optional[float]:
    """Fetches Elevation using the reliable USGS EPQS endpoint."""
    try:
        url = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&wkid=4326&includeDate=false"
        resp = session.get(url, timeout=10)
        if resp.status_code == 200:
            val = resp.json().get('value')
            if val is not None and str(val).strip() != '' and str(val).lower() != 'nodata':
                return round(float(val), 2)
    except Exception:
        pass
    return None

def get_batch_elevations(points: List[Tuple[float, float]]) -> List[Optional[float]]:
    results = []
    session = get_robust_session()
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_index = {
            executor.submit(fetch_elevation_usgs, lat, lon, session): i 
            for i, (lat, lon) in enumerate(points)
        }
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                results.append((idx, future.result()))
            except Exception:
                results.append((idx, None))
    results.sort(key=lambda x: x[0])
    return [res for _, res in results]

# ============================================================================
# TRANSFORMATION
# ============================================================================
def get_state_plane_zone(county_name: str) -> int:
    if not county_name: return INDIANA_STATE_PLANE['EAST']
    east_counties = {
        'ADAMS', 'ALLEN', 'BARTHOLOMEW', 'BLACKFORD', 'BROWN', 'CASS', 'CLARK', 'DEKALB', 
        'DEARBORN', 'DECATUR', 'DELAWARE', 'ELKHART', 'FAYETTE', 'FLOYD', 'FRANKLIN', 
        'FULTON', 'GRANT', 'HAMILTON', 'HANCOCK', 'HARRISON', 'HENRY', 'HOWARD', 
        'HUNTINGTON', 'JACKSON', 'JAY', 'JEFFERSON', 'JENNINGS', 'JOHNSON', 'KOSCIUSKO', 
        'LAGRANGE', 'MADISON', 'MARION', 'MARSHALL', 'MIAMI', 'NOBLE', 'OHIO', 'RANDOLPH', 
        'RIPLEY', 'RUSH', 'SCOTT', 'SHELBY', 'ST_JOSEPH', 'STEUBEN', 'SWITZERLAND', 
        'TIPTON', 'UNION', 'WABASH', 'WASHINGTON', 'WAYNE', 'WELLS', 'WHITLEY'
    }
    return INDIANA_STATE_PLANE['EAST'] if county_name in east_counties else INDIANA_STATE_PLANE['WEST']

def transform_coordinates_complete(df: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    output_df = pd.DataFrame()
    output_df['ID'] = df.iloc[:, 0] if len(df.columns) > 0 else range(1, len(df) + 1)
    output_df['Latitude_WGS84'] = df[lat_col].round(6)
    output_df['Longitude_WGS84'] = df[lon_col].round(6)
    
    # 1. User's Original County Detection
    detected_counties = []
    for idx, row in df.iterrows():
        county = detect_county_simple(row[lat_col], row[lon_col])
        detected_counties.append(county if county else 'UNKNOWN')
    output_df['County_Detected'] = detected_counties
    
    # 2. Fixed API Elevation Fetch
    points = list(zip(df[lat_col], df[lon_col]))
    output_df['Elevation_Feet'] = get_batch_elevations(points)
    
    # 3. GeoPandas Coordinate Conversion
    easting_state, northing_state, epsg_state = [], [], []
    easting_county, northing_county, epsg_county = [], [], []
    
    for idx, row in df.iterrows():
        lat, lon = row[lat_col], row[lon_col]
        county = detected_counties[idx]
        
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
            
        # County Specific
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
            
            lat_candidates = [c for c in df.columns if 'lat' in c.lower()]
            lon_candidates = [c for c in df.columns if 'lon' in c.lower()]
            
            if not lat_candidates or not lon_candidates:
                st.error("❌ Could not find columns containing 'lat' or 'lon' in the CSV.")
                return
                
            lat_col = lat_candidates[0]
            lon_col = lon_candidates[0]
            
            with st.spinner("Processing..."):
                result_df = transform_coordinates_complete(df, lat_col, lon_col)
                st.dataframe(result_df, use_container_width=True)
                
                st.download_button(
                    label="💾 Download Results (CSV)",
                    data=result_df.to_csv(index=False),
                    file_name="indiana_transformation_results.csv",
                    mime="text/csv", type="primary"
                )

if __name__ == "__main__":
    main()
