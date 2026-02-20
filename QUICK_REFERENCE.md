# Indiana Coordinate Transformer - Quick Reference

## 🎯 What Changed

**OLD SYSTEM:**
- EPSG codes hardcoded in Python
- Couldn't verify/update without editing code
- Risk of incorrect codes

**NEW SYSTEM:**
- EPSG codes in CSV file (`indiana_county_epsg.csv`)
- Easy to verify on epsg.io
- Update CSV = app uses new codes instantly
- No code changes needed!

## 📁 Key Files

```
indiana-coordinate-transformer/
├── app.py                          # Main Streamlit app
├── indiana_county_epsg.csv         # ⭐ EPSG CODES HERE (editable!)
├── requirements.txt                # Dependencies
├── README.md                       # Full documentation
├── VERIFY_EPSG_GUIDE.md           # Step-by-step verification guide
└── sample_coordinates.csv         # Test data
```

## ✅ Your Original Codes Are Preserved

All codes from your working system are in the CSV file:

```csv
County,EPSG_Code,Verified,Notes
ALLEN,7260,Yes,NAD83(2011) / InGCS Allen (ftUS)
MARION,7330,Yes,NAD83(2011) / InGCS Marion (ftUS)
DELAWARE,7266,Yes,NAD83(2011) / InGCS Delaware (ftUS)
...
```

## 🔧 How to Verify/Update Codes

### Option 1: Quick Check (Recommended)

1. Go to https://epsg.io/7260 (example: Allen County)
2. See: "NAD83(2011) / InGCS Allen (ftUS)"
3. County matches? ✅ It's correct
4. In CSV, change "Verified" from "No" to "Yes"

### Option 2: Find Correct Code

1. Code seems wrong? Search epsg.io for "InGCS [County Name]"
2. Find correct code
3. Update EPSG_Code in CSV
4. Mark as "Yes"
5. Save CSV

### The App Updates Automatically!

- Edit CSV → Save → Refresh app → New codes active
- No Python knowledge needed
- You're in complete control

## 🎮 How to Use the App

### Upload Mode
1. Upload CSV with Lat/Lon columns
2. Check "Auto-detect County" (or select manually)
3. Click "Transform Coordinates"
4. Download results

### Manual Mode
1. Enter coordinates directly
2. Check "Auto-detect County" (or select manually)
3. Click "Transform Coordinates"
4. Download results

## 🚀 Deployment Checklist

**Before deploying to Streamlit Cloud:**

- [ ] Verify critical county codes on epsg.io
  - Marion (Indianapolis): 7330
  - Allen (Fort Wayne): 7260
  - Lake (Gary): 7363
  - Hamilton (Carmel): 7317
  
- [ ] Upload these files to GitHub:
  - [ ] app.py
  - [ ] indiana_county_epsg.csv ⭐ REQUIRED
  - [ ] requirements.txt
  - [ ] README.md
  - [ ] .gitignore
  
- [ ] Test with sample_coordinates.csv

- [ ] Deploy to Streamlit Cloud
  - Repository: YOUR_USERNAME/indiana-coordinate-transformer
  - Main file: app.py
  
## 📊 Verification Progress

The app shows verification status in the sidebar:

```
📊 EPSG Code Status
Verified Codes: 45/92
⚠️ 47 codes need verification
```

Updates as you mark codes "Yes" in the CSV!

## 🧪 Test Your Codes

After updating, test with known locations:

**Marion County (Indianapolis):**
```
Lat: 39.7684
Lon: -86.1581
Expected EPSG: 7330
```

**Allen County (Fort Wayne):**
```
Lat: 41.0814
Lon: -85.1394  
Expected EPSG: 7260
```

## 💡 Pro Tips

1. **Start with high-priority counties** (your most-used locations)
2. **Batch verify** - do 5-10 counties at a time
3. **Keep a backup** of the CSV before making changes
4. **Test after each batch** - upload test coordinates
5. **The CSV is the source of truth** - the app always uses it

## 🆘 Quick Troubleshooting

**"Could not find CSV file"**
- Make sure `indiana_county_epsg.csv` is in the same folder as app.py
- Check filename spelling (case-sensitive on some systems)

**"Wrong transformation results"**
- Verify EPSG code on epsg.io
- Check county name in CSV matches exactly
- Confirm auto-detect picked the right county

**"EPSG code not found error"**
- That EPSG code doesn't exist
- Search epsg.io for the correct county code
- Update CSV with correct code

## 📞 Support Workflow

1. Check VERIFY_EPSG_GUIDE.md
2. Verify code on epsg.io
3. Update indiana_county_epsg.csv
4. Test with sample data
5. Deploy!

## 🎉 Benefits of This Approach

✅ **You control the codes** - edit CSV anytime  
✅ **No programming needed** - just edit CSV in Excel  
✅ **Easy to verify** - use epsg.io website  
✅ **Instant updates** - save CSV, app uses new codes  
✅ **Transparent** - see all codes in one file  
✅ **Version controlled** - track changes in Git  
✅ **Collaborative** - team can update codes  

---

**Bottom Line:** Your original EPSG codes are preserved and working. You can now easily verify and update any code using the CSV file, without touching Python code!
