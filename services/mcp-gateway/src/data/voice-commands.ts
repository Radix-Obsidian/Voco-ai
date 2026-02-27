export interface VoiceCommand {
  category: string;
  command: string;
  description: string;
  example: string;
}

export const VOICE_COMMANDS: VoiceCommand[] = [
  {
    category: "Code Search",
    command: "Show me the structure of [project/file]",
    description: "Explore codebase architecture",
    example: "Show me the structure of the cognitive-engine project",
  },
  {
    category: "Code Generation",
    command: "Create a [type] that [does something]",
    description: "Generate new code",
    example: "Create a function that validates email addresses",
  },
  {
    category: "Code Editing",
    command: "Edit [file] — [change description]",
    description: "Modify existing code",
    example: "Edit src/hooks/use-auth.ts — add isFounder boolean",
  },
  {
    category: "Search",
    command: "Search for [pattern/keyword]",
    description: "Find code across the codebase",
    example: "Search for all uses of AsyncSqliteSaver",
  },
  {
    category: "Git",
    command: "Show me the diff for [file]",
    description: "Review changes",
    example: "Show me the diff for src/App.tsx",
  },
  {
    category: "Architecture",
    command: "Explain the [component/module]",
    description: "Understand system design",
    example: "Explain the LangGraph state machine",
  },
];
