import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AppPage from "./pages/AppPage";
import ProtectedRoute from "./components/ProtectedRoute";

const queryClient = new QueryClient();

const isDemoMode = new URLSearchParams(window.location.search).get("demo") === "true";

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      {isDemoMode ? (
        <AppPage />
      ) : (
        <ProtectedRoute>
          <AppPage />
        </ProtectedRoute>
      )}
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
