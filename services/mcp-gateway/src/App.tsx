import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ErrorBoundary from "./components/ErrorBoundary";
import AppPage from "./pages/AppPage";
import ProtectedRoute from "./components/ProtectedRoute";
import SplashScreen from "./components/SplashScreen";
import { useBackendReady } from "./hooks/use-backend-ready";
import { useState, useCallback } from "react";

const queryClient = new QueryClient();

const SPLASH_MIN_DISPLAY_MS = 7000;

const AppInner = () => {
  const { isReady, error } = useBackendReady();
  const [splashDone, setSplashDone] = useState(false);
  const handleSplashReady = useCallback(() => setSplashDone(true), []);

  if (error) {
    return <SplashScreen error={error} onRetry={() => window.location.reload()} />;
  }

  if (!isReady || !splashDone) {
    return (
      <SplashScreen
        error={null}
        minDisplayTime={SPLASH_MIN_DISPLAY_MS}
        onReady={handleSplashReady}
      />
    );
  }

  return (
    <>
      <Toaster />
      <Sonner />
      <ProtectedRoute>
        <AppPage />
      </ProtectedRoute>
    </>
  );
};

const App = () => (
  <ErrorBoundary>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <AppInner />
      </TooltipProvider>
    </QueryClientProvider>
  </ErrorBoundary>
);

export default App;
