# GIS Service Package Version 2.0.0
try:
    from gis_service.geocoder import CoquitlamDataValidator
    from gis_service.normalization import (
        normalize_street_name, normalize_intersection_key,
        split_intersection_parts, parse_house_and_street, extract_near_street,
        ParsedAddress
    )
    from gis_service.address_resolver import AddressResolver
    from gis_service.intersection_resolver import IntersectionResolver
    from gis_service.spatial_queries import SpatialQueryEngine
except ModuleNotFoundError:
    pass

from gis_service.routing_engine import EVORoutingEngine
