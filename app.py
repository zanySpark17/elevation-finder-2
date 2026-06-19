import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import io
from typing import Dict, Optional, Tuple, List
import requests
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

# Custom CSS for professional design
st.markdown("""
    <style>
        .main {
            padding-top: 0rem;
        }
        .header-container {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 2rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .header-container h1 {
            margin: 0;
            font-size: 2.5rem;
        }
        .header-container p {
            margin: 0.5rem 0 0 0;
            font-size: 1rem;
            opacity: 0.9;
        }
        .metric-card {
            background: #f0f2f6;
            padding: 1rem;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .success-box {
            background: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
        .info-box {
            background: #cfe2ff;
            border: 1px solid #b6d4fe;
            color: #084298;
            padding: 1rem;
            border-radius: 8px;
            margin: 1rem 0;
        }
    </style>
""", unsafe_allow_html=True)

# ============================================================================
# LOAD EPSG CODES FROM CSV
# ============================================================================

@st.cache_data
def load_county_epsg_codes():
    """Load Indiana County EPSG codes from CSV file"""
    csv_path = 'indiana_county_epsg.csv'
    
    try:
        df = pd.read_csv(csv_path)
        epsg_dict = dict(zip(df['County'], df['EPSG_Code']))
        return epsg_dict
    except FileNotFoundError:
        st.error(f"❌ CRITICAL: '{csv_path}' not found! Please upload this file.")
        return {}

INDIANA_COUNTY_EPSG = load_county_epsg_codes()

# Indiana State Plane Coordinate System EPSG codes
INDIANA_STATE_PLANE = {
    'EAST': 2965,   # NAD83 / Indiana East (ftUS)
    'WEST': 2966    # NAD83 / Indiana West (ftUS)
}

# ============================================================================
# USGS ELEVATION API
# ============================================================================

def get_elevation_from_usgs(latitude: float, longitude: float) -> Optional[float]:
    """
    Fetch elevation data from USGS 3DEP API
    Returns elevation in meters
    """
    try:
        # USGS 3DEP Elevation Point Query Service
        url = "https://epqs.nationalmap.gov/v1/json"
        
        params = {
            "x": longitude,
            "y": latitude,
            "units": "Feet",
            "output": "json"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        if 'value' in data:
            return round(float(data['value']),2)
        else:
            return None
            
    except Exception as e:
        return None

def get_elevation_batch(points: List[Tuple[float, float]], max_workers: int = 5) -> List[Optional[float]]:
    """
    Fetch elevations for multiple points concurrently
    """
    elevations = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(get_elevation_from_usgs, lat, lon): i 
            for i, (lat, lon) in enumerate(points)
        }
        
        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                elevation = future.result()
                elevations.append((idx, elevation))
            except Exception as e:
                elevations.append((idx, None))
    
    # Sort by original index
    elevations.sort(key=lambda x: x[0])
    return [elev for _, elev in elevations]

# ============================================================================
# COUNTY DETECTION
# ============================================================================

