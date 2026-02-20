import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import io
from typing import Dict, Optional, Tuple
import requests
import json

# Set page config
st.set_page_config(
    page_title="Indiana Coordinate Transformer",
    page_icon="🗺️",
    layout="wide"
)

# Indiana State Plane Coordinate System EPSG codes
INDIANA_STATE_PLANE = {
    'EAST': 2965,   # NAD83 / Indiana East (ftUS)
    'WEST': 2966    # NAD83 / Indiana West (ftUS)
}

def load_county_epsg_codes():
    """
    Load Indiana County EPSG codes from CSV file
    This allows manual verification and updates without changing code
    """
    csv_path = 'indiana_county_epsg.csv'
    
    try:
        # Try to load from file
        df = pd.read_csv(csv_path)
        epsg_dict = dict(zip(df['County'], df['EPSG_Code']))
        return epsg_dict
    except FileNotFoundError:
        # Fallback to original codes from your code if CSV not found
        st.warning(f"⚠️ Could not find '{csv_path}'. Using default EPSG codes. Please add the CSV file to verify codes.")
        return {
            'ADAMS': 7301, 'ALLEN': 7260, 'BARTHOLOMEW': 7303, 'BLACKFORD': 7304,
            'BROWN': 7305, 'CASS': 7306, 'CLARK': 7307, 'DEKALB': 7308,
            'DEARBORN': 7309, 'DECATUR': 7310, 'DELAWARE': 7266, 'ELKHART': 7300,
            'FAYETTE': 7313, 'FLOYD': 7314, 'FRANKLIN': 7315, 'FULTON': 7300,
            'GRANT': 7316, 'HAMILTON': 7317, 'HANCOCK': 7308, 'HARRISON': 7319,
            'HENRY': 7312, 'HOWARD': 7320, 'HUNTINGTON': 7321, 'JACKSON': 7322,
            'JAY': 7323, 'JEFFERSON': 7324, 'JENNINGS': 7325, 'JOHNSON': 7326,
            'KOSCIUSKO': 7327, 'LAGRANGE': 7328, 'MADISON': 7329, 'MARION': 7330,
            'MARSHALL': 7300, 'MIAMI': 7331, 'NOBLE': 7332, 'OHIO': 7333,
            'RANDOLPH': 7334, 'RIPLEY': 7354, 'RUSH': 7335, 'SCOTT': 7336,
            'SHELBY': 7337, 'ST_JOSEPH': 7300, 'STEUBEN': 7338, 'SWITZERLAND': 7339,
            'TIPTON': 7340, 'UNION': 7341, 'WABASH': 7342, 'WASHINGTON': 7343,
            'WAYNE': 7352, 'WELLS': 7344, 'WHITLEY': 7345, 'BENTON': 7346,
            'BOONE': 7268, 'CARROLL': 7348, 'CLAY': 7349, 'CLINTON': 7350,
            'CRAWFORD': 7351, 'DAVIESS': 7355, 'DUBOIS': 7356, 'FOUNTAIN': 7357,
            'GIBSON': 7358, 'GREENE': 7359, 'HENDRICKS': 7268, 'JASPER': 7320,
            'KNOX': 7361, 'LA_PORTE': 7362, 'LAKE': 7363, 'LAWRENCE': 7364,
            'MARTIN': 7365, 'MONROE': 7366, 'MONTGOMERY': 7340, 'MORGAN': 7368,
            'NEWTON': 7369, 'ORANGE': 7370, 'OWEN': 7371, 'PARKE': 7372,
            'PERRY': 9774, 'PIKE': 7348, 'PORTER': 7375, 'POSEY': 7376,
            'PULASKI': 7377, 'PUTNAM': 7378, 'SPENCER': 7379, 'STARKE': 7380,
            'SULLIVAN': 7381, 'TIPPECANOE': 7382, 'VANDERBURGH': 7383,
            'VERMILLION': 7384, 'VIGO': 7385, 'WARREN': 7386, 'WARRICK': 7387
        }

# Load EPSG codes from CSV file (editable by user)
INDIANA_COUNTY_EPSG = load_county_epsg_codes()

