import React, { useState } from 'react';
import { QRCodeSVG } from 'qrcode.react';

const cleanHost = (hostStr) => {
  if (!hostStr) return '';
  return hostStr
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/.*$/, '');
};

export default function DriverStationSetup({ onClose }) {
  const [copiedTopic, setCopiedTopic] = useState(false);
  const [copiedServer, setCopiedServer] = useState(false);
  const [qrFormat, setQrFormat] = useState('app'); // 'app' (ntfy://) or 'web' (http://)

  const initialHost = window.location.hostname && window.location.hostname !== 'localhost' 
    ? window.location.hostname 
    : '100.95.146.94';
  const [customHostInput, setCustomHostInput] = useState(initialHost);
  const ntfyServerPort = import.meta.env.VITE_NTFY_PORT || '8080';
  
  const finalTopic = 'cfr-dispatches';
  const effectiveHost = cleanHost(customHostInput) || '100.95.146.94';

  const ntfyBaseServerUrl = `http://${effectiveHost}:${ntfyServerPort}`;
  const ntfyWebUrl = `${ntfyBaseServerUrl}/${finalTopic}`;
  const ntfyDeepLink = `ntfy://${effectiveHost}:${ntfyServerPort}/${finalTopic}`;
  const ntfyWsUrl = `ws://${effectiveHost}:${ntfyServerPort}/${finalTopic}/ws`;

  const qrPayload = qrFormat === 'app' ? ntfyDeepLink : ntfyWebUrl;

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
      <div className="max-w-3xl mx-auto w-full flex justify-between items-center border-b border-slate-800 pb-4 mb-6 flex-shrink-0">
        <div>
          <h1 className="text-lg sm:text-xl font-black text-amber-400 tracking-wider flex items-center gap-2.5 select-none">
            <span>📱 DRIVER MOBILE PUSH ALERTS SETUP</span>
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Direct local Ntfy push notifications for apparatus drivers & station officers.
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

      <div className="max-w-3xl mx-auto w-full grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
        {/* Left Column: Server Configuration */}
        <div className="md:col-span-6 flex flex-col gap-5">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-xl">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-300 font-mono mb-3 flex items-center gap-2">
              <span className="bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded-md border border-amber-500/30 text-[10px]">CONFIG</span>
              LOCAL NTFY SERVER ENDPOINT
            </h2>

            <div className="flex flex-col gap-3">
              <div>
                <label className="text-[10px] text-slate-400 font-mono block mb-1">
                  Station Hostname or Tailscale IP:
                </label>
                <input
                  type="text"
                  value={customHostInput}
                  onChange={(e) => setCustomHostInput(e.target.value)}
                  placeholder="e.g. 100.95.146.94"
                  className="w-full bg-slate-950 border border-slate-800 text-xs text-amber-300 font-mono font-bold rounded-xl p-2.5 focus:outline-none focus:border-amber-500"
                />
              </div>

              <div className="p-3 bg-slate-950/80 rounded-xl border border-slate-800/80 font-mono text-[11px] space-y-1">
                <div className="text-slate-400 text-[10px]">Active Topic:</div>
                <div className="text-amber-400 font-bold">{finalTopic}</div>
                <div className="text-slate-400 text-[10px] pt-1">Server URL:</div>
                <div className="text-sky-300 font-bold truncate">{ntfyBaseServerUrl}</div>
              </div>
            </div>
          </div>

          {/* Quick Setup Instructions */}
          <div className="p-4 bg-slate-900/80 border border-slate-800 rounded-2xl text-left text-xs text-slate-300 font-mono leading-relaxed space-y-2">
            <div className="font-extrabold text-amber-400 uppercase text-[11px]">⚡ 30-Second Setup Guide:</div>
            <div>1. Install the free <span className="text-white font-bold">Ntfy</span> app on your phone.</div>
            <div>2. In Ntfy settings, ensure <span className="text-amber-300 font-bold">Use another server</span> or default server is set to <span className="text-sky-300 font-bold">{ntfyBaseServerUrl}</span>.</div>
            <div>3. Subscribe to topic <span className="text-emerald-400 font-bold">{finalTopic}</span>.</div>
            <div>4. Protocol: <span className="text-purple-300 font-bold">WebSockets</span> (<span className="text-slate-400">{ntfyWsUrl}</span>).</div>
          </div>
        </div>

        {/* Right Column: QR Code */}
        <div className="md:col-span-6 flex flex-col gap-5">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl flex flex-col items-center text-center">
            <h2 className="text-xs font-extrabold uppercase tracking-wider text-amber-400 font-mono mb-1">
              📱 SCAN TO SUBSCRIBE
            </h2>
            <p className="text-[11px] text-slate-400 font-mono mb-3">
              Scan with your phone camera or Ntfy app.
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
              {finalTopic}
            </div>

            {/* Copy Action Buttons */}
            <div className="flex flex-col gap-2 w-full">
              <button
                type="button"
                onClick={handleCopyTopic}
                className="bg-amber-500 hover:bg-amber-400 text-slate-950 font-black py-2.5 px-4 rounded-xl text-xs transition-all shadow-md flex items-center justify-center gap-2 cursor-pointer"
              >
                <span>{copiedTopic ? '✓ TOPIC URL COPIED!' : '📋 COPY TOPIC URL'}</span>
              </button>

              <button
                type="button"
                onClick={handleCopyServer}
                className="bg-slate-950 border border-slate-800 hover:border-slate-700 text-slate-300 py-2 px-3 rounded-xl text-xs font-mono font-bold transition-all cursor-pointer flex items-center justify-center gap-1.5"
              >
                {copiedServer ? '✓ SERVER URL COPIED!' : '📋 COPY SERVER BASE URL'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

