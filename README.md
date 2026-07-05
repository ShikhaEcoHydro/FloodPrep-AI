# FloodPrep AI 🌊
**GIS Pre-processing Tool for Hydraulic Modelling**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://floodprep-ai.streamlit.app)

## Overview
Hydraulic engineers spend 60–80% of their time preparing spatial data before 
opening MIKE+ or SWMM. FloodPrep AI automates that pre-processing workflow — 
upload a catchment boundary and DEM, and get analysis-ready outputs instantly.

## Features
- **Catchment Geometry** — area and perimeter calculated after reprojection to local UTM zone (GeoPandas)
- **Terrain Analysis** — average elevation, elevation range, and slope derived from DEM (Rasterio, NumPy)
- **Hydrology Calculations** — Time of Concentration (Kirpich), Peak Flow (Rational Method), Runoff Volume
- **Interactive Map** — catchment boundary on a zoomable basemap (Folium)
- **PDF Report** — one-click engineering summary export (ReportLab)

## Inputs Required
| Input | Format | Source |
|-------|--------|--------|
| Catchment boundary | GeoJSON | HydroBASINS, QGIS delineation, or custom |
| Digital Elevation Model | GeoTIFF | Copernicus GLO-30, SRTM, or local DEM |

## Tech Stack
Python · Streamlit · GeoPandas · Rasterio · Folium · Plotly · ReportLab · NumPy

## Methodology

The tool follows a sequential GIS and hydrological processing workflow:

**Step 1 — Catchment Geometry:** The uploaded GeoJSON boundary is read using GeoPandas and reprojected from geographic coordinates (WGS84/EPSG:4326) to a locally appropriate UTM zone (estimated automatically via `estimate_utm_crs()`). Area and perimeter are then calculated in metric units (km² and km respectively).

**Step 2 — Terrain Analysis:** The Copernicus GLO-30 DEM is clipped to the catchment boundary using Rasterio's mask function. Since the DEM is delivered in EPSG:4326 (degrees), it is reprojected to the same UTM zone before slope calculation, ensuring pixel dimensions are in metres rather than degrees. Slope is derived using `numpy.gradient`, computing the rate of elevation change between neighbouring pixels in x and y directions: `slope (°) = arctan(√(dz/dx² + dz/dy²))`.

**Step 3 — Time of Concentration (Kirpich Method):** `Tc = 0.0195 × L^0.77 × S^-0.385`, where Tc is in minutes, L is the longest flow path length (m) approximated as 1.5 × √Area (a recognised simplification for preliminary studies where flow accumulation data is unavailable), and S is average slope in m/m.

**Step 4 — Peak Flow (Rational Method):** `Q = C × I × A / 360`, where Q is peak flow (m³/s), C is the runoff coefficient (selected by land cover type from standard reference values), I is design rainfall intensity (mm/hr), and A is catchment area (hectares). The Rational Method is valid for catchments under ~25 km²; the app displays an explicit warning and recommends SCS-CN or hydrodynamic modelling for larger basins.

**Step 5 — Runoff Volume:** `V = C × P × A`, where rainfall depth P is estimated as intensity × time of concentration (a simplification — production use would apply depth-duration-frequency curves).

**Step 6 — Validation:** Computed catchment area was cross-checked against the SUB_AREA attribute reported by HydroBASINS in QGIS, showing less than 0.3% difference, attributable to differing area-calculation methods between the two tools.

## Limitations
- Flow path length (L) is approximated from catchment area, not derived from flow accumulation analysis
- Rational Method outputs are illustrative only for catchments >25 km²
- Runoff coefficient is manually selected, not derived from classified land use data
- Rainfall depth estimated from intensity × Tc; proper design storms require DDF curves

## Data Sources (Demo Dataset)
- Catchment boundary: HydroBASINS Level 6 (Lehner & Grill, 2013), WWF/HydroSHEDS programme
- DEM: Copernicus GLO-30, European Space Agency (2024), distributed by OpenTopography. https://doi.org/10.5069/G9028PQB

## Author
Deepshikha Srivastava | Erasmus Mundus MSc Applied Ecohydrology  
[LinkedIn](https://linkedin.com/in/Deepshikha-Srivastava) · [GitHub](https://github.com/ShikhaEcoHydro)