# Mapping from display names to internal keys
COUNTY_NAME_MAPPING = {
    'La Porte': 'LA_PORTE',
    'St Joseph': 'ST_JOSEPH',
    'Saint Joseph': 'ST_JOSEPH'
}

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
    county_upper = COUNTY_NAME_MAPPING.get(county_name, county_upper)
    
    return INDIANA_STATE_PLANE['EAST'] if county_upper in east_counties else INDIANA_STATE_PLANE['WEST']


def load_indiana_counties_geojson():
    """Load Indiana county boundaries from a GeoJSON source"""
    # This uses the US Census Bureau's county boundary data
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    
    try:
        response = requests.get(url, timeout=10)
        geojson_data = response.json()
        
        # Filter for Indiana counties (FIPS code starts with '18')
        indiana_features = [
            feature for feature in geojson_data['features']
            if feature['properties']['STATE'] == '18'
        ]
        
        # Create a new GeoJSON with only Indiana counties
        indiana_geojson = {
            'type': 'FeatureCollection',
            'features': indiana_features
        }
        
        # Convert to GeoDataFrame
        gdf = gpd.GeoDataFrame.from_features(indiana_geojson['features'], crs='EPSG:4326')
        
        # Add county names from FIPS codes
        fips_to_county = get_indiana_fips_mapping()
        gdf['COUNTY_NAME'] = gdf['GEO_ID'].apply(lambda x: fips_to_county.get(x.split('US')[1], 'Unknown'))
        
        return gdf
    except Exception as e:
        st.error(f"Could not load county boundaries: {str(e)}")
        return None


def get_indiana_fips_mapping():
    """Map FIPS codes to Indiana county names"""
    return {
        '18001': 'ADAMS', '18003': 'ALLEN', '18005': 'BARTHOLOMEW', '18007': 'BENTON',
        '18009': 'BLACKFORD', '18011': 'BOONE', '18013': 'BROWN', '18015': 'CARROLL',
        '18017': 'CASS', '18019': 'CLARK', '18021': 'CLAY', '18023': 'CLINTON',
        '18025': 'CRAWFORD', '18027': 'DAVIESS', '18029': 'DEARBORN', '18031': 'DECATUR',
        '18033': 'DEKALB', '18035': 'DELAWARE', '18037': 'DUBOIS', '18039': 'ELKHART',
        '18041': 'FAYETTE', '18043': 'FLOYD', '18045': 'FOUNTAIN', '18047': 'FRANKLIN',
        '18049': 'FULTON', '18051': 'GIBSON', '18053': 'GRANT', '18055': 'GREENE',
        '18057': 'HAMILTON', '18059': 'HANCOCK', '18061': 'HARRISON', '18063': 'HENDRICKS',
        '18065': 'HENRY', '18067': 'HOWARD', '18069': 'HUNTINGTON', '18071': 'JACKSON',
        '18073': 'JASPER', '18075': 'JAY', '18077': 'JEFFERSON', '18079': 'JENNINGS',
        '18081': 'JOHNSON', '18083': 'KNOX', '18085': 'KOSCIUSKO', '18087': 'LAGRANGE',
        '18089': 'LAKE', '18091': 'LA_PORTE', '18093': 'LAWRENCE', '18095': 'MADISON',
        '18097': 'MARION', '18099': 'MARSHALL', '18101': 'MARTIN', '18103': 'MIAMI',
        '18105': 'MONROE', '18107': 'MONTGOMERY', '18109': 'MORGAN', '18111': 'NEWTON',
        '18113': 'NOBLE', '18115': 'OHIO', '18117': 'ORANGE', '18119': 'OWEN',
        '18121': 'PARKE', '18123': 'PERRY', '18125': 'PIKE', '18127': 'PORTER',
        '18129': 'POSEY', '18131': 'PULASKI', '18133': 'PUTNAM', '18135': 'RANDOLPH',
        '18137': 'RIPLEY', '18139': 'RUSH', '18141': 'SCOTT', '18143': 'SHELBY',
        '18145': 'SPENCER', '18141': 'ST_JOSEPH', '18149': 'STARKE', '18151': 'STEUBEN',
        '18153': 'SULLIVAN', '18155': 'SWITZERLAND', '18157': 'TIPPECANOE', '18159': 'TIPTON',
        '18161': 'UNION', '18163': 'VANDERBURGH', '18165': 'VERMILLION', '18167': 'VIGO',
        '18169': 'WABASH', '18171': 'WARREN', '18173': 'WARRICK', '18175': 'WASHINGTON',
        '18177': 'WAYNE', '18179': 'WELLS', '18181': 'WHITE', '18183': 'WHITLEY'
    }


