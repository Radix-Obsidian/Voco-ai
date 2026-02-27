import { useEffect, useState } from "react";

interface SplashScreenProps {
  error: string | null;
  onRetry?: () => void;
  /** Minimum time (ms) to display the splash before auto-dismissing. Default: 0 (dismiss immediately). */
  minDisplayTime?: number;
  /** Called when the minimum display time has elapsed (only when no error). */
  onReady?: () => void;
}

const SplashScreen = ({ error, onRetry, minDisplayTime = 0, onReady }: SplashScreenProps) => {
  const [dots, setDots] = useState("");
  const [fadingOut, setFadingOut] = useState(false);

  useEffect(() => {
    if (error) return;
    const interval = setInterval(() => {
      setDots((prev) => (prev.length >= 3 ? "" : prev + "."));
    }, 500);
    return () => clearInterval(interval);
  }, [error]);

  useEffect(() => {
    if (error || !minDisplayTime || !onReady) return;
    const fadeStart = setTimeout(() => setFadingOut(true), minDisplayTime - 600);
    const dismiss = setTimeout(onReady, minDisplayTime);
    return () => { clearTimeout(fadeStart); clearTimeout(dismiss); };
  }, [error, minDisplayTime, onReady]);

  return (
    <div className={`flex items-center justify-center min-h-screen bg-zinc-950 text-white transition-opacity duration-500 ${fadingOut ? "opacity-0" : "opacity-100"}`}>
      <div className="text-center space-y-6 max-w-md px-8">
        {/* Logo / Brand */}
        <div className="space-y-2">
          <h1 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
            Voco
          </h1>
          <p className="text-zinc-500 text-sm font-medium">The Intent OS</p>
        </div>

        {error ? (
          /* Error state */
          <div className="space-y-4">
            <div className="bg-red-950/50 border border-red-800/50 rounded-lg p-4">
              <p className="text-red-400 text-sm font-medium mb-1">
                Failed to start backend services
              </p>
              <p className="text-red-300/70 text-xs font-mono">{error}</p>
            </div>
            <div className="space-y-2 text-xs text-zinc-500">
              <p>Make sure Python and uv are installed and on your PATH.</p>
              <p>
                You can also start services manually:
                <code className="block mt-1 bg-zinc-900 rounded px-2 py-1 text-zinc-400">
                  cd services/cognitive-engine && uv run uvicorn src.main:app
                  --port 8001
                </code>
              </p>
            </div>
            {onRetry && (
              <button
                onClick={onRetry}
                className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium rounded-lg transition-colors"
              >
                Retry
              </button>
            )}
          </div>
        ) : (
          /* Loading state */
          <div className="space-y-4">
            {/* Spinner */}
            <div className="flex justify-center">
              <div className="w-8 h-8 border-2 border-violet-500/30 border-t-violet-500 rounded-full animate-spin" />
            </div>
            <p className="text-zinc-400 text-sm">
              Initializing Voco{dots}
            </p>
            <p className="text-zinc-600 text-xs">
              Starting cognitive engine and AI proxy
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default SplashScreen;