def detect_county_simple(lat: float, lon: float) -> Optional[str]:
    """
    Simple county detection using coordinate ranges
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
        'HENRY': {'lat': (39.9, 40.2), 'lon': (-85.4, -85.0)},
        'WAYNE': {'lat': (40.5, 40.8), 'lon': (-85.0, -84.6)},
        'OHIO': {'lat': (38.5, 38.8), 'lon': (-84.8, -84.4)},
    }
    
    for county, bounds in county_bounds.items():
        if (bounds['lat'][0] <= lat <= bounds['lat'][1] and 
            bounds['lon'][0] <= lon <= bounds['lon'][1]):
            return county
    
    return None

def get_state_plane_zone(county_name: str) -> int:
    """Determine which Indiana State Plane zone a county belongs to"""
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
    
    county_upper = county_name.upper().replace(' ', '_')
    return INDIANA_STATE_PLANE['EAST'] if county_upper in east_counties else INDIANA_STATE_PLANE['WEST']

# ============================================================================
# COORDINATE TRANSFORMATION
# ============================================================================

def transform_coordinates_complete(df: pd.DataFrame, lat_col: str, lon_col: str) -> pd.DataFrame:
    """
    Complete transformation pipeline:
    1. Auto-detect county
    2. Get elevation from USGS
    3. Transform to State Plane
    4. Transform to County-specific coordinates
    """
    
    # Initialize output DataFrame
    output_df = pd.DataFrame()
    output_df['ID'] = df.iloc[:, 0] if len(df.columns) > 0 else range(1, len(df) + 1)
    output_df['Latitude_WGS84'] = df[lat_col].round(6)
    output_df['Longitude_WGS84'] = df[lon_col].round(6)
    
    # Auto-detect counties
    detected_counties = []
    for idx, row in df.iterrows():
        county = detect_county_simple(row[lat_col], row[lon_col])
        detected_counties.append(county if county else 'UNKNOWN')
    output_df['County_Detected'] = detected_counties
    
    # Fetch elevations (with progress indicator)
    points = list(zip(df[lat_col], df[lon_col]))
    elevations = get_elevation_batch(points)
    output_df['Elevation_Feet'] = elevations
    
    # Transform coordinates for each point
    easting_state = []
    northing_state = []
    easting_county = []
    northing_county = []
    county_names = []
    epsg_state = []
    epsg_county = []
    
    for idx, row in df.iterrows():
        lat, lon = row[lat_col], row[lon_col]
        detected_county = detected_counties[idx]
        
        # Create geometry
        geometry = gpd.points_from_xy([lon], [lat], crs='EPSG:4326')
        gdf = gpd.GeoDataFrame([1], geometry=geometry, crs='EPSG:4326')
        
        # Transform to State Plane
        state_plane_epsg = get_state_plane_zone(detected_county)
        gdf_state = gdf.to_crs(f'EPSG:{state_plane_epsg}')
        
        easting_state.append(gdf_state.geometry.x.values[0])
        northing_state.append(gdf_state.geometry.y.values[0])
        epsg_state.append(state_plane_epsg)
        
        # Transform to County coordinates
        county_epsg = INDIANA_COUNTY_EPSG.get(detected_county)
        
        if county_epsg:
            try:
                gdf_county = gdf.to_crs(f'EPSG:{county_epsg}')
                easting_county.append(gdf_county.geometry.x.values[0])
                northing_county.append(gdf_county.geometry.y.values[0])
                epsg_county.append(county_epsg)
            except:
                easting_county.append(None)
                northing_county.append(None)
                epsg_county.append(None)
        else:
            easting_county.append(None)
            northing_county.append(None)
            epsg_county.append(None)
        
        county_names.append(detected_county)
    
    # Add transformation results
    zone_names = ['East' if epsg == INDIANA_STATE_PLANE['EAST'] else 'West' for epsg in epsg_state]
    
    output_df['Easting_State_Plane_ft'] = [round(x, 2) if x else None for x in easting_state]
    output_df['Northing_State_Plane_ft'] = [round(y, 2) if y else None for y in northing_state]
    output_df['State_Plane_Zone'] = zone_names
    output_df['State_Plane_EPSG'] = epsg_state
    
    output_df['Easting_County_ft'] = [round(x, 2) if x else None for x in easting_county]
    output_df['Northing_County_ft'] = [round(y, 2) if y else None for y in northing_county]
    output_df['County_EPSG'] = epsg_county
    
    return output_df

# ============================================================================
# STREAMLIT UI - MAIN APP
# ============================================================================

def main():
    # Header
    st.markdown("""
        <div class="header-container">
            <h1>🗺️ Indiana Coordinate & Elevation Transformer</h1>
            <p>Automatic county detection • State Plane conversion • USGS elevation data</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Check if EPSG codes loaded
    if not INDIANA_COUNTY_EPSG:
        st.error("❌ CRITICAL ERROR: indiana_county_epsg.csv not found or empty!")
        st.info("Please ensure indiana_county_epsg.csv is in the same directory as app.py")
        return
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        mode = st.radio(
            "Select Input Mode:",
            ["📁 Upload CSV", "✍️ Manual Entry"],
            index=0
        )
        
        st.markdown("---")
        
        st.info("""
        **This app automatically:**
        ✅ Detects which Indiana county each point is in
        ✅ Converts to State Plane coordinates
        ✅ Converts to county-specific coordinates
        ✅ Fetches elevation from USGS
        
        **No manual input needed!**
        """)
    
    # Main content
    if "📁 Upload CSV" in mode:
        show_csv_mode()
    else:
        show_manual_mode()

