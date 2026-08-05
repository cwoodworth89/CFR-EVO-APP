import React, { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';
import SparkMD5 from 'spark-md5';

const APPARATUS_LIST = [
  { id: 'chief-master', label: '👑 CHIEF / ADMIN MASTER FEED', isMaster: true, icon: '👑', desc: 'Permanent feed (No Expiry) - All calls + Tap-to-listen audio', color: 'from-purple-600/30 to-indigo-600/20 border-purple-400 text-purple-200' },
  { id: 'cfr-dispatches', label: 'ALL STATION CALLS', icon: '🚨', desc: 'Receive all dispatch alerts for the department', color: 'from-amber-500/20 to-orange-500/10 border-amber-500/40 text-amber-300' },
  { id: 'engine-1', label: 'ENGINE 1', icon: '🚒', desc: 'Station 1 Apparatus', color: 'from-rose-500/20 to-red-500/10 border-rose-500/40 text-rose-300' },
  { id: 'engine-2', label: 'ENGINE 2', icon: '🚒', desc: 'Station 2 Apparatus', color: 'from-sky-500/20 to-blue-500/10 border-sky-500/40 text-sky-300' },
  { id: 'engine-3', label: 'ENGINE 3', icon: '🚒', desc: 'Station 3 Apparatus', color: 'from-emerald-500/20 to-teal-500/10 border-emerald-500/40 text-emerald-300' },
  { id: 'engine-4', label: 'ENGINE 4', icon: '🚒', desc: 'Station 4 Apparatus', color: 'from-purple-500/20 to-indigo-500/10 border-purple-500/40 text-purple-300' },
  { id: 'ladder-1', label: 'LADDER 1', icon: '🪜', desc: 'Truck 1 Aerial', color: 'from-yellow-500/20 to-amber-500/10 border-yellow-500/40 text-yellow-300' },
  { id: 'rescue-1', label: 'RESCUE 1', icon: '🚑', desc: 'Heavy Rescue Unit', color: 'from-orange-500/20 to-red-500/10 border-orange-500/40 text-orange-300' },
  { id: 'chief-1', label: 'CHIEF 1', icon: '🚘', desc: 'Battalion Chief Command', color: 'from-cyan-500/20 to-blue-500/10 border-cyan-500/40 text-cyan-300' },
];

const SHIFT_DURATIONS = [
  { hours: 4, label: '4 Hours (Short Shift)' },
  { hours: 8, label: '8 Hours (Day Shift)' },
  { hours: 12, label: '12 Hours (Standard Shift)' },
  { hours: 24, label: '24 Hours (Full Tour)' },
  { hours: 0, label: '♾️ Permanent (No Expiry)' },
];

const cleanHost = (hostStr) => {
  if (!hostStr) return '';
  return hostStr
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/.*$/, '');
};

const getMonthlySecretToken = () => {
  const customSecret = import.meta.env.VITE_NTFY_TOPIC_SECRET;
  if (customSecret && customSecret !== 'AUTO_MONTHLY') {
    return customSecret;
  }
  const masterSalt = import.meta.env.VITE_NTFY_MASTER_SALT || 'cfr_master_salt_2026';
  const now = new Date();
  const year = now.getUTCFullYear();
  const monthNum = String(now.getUTCMonth() + 1).padStart(2, '0');
  const monthNames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const monthCode = `${monthNames[now.getUTCMonth()]}${year}`;
  
  const raw = `${masterSalt}-${year}-${monthNum}`;
  const digest = SparkMD5.hash(raw).substring(0, 6);
  return `${monthCode}-${digest}`;
};