def detect_county_simple(lat: float, lon: float) -> Optional[str]:
    """
    Simpler county detection using coordinate ranges
    This is a fallback method that doesn't require downloading boundary files
    """
    # Create county boundary approximations based on lat/lon ranges
    # This is simplified but works for most cases
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
        # Add more counties as needed
    }
    
    for county, bounds in county_bounds.items():
        if (bounds['lat'][0] <= lat <= bounds['lat'][1] and 
            bounds['lon'][0] <= lon <= bounds['lon'][1]):
            return county
    
    return None


def detect_county_from_coordinates(lat: float, lon: float) -> Optional[str]:
    """Detect which Indiana county a coordinate falls within"""
    
    # First try simple detection
    county = detect_county_simple(lat, lon)
    if county:
        return county
    
    # If simple detection fails, try to use the GeoJSON method
    if 'county_boundaries' not in st.session_state:
        with st.spinner('Loading Indiana county boundaries...'):
            st.session_state.county_boundaries = load_indiana_counties_geojson()
    
    if st.session_state.county_boundaries is None:
        return None
    
    gdf = st.session_state.county_boundaries
    point = Point(lon, lat)
    point_gdf = gpd.GeoDataFrame([1], geometry=[point], crs='EPSG:4326')
    
    # Spatial join to find which county contains the point
    result = gpd.sjoin(point_gdf, gdf, how='left', predicate='within')
    
    if not result.empty and 'COUNTY_NAME' in result.columns:
        county_name = result.iloc[0]['COUNTY_NAME']
        if pd.notna(county_name):
            return county_name
    
    return None


def transform_coordinates(df: pd.DataFrame, lat_col: str, lon_col: str, 
                         county_name: Optional[str] = None, auto_detect: bool = False) -> pd.DataFrame:
    """Transform coordinates with optional auto-detection of county"""
    
    # Normalize county name
    if county_name:
        county_upper = county_name.upper().replace(' ', '_')
        county_upper = COUNTY_NAME_MAPPING.get(county_name, county_upper)
    
    # Create GeoDataFrame
    geometry = gpd.points_from_xy(df[lon_col], df[lat_col])
    gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
    
    # Prepare output DataFrame
    output_df = pd.DataFrame()
    output_df['ID'] = df.iloc[:, 0] if len(df.columns) > 0 else range(1, len(df) + 1)
    output_df['Latitude_WGS84'] = df[lat_col].round(6)
    output_df['Longitude_WGS84'] = df[lon_col].round(6)
    
    # Auto-detect county if requested
    if auto_detect:
        detected_counties = []
        for idx, row in df.iterrows():
            county = detect_county_from_coordinates(row[lat_col], row[lon_col])
            detected_counties.append(county if county else 'Unknown')
        output_df['Detected_County'] = detected_counties
    
    # Transform to State Plane
    if county_name or not auto_detect:
        target_county = county_name if county_name else 'MARION'  # Default to Marion
        state_plane_epsg = get_state_plane_zone(target_county)
        gdf_state_plane = gdf.to_crs(f'EPSG:{state_plane_epsg}')
        
        zone_name = "East" if state_plane_epsg == INDIANA_STATE_PLANE['EAST'] else "West"
        output_df[f'Easting_Indiana_{zone_name}_ft'] = gdf_state_plane.geometry.x.round(2)
        output_df[f'Northing_Indiana_{zone_name}_ft'] = gdf_state_plane.geometry.y.round(2)
        output_df['State_Plane_Zone'] = zone_name
        output_df['State_Plane_EPSG'] = state_plane_epsg
        
        # Transform to County coordinates
        county_epsg = INDIANA_COUNTY_EPSG.get(county_upper)
        if county_epsg:
            gdf_county = gdf.to_crs(f'EPSG:{county_epsg}')
            county_formatted = target_county.replace("_", " ").title()
            output_df[f'Easting_{county_formatted}_ft'] = gdf_county.geometry.x.round(2)
            output_df[f'Northing_{county_formatted}_ft'] = gdf_county.geometry.y.round(2)
            output_df['County_EPSG'] = county_epsg
    
    return output_df


