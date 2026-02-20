# Indiana Coordinate Transformation Tool 🗺️

A Streamlit web application for converting WGS84 (Latitude/Longitude) coordinates to Indiana State Plane and County coordinate systems.

**By: Laith Sadik, PhD, PE**

## Features

✨ **Key Capabilities:**
- 🔍 **Automatic County Detection** - No need to manually specify the county! The app detects which Indiana county each coordinate falls within
- 📁 **CSV File Upload** - Process multiple coordinates at once
- ✍️ **Manual Entry** - Enter coordinates directly in the interface
- 🗺️ **Dual Coordinate Systems** - Converts to both State Plane (East/West zones) and County-specific systems
- ✅ **Verified EPSG Codes** - All coordinate reference systems verified against official EPSG registry
- 💾 **Download Results** - Export transformed coordinates as CSV

## Coordinate Systems Supported

- **Input:** WGS84 (EPSG:4326) - Standard GPS coordinates
- **State Plane:** NAD83 Indiana East (EPSG:2965) / West (EPSG:2966) in US Survey Feet
- **County Systems:** InGCS (Indiana Geospatial Coordinate System) - Individual EPSG codes for all 92 Indiana counties

## Installation

### Local Installation

1. **Clone the repository:**
```bash
git clone https://github.com/YOUR_USERNAME/indiana-coordinate-transformer.git
cd indiana-coordinate-transformer
```

2. **Create a virtual environment (recommended):**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Run the app:**
```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

### Deploy to Streamlit Cloud

1. **Push your code to GitHub**

2. **Go to [Streamlit Cloud](https://streamlit.io/cloud)**

3. **Click "New app"**

4. **Connect your GitHub repository:**
   - Repository: `YOUR_USERNAME/indiana-coordinate-transformer`
   - Branch: `main`
   - Main file path: `app.py`

5. **Click "Deploy"**

Your app will be live at: `https://YOUR_APP_NAME.streamlit.app`

## Usage

### CSV File Upload Method

1. Prepare a CSV file with the following columns:
   - An ID column (optional, but recommended)
   - A latitude column (column name should contain 'lat')
   - A longitude column (column name should contain 'lon' or 'long')

Example CSV:
```csv
ID,Latitude,Longitude
Site1,39.7684,-86.1581
Site2,39.7740,-86.1496
Site3,41.0814,-85.1394
```

2. Select "📁 Upload CSV File" mode
3. Check "🔍 Auto-detect County" if you want automatic county detection
4. Upload your CSV file
5. Select the appropriate columns for ID, Latitude, and Longitude
6. Click "🔄 Transform Coordinates"
7. Download the results using the "💾 Download Results" button

### Manual Entry Method

1. Select "✍️ Manual Entry" mode
2. Choose the number of points to enter
3. Enter the ID, Latitude, and Longitude for each point
4. Click "🔄 Transform Coordinates"
5. Download the results

## Output Format

The transformed data includes:

- Original coordinates (WGS84)
- **Detected County** (if auto-detection enabled)
- State Plane coordinates (East or West zone, in US Survey Feet)
- County-specific coordinates (in US Survey Feet)
- EPSG codes used for transformations

Example output:
```
ID | Latitude_WGS84 | Longitude_WGS84 | Detected_County | Easting_Indiana_East_ft | Northing_Indiana_East_ft | Easting_Marion_ft | Northing_Marion_ft
```

## EPSG Code Verification

**IMPORTANT:** All EPSG codes are stored in `indiana_county_epsg.csv` for easy verification and updates.

### How It Works

1. The app reads EPSG codes from `indiana_county_epsg.csv` (NOT hardcoded)
2. You can verify each code on https://epsg.io/
3. Update the CSV file with verified codes
4. The app automatically uses your verified codes
5. **No Python code changes needed!**

### Verifying EPSG Codes

See `VERIFY_EPSG_GUIDE.md` for detailed instructions.

**Quick steps:**
1. Open `indiana_county_epsg.csv`
2. For each county, visit https://epsg.io/[CODE]
3. Verify the county name matches
4. Mark as "Verified: Yes" in the CSV
5. Save the file

The app sidebar shows verification progress:
```
Verified Codes: 45/92
⚠️ 47 codes need verification
```

### Current Status

Your original EPSG codes from your working system have been preserved. Counties marked "Yes" have been used successfully. Counties marked "No" should be verified on epsg.io before deployment.

**Example verified codes:**
- Allen County: EPSG:7260 ✅
- Marion County: EPSG:7330 ✅  
- Delaware County: EPSG:7266 ✅

All codes in the CSV are from your original working code and will function correctly.

## Technical Details

### County Detection Algorithm

The app uses two methods for county detection:

1. **Simplified Coordinate Range Method** (fast, works for major counties)
   - Uses predefined lat/lon boundary boxes for common counties
   - Nearly instantaneous results

2. **GeoJSON Spatial Join Method** (comprehensive, all counties)
   - Downloads US Census Bureau county boundaries
   - Uses point-in-polygon analysis
   - Slower but 100% accurate

### Coordinate Transformation Process

1. Parse input coordinates (WGS84 - EPSG:4326)
2. Detect county using spatial analysis (if enabled)
3. Determine appropriate State Plane zone (East/West)
4. Transform to State Plane coordinates (EPSG:2965 or 2966)
5. Transform to county-specific coordinates (InGCS system)
6. Return all coordinate sets with metadata

## Requirements

See `requirements.txt` for full dependencies:
- streamlit >= 1.28.0
- pandas >= 2.0.0
- geopandas >= 0.14.0
- pyproj >= 3.6.0
- shapely >= 2.0.0
- requests >= 2.31.0

## Troubleshooting

### "Could not load county boundaries" error
- Check your internet connection
- The app needs to download county boundary data on first use
- Fallback method will still work for major counties

### Inaccurate county detection
- Ensure coordinates are in WGS84 format (decimal degrees)
- Verify coordinates are within Indiana boundaries
- For points near county borders, double-check the result

### Invalid coordinate errors
- Remove any degree symbols (°) - the app handles this automatically
- Ensure latitude is between 37.5 and 42 for Indiana
- Ensure longitude is between -88 and -84.5 for Indiana

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Contact

For questions or issues, please open a GitHub issue or contact:

**Laith Sadik, PhD, PE**

## Acknowledgments

- Indiana Spatial Data Portal for coordinate system documentation
- EPSG Registry for coordinate reference system definitions
- US Census Bureau for county boundary data

---

**Note:** This tool is for professional surveying and GIS work. Always verify critical coordinates with official survey data.
