# NOTE: For local shapefiles see docs/gis_endpoints.md, and for transcription/sanitization vocabulary see docs/call_structure.md
import geopandas as gpd

# Make sure these paths and column names are correct for your setup
ADDRESS_SHAPEFILE_PATH = 'data/Property_Information/Addresses.shp'
ADDRESS_STREET_NAME_COLUMN = 'STREET'

print("Reading shapefile to extract unique street names...")

try:
    gdf = gpd.read_file(ADDRESS_SHAPEFILE_PATH)
    # Drop any rows where the street name is missing, convert to uppercase, and get unique values
    unique_streets = gdf[ADDRESS_STREET_NAME_COLUMN].dropna().str.upper().unique()

    # Save the list to a text file
    with open('data/vocabulary/coquitlam_streets.txt', 'w') as f:
        for street in sorted(unique_streets):
            f.write(f"{street}\n")

    print(f"\nSUCCESS! Found {len(unique_streets)} unique street names.")
    print("They have been saved to 'data/vocabulary/coquitlam_streets.txt'.")

except Exception as e:
    print(f"An error occurred: {e}")