def show_csv_mode():
    """CSV upload interface"""
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
            data=pd.DataFrame({
                'ID': ['Point1', 'Point2'],
                'Latitude': [39.7684, 39.1653],
                'Longitude': [-86.1581, -86.5264]
            }).to_csv(index=False),
            file_name="template.csv",
            mime="text/csv"
        )
    
    uploaded_file = st.file_uploader(
        "Choose CSV file",
        type=['csv'],
        help="Upload CSV with lat/lon coordinates"
    )
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ Loaded: {len(df)} rows, {len(df.columns)} columns")
            
            # Auto-detect columns
            df_cols = df.columns.tolist()
            lat_candidates = [col for col in df_cols if 'lat' in col.lower()]
            lon_candidates = [col for col in df_cols if any(k in col.lower() for k in ['long', 'lon'])]
            
            if not lat_candidates or not lon_candidates:
                st.error("❌ Could not find latitude/longitude columns")
                return
            
            lat_col = lat_candidates[0]
            lon_col = lon_candidates[0]
            
            # Preview
            with st.expander("👁️ Preview Data", expanded=False):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Process button
            if st.button("🚀 Process & Transform", type="primary", use_container_width=True):
                
                # Clean data
                df_clean = df.copy()
                df_clean[lat_col] = pd.to_numeric(
                    df_clean[lat_col].astype(str).str.replace('°', '').str.strip(),
                    errors='coerce'
                )
                df_clean[lon_col] = pd.to_numeric(
                    df_clean[lon_col].astype(str).str.replace('°', '').str.strip(),
                    errors='coerce'
                )
                
                df_clean = df_clean.dropna(subset=[lat_col, lon_col])
                
                if len(df_clean) == 0:
                    st.error("❌ No valid coordinates found!")
                    return
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("🔄 Transforming coordinates and fetching elevations..."):
                    status_text.text("📍 Detecting counties...")
                    progress_bar.progress(20)
                    
                    status_text.text("📡 Fetching elevation data from USGS...")
                    progress_bar.progress(50)
                    
                    result_df = transform_coordinates_complete(df_clean, lat_col, lon_col)
                    
                    status_text.text("✅ Transformation complete!")
                    progress_bar.progress(100)
                
                time.sleep(0.5)
                progress_bar.empty()
                status_text.empty()
                
                # Display results
                st.markdown("---")
                st.subheader("📊 Transformation Results")
                
                # Show stats
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total Points", len(result_df))
                with col2:
                    successful = result_df['County_Detected'].notna().sum()
                    st.metric("Counties Detected", successful)
                with col3:
                    with_elevation = result_df['Elevation_Feet'].notna().sum()
                    st.metric("Elevations Found", with_elevation)
                with col4:
                    with_county_coords = result_df['County_EPSG'].notna().sum()
                    st.metric("County Coords", with_county_coords)
                
                st.markdown("---")
                
                # Results table
                st.dataframe(result_df, use_container_width=True)
                
                # Download results
                csv_data = result_df.to_csv(index=False)
                st.download_button(
                    label="💾 Download Results (CSV)",
                    data=csv_data,
                    file_name="indiana_transformation_results.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True
                )
                
                # Summary
                st.markdown("---")
                st.subheader("📋 Summary")
                
                counties_used = result_df['County_Detected'].value_counts()
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Counties Detected:**")
                    st.dataframe(counties_used, use_container_width=True)
                
                with col2:
                    st.markdown("**Elevation Statistics:**")
                    elev_data = result_df['Elevation_Feet'].dropna()
                    if len(elev_data) > 0:
                        stats = {
                            'Min': f"{elev_data.min():.0f} ft",
                            'Max': f"{elev_data.max():.0f} ft",
                            'Average': f"{elev_data.mean():.0f} ft",
                            'Std Dev': f"{elev_data.std():.0f} ft"
                        }
                        for key, val in stats.items():
                            st.text(f"{key}: {val}")
                    else:
                        st.warning("No elevation data retrieved")
                
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")

def show_manual_mode():
    """Manual entry interface"""
    st.subheader("✍️ Manual Coordinate Entry")
    
    num_points = st.number_input(
        "Number of points:",
        min_value=1,
        max_value=20,
        value=1
    )
    
    data = []
    
    for i in range(int(num_points)):
        st.markdown(f"**Point {i+1}**")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            point_id = st.text_input(
                f"ID",
                value=f"Point_{i+1}",
                key=f"id_{i}"
            )
        
        with col2:
            lat = st.number_input(
                f"Latitude",
                value=39.7684 if i == 0 else 0.0,
                format="%.6f",
                key=f"lat_{i}"
            )
        
        with col3:
            lon = st.number_input(
                f"Longitude",
                value=-86.1581 if i == 0 else 0.0,
                format="%.6f",
                key=f"lon_{i}"
            )
        
        if lat != 0.0 or lon != 0.0:
            data.append({'ID': point_id, 'Latitude': lat, 'Longitude': lon})
    
    if st.button("🚀 Process & Transform", type="primary", use_container_width=True):
        if not data:
            st.warning("⚠️ Please enter at least one coordinate pair")
            return
        
        with st.spinner("🔄 Transforming coordinates and fetching elevations..."):
            df_manual = pd.DataFrame(data)
            result_df = transform_coordinates_complete(df_manual, 'Latitude', 'Longitude')
        
        st.markdown("---")
        st.subheader("📊 Transformation Results")
        st.dataframe(result_df, use_container_width=True)
        
        csv_data = result_df.to_csv(index=False)
        st.download_button(
            label="💾 Download Results",
            data=csv_data,
            file_name="indiana_manual_transformation.csv",
            mime="text/csv",
            type="primary",
            use_container_width=True
        )

if __name__ == "__main__":
    main()


@st.cache_data
def detect_county_simple(lat, lon):
    try:
        r=requests.get(
            "https://geo.fcc.gov/api/census/block/find",
            params={"latitude":lat,"longitude":lon,"format":"json"},
            timeout=10
        )
        data=r.json()
        county=data.get("County",{}).get("name","")
        return county.upper().replace(" COUNTY","").replace(" ","_")
    except:
        return None
