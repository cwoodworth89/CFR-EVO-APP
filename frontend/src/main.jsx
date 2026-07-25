import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import L from 'leaflet'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import './index.css'
import App from './App.jsx'

// Fix Leaflet's default icon asset paths when bundling (Vite/GitHub Pages)
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Uncaught application runtime error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="w-screen h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 text-center select-none font-sans">
          <div className="max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col items-center gap-4 text-left">
            <div className="flex items-center gap-2 text-rose-400">
              <span className="text-3xl">⚠️</span>
              <h1 className="text-lg font-bold uppercase tracking-wider">Application Diagnostic Error</h1>
            </div>
            <p className="text-xs text-slate-400 font-mono leading-relaxed">
              An unhandled exception occurred during application execution:
            </p>
            {this.state.error && (
              <div className="w-full bg-slate-950 border border-slate-800 rounded-xl p-3 text-[11px] font-mono text-rose-300 overflow-x-auto max-h-48 whitespace-pre-wrap">
                {this.state.error.toString()}
                {this.state.error.stack && (
                  <div className="text-[9.5px] text-slate-500 mt-2 border-t border-slate-800 pt-2">
                    {this.state.error.stack}
                  </div>
                )}
              </div>
            )}
            <button
              onClick={() => {
                this.setState({ hasError: false, error: null });
                window.location.reload();
              }}
              className="bg-sky-500 hover:bg-sky-400 text-black font-extrabold px-5 py-2.5 rounded-xl text-xs shadow-lg transition cursor-pointer self-center"
            >
              🔄 RELOAD APPLICATION
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)
