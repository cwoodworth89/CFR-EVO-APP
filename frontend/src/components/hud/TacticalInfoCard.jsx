import React from 'react';

export default function TacticalInfoCard({
  target = {},
  activeCall = null,
  onOpenPrePlan = null,
  className = ""
}) {
  const data = target || (activeCall?.target) || {};

  // Parcel & Building Metadata
  const buildingHeight = data.building_height_m || data.height_m || (data.floors ? (data.floors * 3.2).toFixed(1) : null);
  const storeys = data.floor_count || data.floors || data.storeys || (data.building_height_m ? Math.max(1, Math.round(data.building_height_m / 3.2)) : null);
  const constructionType = data.construction_type || data.building_type || 'Commercial / Mixed';
  const aerialReachClearance = data.aerial_reach || (buildingHeight ? (parseFloat(buildingHeight) <= 32 ? '✅ Ladder Reach Compliant (<32m)' : '⚠️ High-Rise Tower (>32m Aerial Standpipe Required)') : 'Standard Access');

  // Hydrant Information
  const nearestCityHydrant = data.nearest_city_hydrant || activeCall?.nearest_city_hydrant || 'D-163';
  const nearestCityDist = data.nearest_city_dist || activeCall?.nearest_city_dist || '42';
  const cityHydrantGpm = data.city_hydrant_gpm || '1500+ GPM (Blue - Class AA)';
  const nearestPrivateHydrant = data.nearest_private_hydrant || activeCall?.nearest_private_hydrant || null;
  const nearestPrivateDist = data.nearest_private_dist || activeCall?.nearest_private_dist || null;

  // Notes
  const lockBoxNotes = data.lock_box_notes || data.lockbox || 'Front lobby Knox Box (Master Key 4)';
  const hazardNotes = data.hazard_notes || data.hazards || null;
  const prePlanPdf = data.pre_plan_pdf_url || activeCall?.pre_plan_pdf_url;

  return (
    <div className={`bg-slate-900/90 backdrop-blur border border-slate-800 rounded-2xl p-4 shadow-xl flex flex-col gap-3.5 text-left font-sans text-slate-100 ${className}`}>
      {/* Header */}
      <div className="flex justify-between items-center border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-2">
          <span className="text-base">🏢</span>
          <h3 className="font-extrabold text-xs uppercase tracking-wider text-sky-400 font-mono">
            Tactical Parcel & Building Intelligence
          </h3>
        </div>
        {data.gis_id && (
          <span className="text-[10px] font-mono text-slate-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
            GIS: {data.gis_id}
          </span>
        )}
      </div>

      {/* 2x2 Primary Tactical Metric Grid */}
      <div className="grid grid-cols-2 gap-2.5 text-xs">
        {/* Building Height & Storeys */}
        <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-850 flex flex-col gap-0.5">
          <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 font-mono">
            Height & Floors
          </span>
          <div className="text-white font-black text-sm flex items-center gap-1.5">
            <span>{storeys ? `${storeys} Storey${storeys > 1 ? 's' : ''}` : 'Low-Rise'}</span>
            {buildingHeight && (
              <span className="text-sky-400 text-xs font-mono font-bold">({buildingHeight}m)</span>
            )}
          </div>
          <span className="text-[9.5px] text-slate-400 truncate">{constructionType}</span>
        </div>

        {/* Aerial Ladder Reach Clearance */}
        <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-850 flex flex-col gap-0.5">
          <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 font-mono">
            Aerial Ladder Reach
          </span>
          <div className="text-xs font-bold text-emerald-400 flex items-center gap-1">
            {aerialReachClearance}
          </div>
          <span className="text-[9.5px] text-slate-400">100ft Ladder Apparatus Clearance</span>
        </div>

        {/* Nearest City Hydrant */}
        <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-850 flex flex-col gap-0.5">
          <span className="text-[9px] font-bold uppercase tracking-wider text-sky-400 font-mono flex items-center gap-1">
            <span>💧</span>
            <span>City Hydrant ({nearestCityHydrant})</span>
          </span>
          <div className="text-white font-black text-xs font-mono">
            {nearestCityDist}m <span className="text-slate-400 font-normal font-sans">from entrance</span>
          </div>
          <span className="text-[9px] text-sky-300 font-mono">{cityHydrantGpm}</span>
        </div>

        {/* Private Hydrant / Standpipe */}
        <div className="bg-slate-950/80 p-2.5 rounded-xl border border-slate-850 flex flex-col gap-0.5">
          <span className="text-[9px] font-bold uppercase tracking-wider text-amber-400 font-mono flex items-center gap-1">
            <span>🔒</span>
            <span>Private Hydrant / FDC</span>
          </span>
          <div className="text-white font-black text-xs font-mono">
            {nearestPrivateHydrant ? `${nearestPrivateHydrant} (${nearestPrivateDist}m)` : 'None Reported'}
          </div>
          <span className="text-[9px] text-slate-400">On-site standpipe siamese</span>
        </div>
      </div>

      {/* Tactical Access & Hazard Notes */}
      <div className="flex flex-col gap-1.5 bg-slate-950/60 p-2.5 rounded-xl border border-slate-850 text-xs">
        <div className="flex items-center gap-1.5 font-mono text-[10px]">
          <span className="text-amber-400 font-bold">🔑 Lock Box:</span>
          <span className="text-slate-300">{lockBoxNotes}</span>
        </div>
        {hazardNotes && (
          <div className="flex items-center gap-1.5 font-mono text-[10px] text-rose-400">
            <span className="font-bold">⚠️ Hazard Alert:</span>
            <span>{hazardNotes}</span>
          </div>
        )}
      </div>

      {/* Pre-Incident Construction PDF Button */}
      {prePlanPdf && onOpenPrePlan && (
        <button
          type="button"
          onClick={onOpenPrePlan}
          className="bg-sky-900/50 hover:bg-sky-800 text-sky-200 border border-sky-600/60 hover:border-sky-400 font-bold text-xs py-2 px-3 rounded-xl transition flex items-center justify-center gap-2 cursor-pointer shadow-md"
        >
          <span>📄</span>
          <span>View Detailed Pre-Incident Tactical Plan (PDF)</span>
        </button>
      )}
    </div>
  );
}
