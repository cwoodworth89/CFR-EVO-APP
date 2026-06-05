import geopandas as gpd
import os

# --- Configuration ---
# The path to your original, problematic shapefile
input_shapefile = 'data/Emergency_Response_Zones/Emergency_Response_Zones.shp'

# The path where you want to save the new, fixed shapefile
output_shapefile = 'data/Emergency_Response_Zones_fixed.shp'
# ---------------------

def fix_shapefile_winding_order(input_path, output_path):
    """
    Reads a shapefile and saves it again, which often corrects
    formatting issues like invalid winding order.
    """
    if not os.path.exists(input_path):
        print(f"ERROR: Input file not found at '{input_path}'")
        return

    print(f"Reading shapefile from: {input_path}")
    # The warning will still appear here, which is fine.
    # geopandas reads it and auto-corrects it in memory.
    gdf = gpd.read_file(input_path)
    
    print(f"Successfully read {len(gdf)} features.")
    
    try:
        print(f"Saving corrected shapefile to: {output_path}")
        # When we save it, it will write the corrected data to the new file.
        gdf.to_file(output_path, driver='ESRI Shapefile')
        print("\nSUCCESS! The shapefile has been corrected.")
        print(f"Please update the ZONES_SHAPEFILE_PATH in your main script to:")
        print(f"'{output_path}'")
    except Exception as e:
        print(f"\nERROR: Could not save the new shapefile. Reason: {e}")

if __name__ == "__main__":
    fix_shapefile_winding_order(input_shapefile, output_shapefile)