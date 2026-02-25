import { useState, useEffect, useCallback } from "react";
import {
  Settings,
  ChevronDown,
  FolderSync,
  Zap,
  Plus,
  LogOut,
  Loader2,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import vocoIcon from "@/assets/voco-icon.png";
import { useWorkspaces, type Workspace } from "@/hooks/use-workspaces";
import { useVocoProjects, type VocoProject } from "@/hooks/use-voco-projects";
import { useAuth } from "@/hooks/use-auth";
import { useToast } from "@/hooks/use-toast";

const WS_KEY = "voco-active-workspace";
const PROJ_KEY = "voco-active-project";

interface HeaderProps {
  onOpenHistory?: () => void;
  onOpenSettings?: () => void;
  onOpenPricing?: () => void;
}

const Header = ({ onOpenSettings, onOpenPricing }: HeaderProps) => {
  const { signOut } = useAuth();
  const { toast } = useToast();
  const { workspaces, isLoading: wsLoading, createWorkspace } = useWorkspaces();
  const [activeWsId, setActiveWsId] = useState<string | null>(() => localStorage.getItem(WS_KEY));
  const [activeProjId, setActiveProjId] = useState<string | null>(() => localStorage.getItem(PROJ_KEY));
  const [syncing, setSyncing] = useState(false);

  const { projects, isLoading: projLoading, createProject } = useVocoProjects(activeWsId);

  const activeWorkspace = workspaces.find((w) => w.id === activeWsId) ?? workspaces[0] ?? null;
  const activeProject = projects.find((p) => p.id === activeProjId) ?? null;

  useEffect(() => {
    if (!activeWsId && workspaces.length > 0) {
      setActiveWsId(workspaces[0].id);
      localStorage.setItem(WS_KEY, workspaces[0].id);
    }
  }, [workspaces, activeWsId]);

  const selectWorkspace = useCallback((ws: Workspace) => {
    setActiveWsId(ws.id);
    setActiveProjId(null);
    localStorage.setItem(WS_KEY, ws.id);
    localStorage.removeItem(PROJ_KEY);
  }, []);

  const selectProject = useCallback((proj: VocoProject) => {
    setActiveProjId(proj.id);
    localStorage.setItem(PROJ_KEY, proj.id);
  }, []);

  const handleCreateWorkspace = useCallback(async () => {
    const name = window.prompt("Workspace name:");
    if (!name?.trim()) return;
    try {
      const ws = await createWorkspace.mutateAsync(name.trim());
      selectWorkspace(ws);
      toast({ title: "Workspace created", description: ws.name });
    } catch (err) {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    }
  }, [createWorkspace, selectWorkspace, toast]);

  const handleCreateProject = useCallback(async () => {
    if (!activeWsId) {
      toast({ title: "Select a workspace first", variant: "destructive" });
      return;
    }
    const name = window.prompt("Project name:");
    if (!name?.trim()) return;
    try {
      const proj = await createProject.mutateAsync({ name: name.trim(), workspaceId: activeWsId });
      selectProject(proj);
      toast({ title: "Project created", description: proj.name });
    } catch (err) {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    }
  }, [activeWsId, createProject, selectProject, toast]);

  const handleSyncProject = useCallback(async () => {
    if (!activeProject) {
      toast({ title: "Select a project first", variant: "destructive" });
      return;
    }
    setSyncing(true);
    try {
      if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
        const { invoke } = await import("@tauri-apps/api/core");
        const path = await invoke<string | null>("open_folder_dialog");
        if (path) {
          toast({ title: "Project synced", description: path });
        }
      } else {
        toast({ title: "Sync available in desktop app", description: "Open Voco via Tauri to sync local folders." });
      }
    } catch (err) {
      toast({ title: "Sync failed", description: String(err), variant: "destructive" });
    } finally {
      setSyncing(false);
    }
  }, [activeProject, toast]);

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-5 h-14 bg-[#0A0A0A]/90 backdrop-blur-md border-b border-white/[0.06]">
      {/* Left: Logo */}
      <div className="flex items-center gap-3">
        <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-[#111] border border-white/[0.06] p-1.5">
          <img
            src={vocoIcon}
            alt="Voco"
            className="w-full h-full object-contain"
          />
        </div>
      </div>

      {/* Center: Workspace / Project breadcrumbs */}
      <div className="flex items-center gap-1 text-xs">
        {/* Workspace selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] transition-colors">
              <span>{wsLoading ? "Loading..." : activeWorkspace?.name ?? "No workspace"}</span>
              <ChevronDown className="w-3 h-3 opacity-50" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-zinc-900 border-zinc-700 text-zinc-200 min-w-[180px]">
            {workspaces.map((ws) => (
              <DropdownMenuItem
                key={ws.id}
                onClick={() => selectWorkspace(ws)}
                className={`text-xs cursor-pointer ${ws.id === activeWsId ? "text-voco-cyan font-medium" : "text-zinc-300"}`}
              >
                {ws.name}
                <span className="ml-auto text-zinc-600 text-[10px]">{ws.tier}</span>
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator className="bg-zinc-700" />
            <DropdownMenuItem onClick={handleCreateWorkspace} className="text-xs text-zinc-400 cursor-pointer">
              <Plus className="w-3 h-3 mr-1.5" />
              New workspace
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <span className="text-zinc-600">/</span>

        {/* Project selector */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors">
              <span>{projLoading ? "Loading..." : activeProject?.name ?? "No project"}</span>
              <ChevronDown className="w-3 h-3 opacity-50" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent className="bg-zinc-900 border-zinc-700 text-zinc-200 min-w-[180px]">
            {projects.length === 0 && (
              <DropdownMenuItem disabled className="text-xs text-zinc-600">
                No projects yet
              </DropdownMenuItem>
            )}
            {projects.map((proj) => (
              <DropdownMenuItem
                key={proj.id}
                onClick={() => selectProject(proj)}
                className={`text-xs cursor-pointer ${proj.id === activeProjId ? "text-voco-cyan font-medium" : "text-zinc-300"}`}
              >
                {proj.name}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator className="bg-zinc-700" />
            <DropdownMenuItem onClick={handleCreateProject} className="text-xs text-zinc-400 cursor-pointer">
              <Plus className="w-3 h-3 mr-1.5" />
              New project
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <span className="text-zinc-600">/</span>

        {/* Sync project */}
        <button
          onClick={handleSyncProject}
          disabled={syncing}
          className="flex items-center gap-1 px-2.5 py-1.5 rounded-md text-zinc-500 hover:text-zinc-300 hover:bg-white/[0.04] transition-colors disabled:opacity-50"
        >
          {syncing ? <Loader2 className="w-3 h-3 animate-spin" /> : <FolderSync className="w-3 h-3" />}
          <span>Sync</span>
        </button>
      </div>

      {/* Right: Upgrade CTA + Settings + Sign Out */}
      <div className="flex items-center gap-2">
        <Button
          onClick={onOpenPricing}
          size="sm"
          className="h-7 px-3 gap-1.5 bg-voco-green/20 hover:bg-voco-green/30 text-voco-cyan hover:text-voco-cyan border border-voco-green/30 text-xs font-medium"
          variant="ghost"
        >
          <Zap className="h-3 w-3" />
          Upgrade
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenSettings}
          className="text-zinc-500 hover:text-zinc-300 h-8 w-8"
        >
          <Settings className="h-4 w-4" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={signOut}
          className="text-zinc-500 hover:text-zinc-300 h-8 w-8"
          title="Sign out"
        >
          <LogOut className="h-4 w-4" />
        </Button>
      </div>
    </header>
  );
};

export default Header;
