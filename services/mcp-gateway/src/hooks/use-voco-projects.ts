import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/integrations/supabase/client";
import { useAuth } from "@/hooks/use-auth";

export interface VocoProject {
  id: string;
  owner_id: string;
  workspace_id: string;
  name: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export function useVocoProjects(workspaceId: string | null) {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ["voco-projects", workspaceId],
    queryFn: async () => {
      if (!workspaceId) return [];
      const { data, error } = await supabase
        .from("voco_projects")
        .select("*")
        .eq("workspace_id", workspaceId)
        .order("created_at", { ascending: false });
      if (error) throw error;
      return data as VocoProject[];
    },
    enabled: !!user && !!workspaceId,
  });

  const createProject = useMutation({
    mutationFn: async ({ name, workspaceId: wsId }: { name: string; workspaceId: string }) => {
      if (!user) throw new Error("Not authenticated");
      const { data, error } = await supabase
        .from("voco_projects")
        .insert({ name, workspace_id: wsId, owner_id: user.id })
        .select()
        .single();
      if (error) throw error;
      return data as VocoProject;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voco-projects"] });
    },
  });

  const updateProject = useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) => {
      const { error } = await supabase
        .from("voco_projects")
        .update({ name })
        .eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voco-projects"] });
    },
  });

  const deleteProject = useMutation({
    mutationFn: async (id: string) => {
      const { error } = await supabase
        .from("voco_projects")
        .delete()
        .eq("id", id);
      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["voco-projects"] });
    },
  });

  return {
    projects: projectsQuery.data ?? [],
    isLoading: projectsQuery.isLoading,
    createProject,
    updateProject,
    deleteProject,
  };
}
