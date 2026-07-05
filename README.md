# FloodPrep AI 🌊
**GIS Pre-processing Tool for Hydraulic Modelling**

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://floodprep-ai.streamlit.app)

## Overview
Hydraulic engineers spend 60–80% of their time preparing spatial data before 
opening MIKE+ or SWMM. FloodPrep AI automates that pre-processing workflow — 
upload a catchment boundary and DEM, and get analysis-ready outputs instantly.

## Features
- **Catchment Geometry** — area, perimeter (GeoPandas, UTM reprojection)
- **Terrain Analysis** — average elevation, elevation range, slope from DEM 
  (Rasterio, numpy gradient)
- **Hydrology Calculations** — Time of Concentration (Kirpich), Peak Flow 
  (Rational Method), Runoff Volume
- **Interactive Map** — catchment boundary on a zoomable basemap (Folium)
- **PDF Report** — one-click engineering summary export (ReportLab)

## Inputs Required
| Input | Format | Source |
|-------|--------|--------|
| Catchment boundary | GeoJSON | HydroBASINS, QGIS delineation, or custom |
| Digital Elevation Model | GeoTIFF | Copernicus GLO-30, SRTM, or local DEM |

## Tech Stack
Python · Streamlit · GeoPandas · Rasterio · Folium · Plotly · ReportLab · NumPy

## Methodology Notes
- Catchment area calculated after reprojection to local UTM zone
- DEM reprojected to metric CRS before slope calculation
- Rational Method valid for catchments <25 km²; app displays warning for 
  larger basins and recommends SCS-CN or hydrodynamic modelling instead
- Flow path length (L) approximated from catchment area — a known 
  simplification for preliminary studies

## Data Sources (Demo)
- Catchment: HydroBASINS Level 6 (Lehner & Grill, 2013), WWF/HydroSHEDS
- DEM: Copernicus GLO-30, European Space Agency (2024), via OpenTopography. 
  https://doi.org/10.5069/G9028PQB

## Author
Deepshikha Srivastava | Erasmus Mundus MSc Applied Ecohydrology  
[LinkedIn](https://linkedin.com/in/Deepshikha-Srivastava) · 
[GitHub](https://github.com/ShikhaEcoHydro)