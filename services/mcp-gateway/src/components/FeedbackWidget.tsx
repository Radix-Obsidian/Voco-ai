import { useState, useCallback } from "react";
import { MessageSquareHeart, Star, Send, X, Loader2 } from "lucide-react";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";

export function FeedbackWidget() {
  const [open, setOpen] = useState(false);
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const { user } = useAuth();
  const { toast } = useToast();

  const handleSubmit = useCallback(async () => {
    if (!message.trim() && rating === 0) return;
    setSending(true);
    try {
      const { error } = await supabase.from("feedback").insert({
        user_id: user?.id ?? null,
        rating,
        message: message.trim(),
        category: "beta_feedback",
        page: window.location.pathname,
      });
      if (error) throw error;
      toast({ title: "Thanks!", description: "We read every submission." });
      setMessage("");
      setRating(0);
      setOpen(false);
    } catch (err) {
      toast({ title: "Failed to send", description: String(err), variant: "destructive" });
    } finally {
      setSending(false);
    }
  }, [message, rating, user, toast]);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-full bg-gradient-to-r from-voco-purple to-voco-cyan hover:opacity-90 text-white text-sm font-medium shadow-lg shadow-voco-purple/30 transition-all hover:scale-105"
      >
        <MessageSquareHeart className="h-4 w-4" />
        Feedback
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 w-80 rounded-2xl bg-zinc-900 border border-zinc-700 shadow-2xl overflow-hidden animate-in slide-in-from-bottom-4 fade-in duration-200">
      <div className="flex items-center justify-between px-5 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-100 flex items-center gap-2">
          <MessageSquareHeart className="h-4 w-4 text-voco-cyan" />
          How&apos;s Voco today?
        </h3>
        <button onClick={() => setOpen(false)} className="text-zinc-500 hover:text-zinc-300 transition-colors">
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="p-5 space-y-4">
        <div className="flex items-center justify-center gap-1">
          {[1, 2, 3, 4, 5].map((star) => (
            <button
              key={star}
              onClick={() => setRating(star)}
              onMouseEnter={() => setHover(star)}
              onMouseLeave={() => setHover(0)}
              className="p-1 transition-transform hover:scale-110"
            >
              <Star
                className={`h-6 w-6 transition-colors ${
                  star <= (hover || rating)
                    ? "text-voco-cyan fill-voco-cyan"
                    : "text-zinc-600"
                }`}
              />
            </button>
          ))}
        </div>

        <textarea
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="What can we improve? Bugs, ideas, praise — all welcome."
          rows={3}
          className="w-full resize-none rounded-lg bg-zinc-800 border border-zinc-700 text-sm text-zinc-200 placeholder-zinc-600 p-3 focus:outline-none focus:border-voco-cyan/40 transition-colors"
        />

        <button
          onClick={handleSubmit}
          disabled={sending || (!message.trim() && rating === 0)}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-gradient-to-r from-voco-purple to-voco-cyan hover:opacity-90 text-white text-sm font-medium transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {sending ? "Sending..." : "Send Feedback"}
        </button>

        <p className="text-center text-[10px] text-zinc-600">
          Founding team reads every submission.
        </p>
      </div>
    </div>
  );
}
