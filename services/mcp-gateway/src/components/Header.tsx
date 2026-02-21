import { Clock, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import vocoLogo from "@/assets/voco-logo.svg";

interface HeaderProps {
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
}

const Header = ({ onOpenHistory, onOpenSettings }: HeaderProps) => {
  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3">
      <div className="flex items-center gap-3">
        {onOpenHistory && (
          <Button variant="ghost" size="icon" onClick={onOpenHistory} className="text-muted-foreground opacity-40 hover:opacity-100 transition-opacity h-8 w-8">
            <Clock className="h-4 w-4" />
          </Button>
        )}
        <img src={vocoLogo} alt="Voco" className="h-10 w-auto" />
      </div>
      {onOpenSettings && (
        <Button variant="ghost" size="icon" onClick={onOpenSettings} className="text-muted-foreground opacity-40 hover:opacity-100 transition-opacity h-8 w-8">
          <Settings className="h-4 w-4" />
        </Button>
      )}
    </header>
  );
};

export default Header;
