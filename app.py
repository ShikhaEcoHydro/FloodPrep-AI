import streamlit as st
import geopandas as gpd
import rasterio
from rasterio.mask import mask
import numpy as np
import folium
from streamlit_folium import st_folium
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

st.set_page_config(page_title="FloodPrep AI", layout="wide")

st.title("FloodPrep AI")
st.caption("GIS pre-processing for hydraulic modelling")

# --- Sidebar: inputs ---
with st.sidebar:
    st.header("Inputs")
    catchment_file = st.file_uploader("Catchment boundary (GeoJSON)", type=["geojson", "json"])
    dem_file = st.file_uploader("DEM (GeoTIFF)", type=["tif", "tiff"])
    landuse_file = st.file_uploader("Land use (GeoJSON)", type=["geojson", "json"])
    rainfall_mm = st.number_input("Design rainfall intensity (mm/hr)", min_value=0.0, value=50.0)

# --- Main area ---
col1, col2 = st.columns(2)

gdf_metric = None  # we'll reuse this in col2 below

with col1:
    st.subheader("Catchment Geometry")
    if catchment_file is not None:
        gdf = gpd.read_file(catchment_file)
        gdf_metric = gdf.to_crs(gdf.estimate_utm_crs())

        area_km2 = gdf_metric.geometry.area.sum() / 1_000_000
        perimeter_km = gdf_metric.geometry.length.sum() / 1000

        st.metric("Area", f"{area_km2:.2f} km²")
        st.metric("Perimeter", f"{perimeter_km:.2f} km")
    else:
        st.info("Upload a catchment file to see area, perimeter, slope.")

from rasterio.warp import calculate_default_transform, reproject, Resampling

with col2:
    st.subheader("Hydrology Outputs")
    if catchment_file is not None and dem_file is not None:
        with rasterio.open(dem_file) as src:
            gdf_dem_crs = gdf.to_crs(src.crs)
            geoms = gdf_dem_crs.geometry.values

            out_image, out_transform = mask(src, geoms, crop=True, nodata=np.nan)
            dem_array = out_image[0].astype(float)

            nodata_val = src.nodata
            if nodata_val is not None:
                dem_array[dem_array == nodata_val] = np.nan

            src_crs = src.crs
            src_height, src_width = dem_array.shape

        utm_crs = gdf.estimate_utm_crs()

        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs, utm_crs, src_width, src_height, *gdf_dem_crs.total_bounds
        )

        dem_array_clean = np.where(np.isnan(dem_array), -9999, dem_array)
        dem_reprojected = np.empty((dst_height, dst_width), dtype=np.float32)

        reproject(
            source=dem_array_clean,
            destination=dem_reprojected,
            src_transform=out_transform,
            src_crs=src_crs,
            dst_transform=dst_transform,
            dst_crs=utm_crs,
            resampling=Resampling.bilinear,
            src_nodata=-9999,
            dst_nodata=-9999
        )

        dem_reprojected[dem_reprojected == -9999] = np.nan

        pixel_size_x = abs(dst_transform[0])
        pixel_size_y = abs(dst_transform[4])

        avg_elevation = np.nanmean(dem_reprojected)
        min_elevation = np.nanmin(dem_reprojected)
        max_elevation = np.nanmax(dem_reprojected)

        dz_dy, dz_dx = np.gradient(dem_reprojected, pixel_size_y, pixel_size_x)
        slope_radians = np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))
        slope_degrees = np.degrees(slope_radians)
        slope_percent = np.tan(slope_radians) * 100

        avg_slope_percent = np.nanmean(slope_percent)
        avg_slope_degrees = np.nanmean(slope_degrees)

        st.metric("Average Elevation", f"{avg_elevation:.1f} m")
        st.metric("Elevation Range", f"{min_elevation:.1f} – {max_elevation:.1f} m")
        st.metric("Average Slope", f"{avg_slope_percent:.2f} %  ({avg_slope_degrees:.2f}°)")

        st.markdown("---")
        st.markdown("**Land Cover Assumption**")
        land_cover_type = st.selectbox(
            "Select dominant land cover (used to estimate runoff coefficient)",
            ["Forest / Natural", "Agricultural / Open", "Suburban / Mixed", "Urban / Impervious"]
        )

        c_lookup = {
            "Forest / Natural": 0.20,
            "Agricultural / Open": 0.35,
            "Suburban / Mixed": 0.55,
            "Urban / Impervious": 0.85
        }
        runoff_coefficient = c_lookup[land_cover_type]
        st.caption(f"Assumed runoff coefficient (C) = {runoff_coefficient} — illustrative value, not derived from actual land cover classification.")

        # --- Rational Method validity warning ---
        RATIONAL_METHOD_MAX_AREA_KM2 = 25  # rule-of-thumb upper limit for Rational Method validity
        if area_km2 > RATIONAL_METHOD_MAX_AREA_KM2:
            st.warning(
                f"⚠️ Catchment area ({area_km2:.1f} km²) exceeds the typical valid range for the "
                f"Rational Method (~{RATIONAL_METHOD_MAX_AREA_KM2} km²). Peak flow and runoff volume "
                f"below are illustrative of the calculation methodology only, not reliable hydrological "
                f"estimates at this scale. For large basins, a full hydrograph method (e.g., SCS-CN, "
                f"unit hydrograph, or hydrodynamic modelling) is appropriate instead."
            )

        # --- Time of Concentration (Kirpich) ---
        # L approximated from catchment area (simplification — true flow-path length needs flow accumulation analysis)
        L_meters = 1.5 * np.sqrt(area_km2 * 1_000_000)  # rough proxy for longest flow path
        S_decimal = avg_slope_percent / 100  # convert % to decimal m/m

        Tc_minutes = 0.0195 * (L_meters ** 0.77) * (S_decimal ** -0.385)
        Tc_hours = Tc_minutes / 60

        # --- Peak Flow (Rational Method) ---
        # Q = C * I * A / 360, with A in hectares, I in mm/hr, Q in m3/s
        area_hectares = area_km2 * 100
        peak_flow_cms = runoff_coefficient * rainfall_mm * area_hectares / 360

        # --- Runoff Volume ---
        # Approximate storm duration using Tc; V = C * P * A (P = rainfall depth over duration)
        rainfall_depth_mm = rainfall_mm * Tc_hours  # crude depth estimate from intensity x duration
        runoff_volume_m3 = runoff_coefficient * (rainfall_depth_mm / 1000) * (area_km2 * 1_000_000)

        st.markdown("---")
        st.markdown("**Runoff & Flow Estimates**")
        st.metric("Time of Concentration", f"{Tc_minutes:.1f} min ({Tc_hours:.2f} hr)")
        st.metric("Peak Flow (Rational Method)", f"{peak_flow_cms:.2f} m³/s")
        st.metric("Estimated Runoff Volume", f"{runoff_volume_m3:,.0f} m³")

    else:
        st.info("Upload both catchment and DEM files to see elevation stats.")

