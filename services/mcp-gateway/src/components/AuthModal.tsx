import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { supabase } from "@/integrations/supabase/client";
import { useToast } from "@/hooks/use-toast";
import { openExternalLink, EXTERNAL_LINKS } from "@/lib/external-links";
import { invoke } from "@tauri-apps/api/core";

interface AuthModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultTab?: "signin" | "signup";
}

const AuthModal = ({ open, onOpenChange, defaultTab = "signin" }: AuthModalProps) => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    // IP-based free account limit: check before calling Supabase signup
    try {
      const ipCheck = await invoke<{ allowed: boolean; message: string }>("check_signup_ip", {
        customerEmail: email,
      });
      if (!ipCheck.allowed) {
        setLoading(false);
        toast({
          title: "Account limit reached",
          description: ipCheck.message || "One free account per device. Upgrade to Pro for unlimited access.",
          variant: "destructive",
        });
        return;
      }
    } catch (ipErr) {
      // Fail open — if the check itself errors, allow signup to proceed
      console.warn("[AuthModal] IP check failed (allowing signup):", ipErr);
    }

    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { emailRedirectTo: window.location.origin },
    });
    setLoading(false);
    if (error) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } else {
      toast({ title: "Check your email", description: "We sent you a verification link." });

      // Record the IP after successful signup (fire-and-forget)
      const userId = data?.user?.id;
      if (userId) {
        invoke("record_signup_ip", { userId, customerEmail: email }).catch((err) =>
          console.warn("[AuthModal] Failed to record signup IP:", err)
        );
      }
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    setLoading(false);
    if (error) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    } else {
      onOpenChange(false);
      // Auth state change will automatically trigger ProtectedRoute to render AppPage
    }
  };

  const handleGoogle = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: window.location.origin,
      },
    });
    if (error) {
      toast({ title: "Error", description: error.message, variant: "destructive" });
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-black/80 backdrop-blur-2xl border border-white/10 sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="text-foreground text-xl">
            {defaultTab === "signup" ? "Join the Voco Beta" : "Welcome Back"}
          </DialogTitle>
          <DialogDescription className="text-muted-foreground">
            {defaultTab === "signup"
              ? "50 spots. Sub-300ms voice-to-code on your localhost."
              : "Sign in to your Voco account."}
          </DialogDescription>
        </DialogHeader>
        {defaultTab === "signup" && (
          <div className="text-center text-xs text-muted-foreground">
            <button
              type="button"
              onClick={() => openExternalLink(EXTERNAL_LINKS.features)}
              className="text-voco-cyan hover:text-voco-cyan/80 underline underline-offset-2 transition-colors"
            >
              Learn more about Voco
            </button>
          </div>
        )}

        <Button
          variant="outline"
          className="w-full border-white/10 bg-white/5 hover:bg-white/10 text-foreground"
          onClick={handleGoogle}
        >
          <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
          Continue with Google
        </Button>

        <div className="relative my-2">
          <div className="absolute inset-0 flex items-center"><span className="w-full border-t border-white/10" /></div>
          <div className="relative flex justify-center text-xs"><span className="bg-black/80 px-2 text-muted-foreground">or</span></div>
        </div>

        <Tabs defaultValue={defaultTab} className="w-full">
          <TabsList className="w-full bg-white/5 border border-white/10">
            <TabsTrigger value="signin" className="flex-1 data-[state=active]:bg-white/10">Sign In</TabsTrigger>
            <TabsTrigger value="signup" className="flex-1 data-[state=active]:bg-white/10">Sign Up</TabsTrigger>
          </TabsList>

          <TabsContent value="signin">
            <form onSubmit={handleSignIn} className="space-y-3 mt-3">
              <div><Label className="text-muted-foreground text-xs">Email</Label><Input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="bg-white/5 border-white/10 text-foreground" /></div>
              <div><Label className="text-muted-foreground text-xs">Password</Label><Input type="password" value={password} onChange={e => setPassword(e.target.value)} required className="bg-white/5 border-white/10 text-foreground" /></div>
              <Button type="submit" disabled={loading} className="w-full bg-[#0FF984] hover:bg-[#0de070] text-black">{loading ? "Signing in..." : "Sign In"}</Button>
            </form>
          </TabsContent>

          <TabsContent value="signup">
            <form onSubmit={handleSignUp} className="space-y-3 mt-3">
              <div><Label className="text-muted-foreground text-xs">Email</Label><Input type="email" value={email} onChange={e => setEmail(e.target.value)} required className="bg-white/5 border-white/10 text-foreground" /></div>
              <div><Label className="text-muted-foreground text-xs">Password</Label><Input type="password" value={password} onChange={e => setPassword(e.target.value)} required minLength={6} className="bg-white/5 border-white/10 text-foreground" /></div>
              <Button type="submit" disabled={loading} className="w-full bg-[#0FF984] hover:bg-[#0de070] text-black">{loading ? "Creating account..." : "Claim Your Beta Spot"}</Button>
              <p className="text-center text-xs text-muted-foreground mt-2">Free tier forever. No credit card required.</p>
            </form>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
};

export default AuthModal;
