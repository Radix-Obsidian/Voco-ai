// WebMCP (Model Context Protocol) navigator extension types
// https://github.com/modelcontextprotocol/specification

interface ModelContextTool {
  name: string;
  input: Record<string, unknown>;
}

interface ModelContext {
  callTool(tool: ModelContextTool): Promise<unknown>;
}

interface Navigator {
  modelContext?: ModelContext;
}
