import { useAuth } from "@/hooks/use-auth";
import AuthModal from "./AuthModal";

const ProtectedRoute = ({ children }: { children: React.ReactNode }) => {
  const { session, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="h-8 w-8 rounded-full border-2 border-muted-foreground/30 border-t-foreground animate-spin" />
      </div>
    );
  }

  if (!session) {
    // Always force open — prevent dismiss via Escape or click-outside
    return <AuthModal open={true} onOpenChange={() => {}} defaultTab="signin" />;
  }

  return <>{children}</>;
};

export default ProtectedRoute;
