import React, { useState, useEffect, useRef } from 'react';

export default function AudioWaveformPlayer({
  audioSignedUrl,
  audioDuration,
  audioRef: externalAudioRef,
}) {
  const localAudioRef = useRef(null);
  const audioRef = externalAudioRef || localAudioRef;
  const canvasRef = useRef(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(audioDuration || 0);

  useEffect(() => {
    if (audioDuration) {
      setDuration(audioDuration);
    }
  }, [audioDuration]);

  // Reset playback state on URL change
  useEffect(() => {
    setIsPlaying(false);
    setCurrentTime(0);
  }, [audioSignedUrl]);

  // Draw simulated or reactive waveform on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    ctx.clearRect(0, 0, width, height);

    const barCount = 48;
    const barWidth = width / barCount - 2;
    const progress = duration > 0 ? currentTime / duration : 0;

    for (let i = 0; i < barCount; i++) {
      const x = i * (barWidth + 2);
      // Generate pseudo-random bar heights based on index to simulate audio spectrum
      const factor = Math.sin((i / barCount) * Math.PI) * 0.7 + 0.3;
      const wave = Math.abs(Math.sin(i * 1.5)) * 0.5 + 0.5;
      const barHeight = Math.max(4, height * 0.8 * factor * wave);
      const y = (height - barHeight) / 2;

      const isPlayed = i / barCount <= progress;
      ctx.fillStyle = isPlayed ? '#38bdf8' : '#334155';
      ctx.beginPath();
      ctx.roundRect ? ctx.roundRect(x, y, barWidth, barHeight, 2) : ctx.rect(x, y, barWidth, barHeight);
      ctx.fill();
    }
  }, [currentTime, duration, audioSignedUrl]);

  const handlePlayPause = () => {
    if (!audioRef.current) return;
    if (audioRef.current.paused) {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(err => {
        console.warn('Audio playback error:', err);
      });
    } else {
      audioRef.current.pause();
      setIsPlaying(false);
    }
  };

  const handleRewind = (seconds = 5) => {
    if (!audioRef.current) return;
    const newTime = Math.max(0, audioRef.current.currentTime - seconds);
    audioRef.current.currentTime = newTime;
    setCurrentTime(newTime);
    if (audioRef.current.paused) {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      if (audioRef.current.duration && !isNaN(audioRef.current.duration)) {
        setDuration(audioRef.current.duration);
      }
    }
  };

  const handleSeek = (e) => {
    const canvas = canvasRef.current;
    if (!canvas || !audioRef.current || !duration) return;
    const rect = canvas.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    const targetTime = ratio * duration;
    audioRef.current.currentTime = targetTime;
    setCurrentTime(targetTime);
  };

  const formatTime = (sec) => {
    if (sec == null || isNaN(sec)) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${String(s).padStart(2, '0')}`;
  };

  return (
    <div className="flex flex-col gap-2 bg-slate-950 p-3 border border-slate-850 rounded-xl">
      <div className="flex justify-between items-center text-[10px] text-slate-400 font-extrabold uppercase font-mono">
        <span className="flex items-center gap-1.5 text-slate-300">
          <span>🎙️</span>
          <span>Dispatch Recording & Waveform</span>
        </span>
        <span className="text-sky-400 font-bold">
          {formatTime(currentTime)} / {formatTime(duration)}
        </span>
      </div>

      {audioSignedUrl ? (
        <div className="flex flex-col gap-2 mt-1">
          {/* Waveform Canvas */}
          <div
            className="w-full bg-slate-900 border border-slate-800 rounded-lg p-2 cursor-pointer hover:border-sky-500/50 transition-colors"
            onClick={handleSeek}
            title="Click waveform to scrub"
          >
            <canvas
              ref={canvasRef}
              width={400}
              height={36}
              className="w-full h-9 block"
            />
          </div>

          {/* Hidden native audio element synced with controls */}
          <audio
            ref={audioRef}
            src={audioSignedUrl}
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onEnded={() => {
              setIsPlaying(false);
              setCurrentTime(0);
            }}
            preload="auto"
            className="hidden"
          />

          {/* Player Controls Bar */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={handlePlayPause}
                className="px-3 py-1.5 bg-sky-500 hover:bg-sky-400 text-slate-950 rounded-lg text-xs font-mono font-black transition-all cursor-pointer shadow-md flex items-center gap-1 active:scale-95"
              >
                <span>{isPlaying ? '⏸️ PAUSE' : '▶️ PLAY'}</span>
              </button>

              <button
                type="button"
                onClick={() => handleRewind(5)}
                className="px-2.5 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 text-slate-300 hover:text-white rounded-lg text-[11px] font-mono font-bold whitespace-nowrap transition-all cursor-pointer active:scale-95"
                title="Skip back 5 seconds"
              >
                ⏪ -5s
              </button>
            </div>

            <div className="text-[9.5px] font-mono text-slate-500 truncate max-w-[140px]">
              {audioSignedUrl.split('/').pop()}
            </div>
          </div>
        </div>
      ) : (
        <div className="text-[10px] text-slate-500 font-mono py-3 italic animate-pulse text-center bg-slate-900/50 rounded-lg border border-slate-850">
          No dispatch audio recording available
        </div>
      )}
    </div>
  );
}