# Streamlit UI
def main():
    st.title("🗺️ Indiana Coordinate Transformation Tool")
    st.markdown("**Convert WGS84 (Lat/Lon) to Indiana State Plane & County Coordinate Systems**")
    st.markdown("*By: Laith Sadik, PhD, PE*")
    
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Settings")
        
        mode = st.radio(
            "Select Input Mode:",
            ["📁 Upload CSV File", "✍️ Manual Entry"],
            index=0
        )
        
        st.markdown("---")
        
        auto_detect = st.checkbox(
            "🔍 Auto-detect County", 
            value=True,
            help="Automatically detect which county each coordinate falls within"
        )
        
        if not auto_detect:
            county_options = sorted([county.replace('_', ' ').title() 
                                   for county in INDIANA_COUNTY_EPSG.keys()])
            selected_county = st.selectbox(
                "Select County:",
                county_options,
                index=county_options.index('Marion')
            )
        else:
            selected_county = None
        
        st.markdown("---")
        st.info("""
        **Coordinate Systems:**
        - Input: WGS84 (EPSG:4326)
        - State Plane: NAD83 Indiana East/West
        - County: InGCS (Indiana Geospatial Coordinate System)
        """)
        
        # Show EPSG code verification status
        with st.expander("📊 EPSG Code Status", expanded=False):
            try:
                csv_df = pd.read_csv('indiana_county_epsg.csv')
                verified_count = csv_df[csv_df['Verified'] == 'Yes'].shape[0]
                total_count = csv_df.shape[0]
                
                st.metric("Verified Codes", f"{verified_count}/{total_count}")
                
                if verified_count < total_count:
                    st.warning(f"⚠️ {total_count - verified_count} codes need verification")
                    st.caption("Edit 'indiana_county_epsg.csv' to verify codes using epsg.io")
                else:
                    st.success("✅ All codes verified!")
                    
            except FileNotFoundError:
                st.warning("CSV file not found. Using default codes.")
    
    # Main content area
    if "📁 Upload CSV File" in mode:
        show_file_upload(auto_detect, selected_county)
    else:
        show_manual_entry(auto_detect, selected_county)