st.subheader("Map")

if catchment_file is not None:
    # Get centroid for map centering
    centroid = gdf.geometry.centroid.iloc[0]
    m = folium.Map(
        location=[centroid.y, centroid.x],
        zoom_start=9,
        tiles="CartoDB positron"
    )

    # Add catchment boundary
    folium.GeoJson(
        gdf,
        name="Catchment Boundary",
        style_function=lambda x: {
            "fillColor": "#3388ff",
            "color": "#0000ff",
            "weight": 2,
            "fillOpacity": 0.2
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["HYBAS_ID", "SUB_AREA"],
            aliases=["Basin ID", "Sub-area (km²)"],
            localize=True
        )
    ).add_to(m)

    # Add layer control
    folium.LayerControl().add_to(m)

    st_folium(m, width=1200, height=500)
else:
    st.info("Upload a catchment file to see the map.")

st.subheader("Report")

if catchment_file is not None and dem_file is not None:
    if st.button("Generate PDF Report"):

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("FloodPrep AI — Catchment Analysis Report", styles["Title"]))
        elements.append(Spacer(1, 0.5*cm))

        # Subtitle
        elements.append(Paragraph("Generated by FloodPrep AI | Copernicus GLO-30 DEM | HydroBASINS Catchment", styles["Normal"]))
        elements.append(Spacer(1, 1*cm))

        # Section 1: Catchment Geometry
        elements.append(Paragraph("1. Catchment Geometry", styles["Heading2"]))
        elements.append(Spacer(1, 0.3*cm))

        geometry_data = [
            ["Parameter", "Value"],
            ["Catchment Area", f"{area_km2:.2f} km²"],
            ["Perimeter", f"{perimeter_km:.2f} km"],
            ["Average Elevation", f"{avg_elevation:.1f} m"],
            ["Elevation Range", f"{min_elevation:.1f} – {max_elevation:.1f} m"],
            ["Average Slope", f"{avg_slope_percent:.2f} % ({avg_slope_degrees:.2f}°)"],
        ]

        t1 = Table(geometry_data, colWidths=[8*cm, 8*cm])
        t1.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C6E9A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2FB")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t1)
        elements.append(Spacer(1, 1*cm))

        # Section 2: Hydrology Outputs
        elements.append(Paragraph("2. Hydrology Outputs (Rational Method)", styles["Heading2"]))
        elements.append(Spacer(1, 0.3*cm))

        hydro_data = [
            ["Parameter", "Value"],
            ["Land Cover Type", land_cover_type],
            ["Runoff Coefficient (C)", str(runoff_coefficient)],
            ["Design Rainfall Intensity", f"{rainfall_mm:.1f} mm/hr"],
            ["Time of Concentration (Tc)", f"{Tc_minutes:.1f} min ({Tc_hours:.2f} hr)"],
            ["Peak Flow (Rational Method)", f"{peak_flow_cms:.2f} m³/s"],
            ["Estimated Runoff Volume", f"{runoff_volume_m3:,.0f} m³"],
        ]

        t2 = Table(hydro_data, colWidths=[8*cm, 8*cm])
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C6E9A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#EAF2FB")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(t2)
        elements.append(Spacer(1, 1*cm))

        # Disclaimer
        if area_km2 > 25:
            elements.append(Paragraph(
                "⚠ Disclaimer: Catchment area exceeds the valid range for the Rational Method (~25 km²). "
                "Peak flow and runoff volume are illustrative only. For large basins, a full hydrograph "
                "method (SCS-CN, unit hydrograph, or hydrodynamic modelling) is recommended.",
                styles["Normal"]
            ))
            elements.append(Spacer(1, 0.5*cm))

        # Data sources
        elements.append(Paragraph("3. Data Sources", styles["Heading2"]))
        elements.append(Spacer(1, 0.3*cm))
        elements.append(Paragraph(
            "• Catchment boundary: HydroBASINS (Lehner & Grill, 2013), WWF / HydroSHEDS programme.",
            styles["Normal"]
        ))
        elements.append(Spacer(1, 0.2*cm))
        elements.append(Paragraph(
            "• DEM: Copernicus GLO-30 (European Space Agency, 2024). Distributed by OpenTopography. "
            "https://doi.org/10.5069/G9028PQB.",
            styles["Normal"]
        ))

        doc.build(elements)
        buffer.seek(0)

        st.download_button(
            label="Download PDF Report",
            data=buffer,
            file_name="FloodPrep_AI_Report.pdf",
            mime="application/pdf"
        )
else:
    st.info("Upload catchment and DEM files to generate a report.")
