from sqlalchemy import Column, Integer, BigInteger, String, Float, Boolean, Text, DateTime, Date, JSON, ARRAY, Numeric, CheckConstraint, func
from sqlalchemy.orm import synonym
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY as PG_ARRAY
import uuid


try:
    from api.database import Base
except ModuleNotFoundError:
    from backend.api.database import Base

SafeJSON = JSON().with_variant(JSONB(), "postgresql")
SafeArray = JSON().with_variant(PG_ARRAY(String), "postgresql")
SafeUUID = String(36).with_variant(UUID(as_uuid=True), "postgresql")

class LiveCallModel(Base):
    __tablename__ = "dispatches"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    dispatch_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    incident_type = Column(String, default="Unknown Incident", nullable=False)
    responding_units = Column(SafeArray, default=[], nullable=False)
    routing_metrics = Column(SafeJSON, default=[], nullable=True)
    target = Column(SafeJSON, default={}, nullable=False)
    
    raw_transcript = Column(Text, nullable=True)
    sanitized_transcript = Column(Text, nullable=True)
    # confidence_score was removed 2026-08-29 (punch-list #45). It was a
    # metadata-completeness score labelled as confidence; named review flags
    # in target.review_flags replace it.
    verify_location = Column(Boolean, default=False)
    origins = Column(SafeArray, default=[])
    
    audio_url = Column(Text, nullable=True)
    audio_duration = Column(Numeric(6, 2), nullable=True)
    
    verified_transcript = Column(Text, nullable=True)
    verified_address = Column(Text, nullable=True)
    verified_incident = Column(Text, nullable=True)
    verified_units = Column(SafeArray, nullable=True)
    # Promoted out of the `target` JSON blob 2026-08-31. These are fixed fields a
    # human types during review, not the geocoder's variable-shaped answer, so they
    # belong in the schema where they can be typed, indexed and seen.
    verified_map_grid = Column(Text, nullable=True)
    verified_talkgroup = Column(Text, nullable=True)
    verified_response_type = Column(Text, nullable=True)
    verified_x_street_1 = Column(Text, nullable=True)
    verified_x_street_2 = Column(Text, nullable=True)
    feedback_submitted = Column(Boolean, default=False)
    quality_rating = Column(String, default="PENDING")
    model_updated = Column(Boolean, default=False)
    review_notes = Column(Text, nullable=True)