def show_file_upload(auto_detect: bool, selected_county: Optional[str]):
    """Display file upload interface"""
    
    st.subheader("📂 Upload CSV File")
    
    with st.expander("ℹ️ CSV File Requirements", expanded=False):
        st.markdown("""
        Your CSV should contain:
        - A column with latitude values (column name containing 'lat')
        - A column with longitude values (column name containing 'lon' or 'long')
        - Optional: ID column (containing 'id', 'point', 'boring', or 'name')
        - Coordinates can include degree symbols (°) - they will be cleaned automatically
        
        **Example format:**
        ```
        ID,Latitude,Longitude
        Point1,39.7684,-86.1581
        Point2,39.7740,-86.1496
        ```
        """)
    
    uploaded_file = st.file_uploader(
        "Choose a CSV file",
        type=['csv'],
        help="Upload a CSV file with latitude and longitude coordinates"
    )
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            
            st.success(f"✅ File loaded: {len(df)} rows, {len(df.columns)} columns")
            
            # Show preview
            with st.expander("👁️ Preview Data", expanded=True):
                st.dataframe(df.head(10), use_container_width=True)
            
            # Find columns
            df_cols = df.columns.tolist()
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Find ID column
                id_candidates = [col for col in df_cols 
                               if any(keyword in col.lower() 
                                     for keyword in ['id', 'boring', 'point', 'name'])]
                id_col = st.selectbox(
                    "ID Column:",
                    [df_cols[0]] + id_candidates if id_candidates else df_cols,
                    index=0
                )
            
            with col2:
                # Find Latitude column
                lat_candidates = [col for col in df_cols if 'lat' in col.lower()]
                lat_col = st.selectbox(
                    "Latitude Column:",
                    lat_candidates if lat_candidates else df_cols,
                    index=0 if lat_candidates else None
                )
            
            with col3:
                # Find Longitude column
                lon_candidates = [col for col in df_cols 
                                if any(keyword in col.lower() 
                                      for keyword in ['long', 'lon'])]
                lon_col = st.selectbox(
                    "Longitude Column:",
                    lon_candidates if lon_candidates else df_cols,
                    index=0 if lon_candidates else None
                )
            
            if st.button("🔄 Transform Coordinates", type="primary"):
                with st.spinner("Transforming coordinates..."):
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
                    
                    # Remove invalid coordinates
                    df_clean = df_clean.dropna(subset=[lat_col, lon_col])
                    
                    if len(df_clean) == 0:
                        st.error("❌ No valid coordinates found after cleaning!")
                        return
                    
                    st.info(f"📊 Processing {len(df_clean)} valid coordinate pairs...")
                    
                    # Transform
                    result_df = transform_coordinates(
                        df_clean, lat_col, lon_col, 
                        selected_county, auto_detect
                    )
                    
                    st.success("✅ Transformation completed!")
                    
                    # Display results
                    st.subheader("📋 Results")
                    st.dataframe(result_df, use_container_width=True)
                    
                    # Download button
                    csv = result_df.to_csv(index=False)
                    filename = f"indiana_coordinates_transformed.csv"
                    
                    st.download_button(
                        label="💾 Download Results (CSV)",
                        data=csv,
                        file_name=filename,
                        mime="text/csv",
                        type="primary"
                    )
                    
        except Exception as e:
            st.error(f"❌ Error processing file: {str(e)}")


def show_manual_entry(auto_detect: bool, selected_county: Optional[str]):
    """Display manual entry interface"""
    
    st.subheader("✍️ Manual Coordinate Entry")
    
    num_points = st.number_input(
        "Number of points to enter:",
        min_value=1,
        max_value=20,
        value=3,
        step=1
    )
    
    st.markdown("### 📍 Enter Coordinates")
    
    data = []
    
    for i in range(int(num_points)):
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            point_id = st.text_input(
                f"Point {i+1} ID:",
                value=f"Point_{i+1}",
                key=f"id_{i}"
            )
        
        with col2:
            lat = st.number_input(
                f"Latitude:",
                value=0.0,
                format="%.6f",
                key=f"lat_{i}",
                help="Example: 39.7684"
            )
        
        with col3:
            lon = st.number_input(
                f"Longitude:",
                value=0.0,
                format="%.6f",
                key=f"lon_{i}",
                help="Example: -86.1581"
            )
        
        if lat != 0.0 and lon != 0.0:
            data.append({
                'ID': point_id,
                'Latitude': lat,
                'Longitude': lon
            })
    
    if st.button("🔄 Transform Coordinates", type="primary"):
        if not data:
            st.warning("⚠️ Please enter at least one valid coordinate pair!")
            return
        
        with st.spinner("Transforming coordinates..."):
            df_manual = pd.DataFrame(data)
            
            result_df = transform_coordinates(
                df_manual, 'Latitude', 'Longitude',
                selected_county, auto_detect
            )
            
            st.success("✅ Transformation completed!")
            
            # Display results
            st.subheader("📋 Results")
            st.dataframe(result_df, use_container_width=True)
            
            # Download button
            csv = result_df.to_csv(index=False)
            filename = "indiana_coordinates_manual_transformed.csv"
            
            st.download_button(
                label="💾 Download Results (CSV)",
                data=csv,
                file_name=filename,
                mime="text/csv",
                type="primary"
            )


if __name__ == "__main__":
    main()
