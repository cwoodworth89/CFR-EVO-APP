"""Hardcoded geocoding overrides for locations absent from public.parcels.

Split out of custom_places_resolver.py when the untrusted custom-places dataset was
removed. These are retained because they are real dispatch destinations that the parcel
data does not cover -- a bridge deck, a hospital campus with internal station numbers,
and a transit loop.

TECHNICAL DEBT (CLAUDE.md §6.2): string-matching a destination in application code is
the wrong place for this. Each of these belongs in public.parcels or
public.custom_places-equivalent municipal data as a proper record. They are kept only
because deleting them would cause live geocoding failures with no replacement.

The '3080 Gordon Ave' case is the clearest example: it exists as a dispatch destination
but not as a parcel, so the code silently substitutes 3030 Gordon Ave. That is a data
gap being papered over in Python and should be fixed in the parcel table.
"""
import re


def check_manual_overrides(clean_address: str, get_coordinates_fn=None) -> dict | None:
    """Last-resort geocoding for destinations missing from public.parcels."""
    if not clean_address:
        return None
    upper = clean_address.upper()

    if upper == '3080 GORDON AVE' and get_coordinates_fn:
        res = get_coordinates_fn('3030 GORDON AVE')
        if res:
            res['address'] = '3080 Gordon Ave'
            return res

    if '2900 BARNET' in upper:
        return {
            'address': '2900 Barnet Hwy (Coquitlam Central Bus Loop)',
            'lat': 49.2765771, 'lng': -122.8003925,
            'rings': [], 'confidence': 100.0, 'is_ambiguous': False
        }

    if 'PORT MANN' in upper or 'PORTMAN' in upper:
        return {
            'address': 'Port Mann Bridge, Coquitlam, BC',
            'lat': 49.2237874, 'lng': -122.8152597,
            'rings': [], 'confidence': 100.0, 'is_ambiguous': False
        }

    if 'RIVERVIEW' in upper or ('STATION' in upper and re.search(r'\bSTATION\s*\d+\b', upper)):
        station_match = re.search(r'\bSTATION\s*(\d+)\b', upper)
        if station_match or upper in ['BROOKSIDE', 'CENTRALE', 'CREASE CLINIC']:
            num = station_match.group(1) if station_match else ''
            label = (f'Station {num}, Riverview Hospital (2601 Lougheed Hwy)' if num
                     else f'{clean_address.title()}, Riverview Hospital (2601 Lougheed Hwy)')
            return {
                'address': label,
                'lat': 49.245830, 'lng': -122.805330,
                'rings': [], 'confidence': 100.0, 'is_ambiguous': False
            }
    return None