class EvaluationHistoryModel(Base):
    __tablename__ = "evaluation_history"
    __table_args__ = {'extend_existing': True}

    id = Column(SafeUUID, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    model_version = Column(String, nullable=False)
    total_samples = Column(Integer, nullable=False)
    # Nullable since 2026-09-05: a parser or geocoder harness run has no WER, and an
    # invented 0.0 would be a fabricated number (CLAUDE.md 6.1).
    wer = Column(Numeric(5, 2), nullable=True)
    cer = Column(Numeric(5, 2), nullable=True)
    perfect_percent = Column(Numeric(5, 2), nullable=True)
    operational_percent = Column(Numeric(5, 2), nullable=True)
    failed_percent = Column(Numeric(5, 2), nullable=True)
    # Added 2026-09-05 (migration 2026-09-05_evaluation_history_harness_runs.sql) so any
    # harness run can be recorded and compared over time: tools/harness_history.py.
    stage = Column(String, nullable=True)
    git_hash = Column(String, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    metrics = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)


class RoadClosureModel(Base):
    __tablename__ = "road_closures"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # Always the feed's own id. A feed record without one is skipped at ingestion, never
    # given an id from its position in the list (punch list #91, operator 2026-09-16).
    closure_id = Column(String, unique=True, index=True, nullable=False)
    # NULL when the feed sent no road name (#91): nothing is made up; the kiosk shows "--".
    street_name = Column(String, nullable=True)
    source = Column(String, nullable=False)
    # NULL when the feed sent no usable severity (#91). No default: an unknown severity is
    # not a tier, and the old default "FULL_CLOSURE" served an unknown as NO_ACCESS.
    closure_type = Column(String, nullable=True)
    emergency_access = Column(String, nullable=True)
    headline = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    geometry = Column(SafeJSON, nullable=False)
    coordinates = Column(SafeArray, nullable=False)
    zone_id = Column(String(16), index=True, nullable=True)
    affected_zones = Column(SafeArray, nullable=True)
    # Resolved server-side from public.zones so the kiosk can group closures by hall
    # without fetching zones.json.
    hall_id = Column(String(4), index=True, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class RoadClosureSyncStatusModel(Base):
    """The outcome of the most recent attempt to sync road closures from the remote feeds.

    One row, id = 1. It is deliberately NOT a column on road_closures: the outcome of an
    attempt is not a property of any closure, and a successful sync that returns zero
    closures touches no row at all -- which is precisely the case the flag has to be able
    to report (punch list #89, operator ruling 2026-09-16).

    Persisted rather than held in process memory because the API container restarts, and
    run_periodic_road_closure_sync only re-attempts once the local data is already past
    check_and_sync_if_stale's 24 h gate -- so an in-memory flag would clear on every
    restart and then read "all clear" for up to an hour with the link still down.
    """
    __tablename__ = "road_closure_sync_status"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_road_closure_sync_status_singleton"),
        CheckConstraint(
            "last_outcome IN ('NOT_ATTEMPTED', 'SUCCEEDED', 'FAILED')",
            name="ck_road_closure_sync_status_outcome",
        ),
        {'extend_existing': True},
    )

    id = Column(Integer, primary_key=True, autoincrement=False, default=1)
    # NOT_ATTEMPTED / SUCCEEDED / FAILED. NOT_ATTEMPTED is the state before this API
    # container has ever run a sync; it is not the same as a failure and must not render
    # as one.
    last_outcome = Column(String(16), nullable=False, default="NOT_ATTEMPTED")
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    # Free text from the exception, when there was one. Diagnostic, not crew-facing.
    last_error = Column(Text, nullable=True)
    # Per-source reachability for the attempt, e.g.
    # {"DriveBC Open511": {"reached": true}, "Municipal 511": {"reached": false, "error": "..."}}
    # It is what makes "any source unreachable counts as FAILED" auditable rather than a
    # bare boolean the operator has to take on trust.
    sources = Column(SafeJSON, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class StreetViewOverrideModel(Base):
    __tablename__ = "streetview_overrides"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    clean_address = Column(String, unique=True, index=True, nullable=False)
    front_lat = Column(Float, nullable=False)
    front_lng = Column(Float, nullable=False)
    heading = Column(Float, default=0.0)
    pitch = Column(Float, default=5.0)
    fov = Column(Float, default=80.0)


class ParcelModel(Base):
    __tablename__ = "parcels"
    __table_args__ = {'extend_existing': True}


    # System
    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    parcel_uuid = Column(SafeUUID, default=lambda: str(uuid.uuid4()), nullable=False)

    # From Addresses.shp
    gis_id = Column(String(255), index=True, nullable=True)
    address = Column(String(255), unique=True, index=True, nullable=False)
    clean_address = synonym('address')
    house = Column(String(50), nullable=True)
    street = Column(String(255), nullable=True)
    streettype = Column(String(50), nullable=True)
    unit = Column(String(50), index=True, nullable=True)
    unittype = Column(String(50), nullable=True)
    postal = Column(String(10), nullable=True)
    block = Column(String(50), nullable=True)
    plan = Column(String(50), nullable=True)
    lot = Column(String(50), nullable=True)
    legaldesc = Column(Text, nullable=True)
    plan_area = Column(String(20), nullable=True)
    folio = Column(String(50), nullable=True)
    zonetype1 = Column(String(30), index=True, nullable=True)
    zonetype2 = Column(String(30), nullable=True)
    zonetype3 = Column(String(30), nullable=True)
    status = Column(String(20), nullable=True)
    units = Column(Integer, nullable=True)
    sc_card = Column(String(50), nullable=True)
    extract_dt = Column(DateTime, nullable=True)

    # From Addresses.shp Geometry
    # The PARCEL POLYGON CENTROID, computed by us from geom -- not supplied by the
    # City. Zone point-in-polygon input, map centring, and simple per-parcel script
    # work. Also the LAST-RESORT arrival position, and a poor one: outside the parcel
    # on 177 rows. Never copy into front_* or entrance_* (punch-list #50).
    # Renamed from lat/lng 2026-08-31 so the name says what it holds; the API still
    # publishes it as "lat"/"lng".
    centroid_lat = Column(Float, nullable=True)
    centroid_lng = Column(Float, nullable=True)

    # Pre-computed at import
    zone_id = Column(String(16), index=True, nullable=True)
    address_normalized = Column(String(255), index=True, nullable=True)

    # Operational (Tactical Property & Pre-Plan Metadata)
    front_lat = Column(Float, nullable=True)
    front_lng = Column(Float, nullable=True)
    # The operator-verified arrival point (punch-list #49): where the truck stops. NULL on
    # every parcel until someone sets one; an import never writes these. Outranks front_*
    # in the resolver. Attribution is required: an unattributed override is just another
    # unexplained number (CLAUDE.md 6.3).
    entrance_lat = Column(Float, nullable=True)
    entrance_lng = Column(Float, nullable=True)
    entrance_note = Column(Text, nullable=True)
    entrance_set_by = Column(Text, nullable=True)
    entrance_set_at = Column(DateTime(timezone=True), nullable=True)

    # Preferred Street View camera, NULL until the operator saves one. The defaults that
    # used to sit here made every parcel read as a saved 0-degree view (#35a, migration
    # 2026-09-06_streetview_override_is_null_until_saved.sql). fov is degrees.
    streetview_heading = Column(Float, nullable=True)
    streetview_pitch = Column(Float, nullable=True)
    streetview_fov = Column(Float, nullable=True)
    # The panorama the operator was looking at when they saved: pins the camera position,
    # not just the heading. Storable indefinitely under the Maps Platform Service Specific
    # Terms A.3 (docs/standards/google-maps-platform-terms-excerpts.md).
    streetview_pano_id = Column(Text, nullable=True)
    # Where the camera stands, which is NOT where the truck stops. It lived in front_lat
    # until 2026-09-11 and moved the routing destination every time a view was saved
    # (punch list #78). Operator ruling: the computed point, the arrival point and the
    # Street View point are separate and do not change each other.
    streetview_lat = Column(Float, nullable=True)
    streetview_lng = Column(Float, nullable=True)

    lock_box_notes = Column(Text, nullable=True)
    hazard_notes = Column(Text, nullable=True)
    pre_plan_pdf_url = Column(Text, nullable=True)
    construction_type = Column(String(100), nullable=True)
    floor_count = Column(Integer, nullable=True)
    is_pa_page = Column(Boolean, server_default="false", default=False, nullable=False)

    # The CFR-owned master row for a multi-parcel address: one per property, built by
    # import_parcels.build_base_site_rows, unique per address via
    # parcels_base_site_address_uniq. It carries the operator's context -- entrance point,
    # lockbox, hazard notes -- and speaks for every City row at that address.
    #
    # The column has existed since 2026-08-31 but was absent from this model, so every ORM
    # lookup was blind to it and resolved an address to an arbitrary City row. That is
    # punch-list #77: the save and the resolver each picked independently and disagreed.
    # See docs/briefings/base_site_rows_decision.md.
    is_base_site = Column(Boolean, server_default="false", default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


