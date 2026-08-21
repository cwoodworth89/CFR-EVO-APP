"""Custom places resolver for manually curated locations (parks, schools, facilities).
These are catch-all entries checked LAST in the resolution chain."""
import re
import logging
from typing import Optional

try:
    from thefuzz import fuzz
except ImportError:
    import difflib
    class _Fuzz:
        @staticmethod
        def token_set_ratio(s1, s2):
            return int(difflib.SequenceMatcher(None, str(s1).lower(), str(s2).lower()).ratio() * 100)
    fuzz = _Fuzz()


class CustomPlacesResolver:
    def __init__(self, places_cache: dict):
        self._cache = places_cache or {}  # {name_lower: {address, lat, lng, ...}}

    def resolve(self, address: str) -> dict | None:
        """Fuzzy match against custom places. Returns geocoded result or None."""
        if not self._cache or not address:
            return None
        clean = address.strip().lower()
        best_match = None
        best_score = 0
        for name, details in self._cache.items():
            score = fuzz.token_set_ratio(clean, name)
            if score > best_score:
                best_score = score
                best_match = details
        if best_score >= 85 and best_match:
            return {
                "address": best_match.get('address', address),
                "lat": best_match['lat'],
                "lng": best_match['lng'],
                "rings": [],
                "confidence": float(best_score),
                "is_ambiguous": False,
                "is_custom_place": True
            }
        return None

    def check_manual_overrides(self, clean_address: str, get_coordinates_fn=None) -> dict | None:
        """Hardcoded special cases: Port Mann Bridge, Riverview Hospital, 3080 Gordon Ave."""
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
                label = f'Station {num}, Riverview Hospital (2601 Lougheed Hwy)' if num else f'{clean_address.title()}, Riverview Hospital (2601 Lougheed Hwy)'
                return {
                    'address': label,
                    'lat': 49.245830, 'lng': -122.805330,
                    'rings': [], 'confidence': 100.0, 'is_ambiguous': False
                }
        return None
