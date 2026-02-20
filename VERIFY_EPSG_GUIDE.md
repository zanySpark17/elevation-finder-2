# How to Verify Indiana County EPSG Codes

## 🎯 Purpose

This guide helps you verify each Indiana county's EPSG code using epsg.io to ensure 100% accuracy in coordinate transformations.

## 📋 Step-by-Step Verification Process

### Step 1: Open the CSV File

Open `indiana_county_epsg.csv` in Excel, Google Sheets, or any text editor.

The file has this structure:
```csv
County,EPSG_Code,Verified,Notes
ALLEN,7260,Yes,NAD83(2011) / InGCS Allen (ftUS)
ADAMS,7301,No,Need to verify
...
```

### Step 2: Verify Each Code

For each county marked as "No" in the Verified column:

1. **Go to epsg.io**
   - Open your browser
   - Visit: https://epsg.io/

2. **Search for the EPSG Code**
   - In the search box, type the EPSG code (e.g., "7260")
   - Press Enter

3. **Verify the County Name**
   - Look at the full name shown (e.g., "NAD83(2011) / InGCS Allen (ftUS)")
   - Check that the county name matches
   - Verify it says "InGCS" (Indiana Geospatial Coordinate System)
   - Confirm it says "(ftUS)" meaning US Survey Feet

4. **Update the CSV**
   - If correct: Change "Verified" from "No" to "Yes"
   - If incorrect: 
     - Search epsg.io for the correct county name
     - Update the EPSG_Code column with the correct code
     - Change "Verified" to "Yes"
     - Update the Notes column

### Step 3: Example Verification

**Example 1: ALLEN County**

1. Go to https://epsg.io/7260
2. See: "NAD83(2011) / InGCS Allen (ftUS)"
3. ✅ County name matches = CORRECT
4. Mark as "Yes" in CSV

**Example 2: If you find an error**

1. Go to https://epsg.io/7999 (example wrong code)
2. See: Code doesn't exist or wrong county
3. Search epsg.io for "InGCS [County Name]"
4. Find correct code (e.g., 7301)
5. Update CSV with correct code
6. Mark as "Yes"

## 📝 CSV File Format

```csv
County,EPSG_Code,Verified,Notes
ADAMS,7301,Yes,NAD83(2011) / InGCS Adams (ftUS)
ALLEN,7260,Yes,NAD83(2011) / InGCS Allen (ftUS)
BARTHOLOMEW,7303,Yes,NAD83(2011) / InGCS Bartholomew (ftUS)
```

**Columns:**
- **County**: County name (must match exactly, use underscore for spaces)
- **EPSG_Code**: The EPSG code number
- **Verified**: "Yes" or "No" - have you personally verified this on epsg.io?
- **Notes**: Description from epsg.io

## ✅ What to Look For on epsg.io

A CORRECT entry will show:

✓ **Datum:** NAD83(2011) or NAD83  
✓ **System:** InGCS (Indiana Geospatial Coordinate System)  
✓ **County:** Matching the county name  
✓ **Units:** US Survey Feet (ftUS)  

Example correct entry:
```
EPSG:7260
NAD83(2011) / InGCS Allen (ftUS)
Projected CRS
```

## 🚫 Common Issues

### Issue 1: Code doesn't exist
- **Symptom:** epsg.io says "Not found" or shows a different region
- **Solution:** Search for "InGCS [County Name]" and find the correct code

### Issue 2: Wrong county name
- **Symptom:** Code exists but shows different county
- **Solution:** Search for the correct county's code

### Issue 3: Multiple codes for same county
- **Symptom:** Several EPSG codes found for one county
- **Solution:** Use the NAD83(2011) version with (ftUS) units

## 🔍 Quick Verification Checklist

For each county, verify:

- [ ] EPSG code exists on epsg.io
- [ ] County name matches exactly
- [ ] Shows "InGCS" in the name
- [ ] Shows "NAD83(2011)" or "NAD83"
- [ ] Shows "(ftUS)" for US Survey Feet
- [ ] No errors when loading in pyproj/geopandas

## 📊 Tracking Your Progress

As you verify codes, the Streamlit app sidebar will show:

```
Verified Codes: 45/92
⚠️ 47 codes need verification
```

This updates automatically as you edit the CSV file.

## 🎯 Priority Counties to Verify First

Start with these high-population counties:

1. **MARION** (Indianapolis) - EPSG:7330
2. **LAKE** (Gary) - EPSG:7363
3. **ALLEN** (Fort Wayne) - EPSG:7260
4. **HAMILTON** (Carmel) - EPSG:7317
5. **ST_JOSEPH** (South Bend) - EPSG:7300

## 💾 Saving Your Work

**After each verification:**

1. Save the CSV file
2. Refresh the Streamlit app
3. The app will automatically use your verified codes
4. No need to change any Python code!

## 🧪 Testing Your Codes

After updating codes, test with known locations:

**Marion County Test:**
- Lat: 39.7684, Lon: -86.1581 (Indianapolis)
- Should use EPSG:7330

**Allen County Test:**
- Lat: 41.0814, Lon: -85.1394 (Fort Wayne)  
- Should use EPSG:7260

**St. Joseph County Test:**
- Lat: 41.6764, Lon: -86.2520 (South Bend)
- Should use EPSG:7300

## 📚 Reference Links

- **epsg.io:** https://epsg.io/
- **EPSG Registry:** https://epsg.org/
- **Indiana GIS Portal:** https://www.indianamap.org/
- **Spatial Reference:** https://spatialreference.org/

## 🆘 If You're Unsure

If you're not sure about a code:

1. Leave it marked as "No" in the Verified column
2. Add a note in the Notes column
3. The app will still work with unverified codes
4. You can verify it later

## ✨ Final Checklist

Before deployment, ensure:

- [ ] All 92 counties have EPSG codes
- [ ] All codes marked "Yes" have been verified on epsg.io
- [ ] CSV file is saved
- [ ] CSV file is uploaded to GitHub with the app
- [ ] Tested transformations for at least 3 different counties

---

**Remember:** The CSV file method means you control the EPSG codes. The app will ALWAYS use whatever codes are in the CSV file, so you can update them anytime without touching the Python code!
