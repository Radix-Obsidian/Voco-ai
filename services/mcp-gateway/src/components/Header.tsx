import { Settings, MessageSquare, ChevronDown, FolderSync } from "lucide-react";
import { Button } from "@/components/ui/button";
import vocoLogo from "@/assets/voco-logo.svg";
import vocoIcon from "@/assets/voco-icon.svg";

interface HeaderProps {
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
}

const Header = ({ onOpenSettings }: HeaderProps) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-5 h-14 bg-[#0A0A0A]/90 backdrop-blur-md border-b border-white/[0.06]">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center justify-center w-8 h-8 rounded-lg bg-[#111] border border-white/[0.06]">
          <img
            src={vocoIcon}
            alt="Voco"
            className="w-5 h-5 object-contain drop-shadow-[0_0_6px_rgba(0,255,170,0.5)]"
          />
        </div>
        <img
          src={vocoLogo}
          alt="Voco"
          className="h-5 w-auto object-contain brightness-0 invert"
        />
      </div>

      {/* Center: Workspace breadcrumbs */}
      <div className="flex items-center gap-1 text-xs">
        <button className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors">
          <span>Test Workspace</span>
          <ChevronDown className="w-3 h-3 opacity-50" />
        </button>
        <span className="text-zinc-600">/</span>
        <button className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors">
          <span>No project</span>
          <ChevronDown className="w-3 h-3 opacity-50" />
        </button>
        <span className="text-zinc-600">/</span>
        <button className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors">
          <FolderSync className="w-3 h-3" />
          <span>Sync Project</span>
        </button>
      </div>

      {/* Right: Quota + Settings */}
      <div className="flex items-center gap-3">
        {/* Quota pill */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/[0.06] text-xs">
          <span className="text-zinc-400">0 / 5 free</span>
          <div className="w-12 h-1 rounded-full bg-white/[0.06] overflow-hidden">
            <div className="w-0 h-full rounded-full bg-voco-emerald" />
          </div>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenSettings}
          className="text-zinc-500 hover:text-zinc-300 h-8 w-8"
        >
          <MessageSquare className="h-4 w-4" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenSettings}
          className="text-zinc-500 hover:text-zinc-300 h-8 w-8"
        >
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
};

export default Header;