export default function DriverStationSetup({ onClose }) {
  const [selectedUnit, setSelectedUnit] = useState('chief-master');
  const [shiftHours, setShiftHours] = useState(0);
  const [copiedTopic, setCopiedTopic] = useState(false);
  const [copiedServer, setCopiedServer] = useState(false);
  const [qrFormat, setQrFormat] = useState('web'); // Default to plain 'http://' to avoid TLS app default

  // Default to Tailscale IP 100.95.146.94 if available or current hostname
  const initialHost = window.location.hostname && window.location.hostname !== 'localhost' 
    ? window.location.hostname 
    : '100.95.146.94';
  const [customHostInput, setCustomHostInput] = useState(initialHost);
  const ntfyServerPort = import.meta.env.VITE_NTFY_PORT || '8080';
  
  const selectedUnitObj = APPARATUS_LIST.find(u => u.id === selectedUnit) || APPARATUS_LIST[0];
  
  // Permanent master topic bypasses monthly secret rotation
  const topicSecret = selectedUnitObj.isMaster ? '' : getMonthlySecretToken();
  const finalTopic = topicSecret ? `${selectedUnit}-${topicSecret}` : selectedUnit;

  const effectiveHost = cleanHost(customHostInput) || '100.95.146.94';

  // Construct topic subscription URLs per spec
  const ntfyBaseServerUrl = `http://${effectiveHost}:${ntfyServerPort}`;
  const ntfyWebUrl = `${ntfyBaseServerUrl}/${finalTopic}`;
  const ntfyDeepLink = `ntfy://${effectiveHost}:${ntfyServerPort}/${finalTopic}`;
  const ntfyWsUrl = `ws://${effectiveHost}:${ntfyServerPort}/${finalTopic}/ws`;

  // QR Code payload based on user selection
  const qrPayload = qrFormat === 'web' ? ntfyWebUrl : ntfyDeepLink;

  const handleCopyTopic = () => {
    navigator.clipboard.writeText(ntfyWebUrl);
    setCopiedTopic(true);
    setTimeout(() => setCopiedTopic(false), 2500);
  };

  const handleCopyServer = () => {
    navigator.clipboard.writeText(ntfyBaseServerUrl);
    setCopiedServer(true);
    setTimeout(() => setCopiedServer(false), 2500);
  };

  return (
    <div className="fixed inset-0 bg-slate-950/95 backdrop-blur-md z-[3000] flex flex-col p-4 sm:p-6 text-slate-100 font-sans animate-in fade-in duration-200 overflow-y-auto">
      {/* Header */}
      <div className="max-w-4xl mx-auto w-full flex justify-between items-center border-b border-slate-800 pb-4 mb-6 flex-shrink-0">
        <div>
          <h1 className="text-lg sm:text-xl font-black text-amber-400 tracking-wider flex items-center gap-2.5 select-none">
            <span>📱 DRIVER MOBILE PUSH ALERTS SETUP</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Low-barrier mobile alert dispatch setup for apparatus drivers. Receive loud alarms that bypass Do-Not-Disturb & silent mode.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="bg-slate-900 border border-slate-800 hover:border-slate-700 hover:text-white text-slate-400 px-3.5 py-2 rounded-xl text-xs font-bold transition-all cursor-pointer shadow-md"
        >
          ✕ CLOSE
        </button>
      </div>

      <div className="max-w-4xl mx-auto w-full grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
        {/* Left Column: Unit Selection & Shift Duration */}
        <div className="md:col-span-7 flex flex-col gap-5">
          {/* Step 1: Select Unit */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-300 font-mono mb-3 flex items-center gap-2">
              <span className="bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-md border border-amber-500/30 text-[10px]">STEP 1</span>
              SELECT ASSIGNED APPARATUS
            </h2>

            <div className="grid grid-cols-2 gap-2.5">
              {APPARATUS_LIST.map((unit) => {
                const isSelected = selectedUnit === unit.id;
                return (
                  <button
                    key={unit.id}
                    type="button"
                    onClick={() => setSelectedUnit(unit.id)}
                    className={`flex items-center gap-3 p-3 rounded-xl border text-left transition-all cursor-pointer ${
                      isSelected
                        ? `bg-gradient-to-r ${unit.color} ring-2 ring-amber-400/50 shadow-lg scale-[1.02]`
                        : 'bg-slate-950/60 border-slate-850 hover:border-slate-700 text-slate-300'
                    }`}
                  >
                    <span className="text-xl select-none">{unit.icon}</span>
                    <div className="min-w-0">
                      <div className="text-xs font-black tracking-wider leading-none">{unit.label}</div>
                      <div className="text-[9px] text-slate-400 font-mono mt-1 truncate">{unit.desc}</div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 2: Select Shift Duration */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-300 font-mono mb-3 flex items-center gap-2">
              <span className="bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-md border border-amber-500/30 text-[10px]">STEP 2</span>
              SELECT SHIFT DURATION
            </h2>

            <div className="grid grid-cols-2 gap-2">
              {SHIFT_DURATIONS.map((dur) => {
                const isSelected = shiftHours === dur.hours;
                return (
                  <button
                    key={dur.hours}
                    type="button"
                    onClick={() => setShiftHours(dur.hours)}
                    className={`py-2.5 px-3 rounded-xl border text-xs font-bold font-mono transition-all cursor-pointer ${
                      isSelected
                        ? 'bg-sky-500/20 border-sky-500/50 text-sky-300 ring-1 ring-sky-400/40'
                        : 'bg-slate-950/60 border-slate-850 hover:border-slate-700 text-slate-400'
                    }`}
                  >
                    {dur.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Step 3: Server Address / Tailscale Host */}
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-300 font-mono mb-2 flex items-center gap-2">
              <span className="bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-md border border-purple-500/30 text-[10px]">STEP 3</span>
              SERVER ADDRESS / TAILSCALE HOST
            </h2>
            <p className="text-[10px] text-slate-400 font-mono mb-2.5">
              Specify your Tailscale IP or Hostname (e.g. <span className="text-amber-300 font-bold">100.95.146.94</span>). Prefixes like http:// will be automatically stripped.
            </p>
            <input
              type="text"
              value={customHostInput}
              onChange={(e) => setCustomHostInput(e.target.value)}
              placeholder="e.g. 100.95.146.94 or station-server.tailscale.net"
              className="w-full bg-slate-950 border border-slate-800 text-xs text-amber-300 font-mono font-bold rounded-xl p-2.5 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>

        {/* Right Column: QR Code & Mobile Connection Instructions */}
        <div className="md:col-span-5 flex flex-col gap-5">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl flex flex-col items-center text-center">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-mono mb-1">
              📱 SCAN TO PAIR DRIVER PHONE
            </h2>
            <p className="text-[11px] text-slate-400 font-mono mb-3">
              Scan with phone camera or Ntfy app to subscribe in 1 tap.
            </p>

            {/* QR Format Selector */}
            <div className="flex gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800 mb-3.5 w-full">
              <button
                type="button"
                onClick={() => setQrFormat('app')}
                className={`flex-1 py-1.5 px-2 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                  qrFormat === 'app'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                📲 Ntfy App (ntfy://)
              </button>
              <button
                type="button"
                onClick={() => setQrFormat('web')}
                className={`flex-1 py-1.5 px-2 rounded-lg text-[10px] font-mono font-bold transition-all cursor-pointer ${
                  qrFormat === 'web'
                    ? 'bg-sky-500/20 text-sky-300 border border-sky-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🌐 Browser (http://)
              </button>
            </div>

            {/* QR Code Container */}
            <div className="bg-white p-3.5 rounded-2xl shadow-xl mb-4 border-2 border-amber-400/40">
              <QRCodeSVG
                value={qrPayload}
                size={180}
                bgColor={"#FFFFFF"}
                fgColor={"#020617"}
                level={"H"}
                includeMargin={false}
              />
            </div>

            <div className="text-xs font-mono font-bold text-slate-200 mb-3 bg-slate-950 px-3 py-1.5 rounded-lg border border-slate-800 w-full truncate">
              {selectedUnitObj.label} ({shiftHours === 0 ? 'Permanent' : `${shiftHours}h Shift`})
            </div>

            {/* Copy / Action Buttons */}
            <div className="flex flex-col gap-2 w-full">
              <button
                type="button"
                onClick={handleCopyTopic}
                className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-2.5 px-4 rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>{copiedTopic ? '✓ TOPIC URL COPIED!' : '📋 COPY TOPIC URL (http://...)'}</span>
              </button>

              <button
                type="button"
                onClick={handleCopyServer}
                className="bg-slate-950 border border-slate-800 hover:border-slate-700 text-slate-300 py-2 px-3 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5"
              >
                {copiedServer ? '✓ SERVER URL COPIED!' : '📋 COPY SERVER BASE URL (http://...:8080)'}
              </button>
            </div>

            {/* TLS Warning Alert */}
            <div className="mt-4 p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-left text-[10px] text-amber-200 font-mono leading-relaxed w-full">
              <span className="font-extrabold text-amber-400">⚠️ TLS / UNENCRYPTED HTTP:</span> The local Ntfy push server runs strictly on <span className="text-emerald-400 font-bold font-mono">http://</span> (Port 8080). Do <span className="text-rose-400 font-bold underline">NOT</span> use <span className="font-bold">https://</span> or HTTPS proxies, as SSL handshakes will fail with TLS packet errors.
            </div>

            {/* Quick Setup Instructions */}
            <div className="mt-3 p-3 bg-slate-950/80 border border-slate-850 rounded-xl text-left text-[10px] text-slate-400 font-mono leading-relaxed space-y-1.5 w-full">
              <div className="font-extrabold text-amber-400 uppercase">⚡ 30-Second Setup Guide:</div>
              <div>1. Install free <span className="text-white font-bold">Ntfy</span> app from App Store / Play Store.</div>
              <div>2. Tap <span className="text-white font-bold">+ Subscribe to topic</span>.</div>
              <div>3. Server URL: <span className="text-sky-300 font-bold">{ntfyWebUrl}</span> (<span className="text-amber-400 font-bold">http://</span> plain text, Port 8080).</div>
              <div>4. Protocol: Select <span className="text-purple-300 font-bold">WebSockets</span> (<span className="text-slate-300">{ntfyWsUrl}</span>) for low-latency alerts.</div>
              <div>5. <span className="text-emerald-400 font-bold">Done!</span> Loud siren alerts will ring even when silent mode is ON.</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
