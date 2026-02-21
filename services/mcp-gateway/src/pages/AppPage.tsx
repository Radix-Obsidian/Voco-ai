import { useEffect } from "react";
import Header from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card";
import { useVocoSocket } from "@/hooks/use-voco-socket";
import { useAudioCapture } from "@/hooks/use-audio-capture";
import { GhostTerminal } from "@/components/GhostTerminal";
import { ReviewDeck } from "@/components/ReviewDeck";
import { CommandApproval } from "@/components/CommandApproval";

const AppPage = () => {
  const {
    isConnected,
    bargeInActive,
    sendAudioChunk,
    connect,
    disconnect,
    terminalOutput,
    setTerminalOutput,
    proposals,
    commandProposals,
    submitProposalDecisions,
    submitCommandDecisions,
  } = useVocoSocket();
  const { isCapturing, startCapture, stopCapture } =
    useAudioCapture(isConnected ? sendAudioChunk : null);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  const handleCloseTerminal = () => {
    setTerminalOutput(null);
  };

  // Priority: CommandApproval > ReviewDeck > GhostTerminal
  const renderOverlay = () => {
    if (commandProposals.length > 0) {
      return (
        <CommandApproval
          commands={commandProposals}
          onSubmitDecisions={submitCommandDecisions}
        />
      );
    }
    if (proposals.length > 0) {
      return (
        <ReviewDeck
          proposals={proposals}
          onSubmitDecisions={submitProposalDecisions}
        />
      );
    }
    return <GhostTerminal output={terminalOutput} onClose={handleCloseTerminal} />;
  };

  return (
    <div className="noise-overlay min-h-screen bg-background text-foreground">
      <Header />
      <main className="flex items-center justify-center min-h-screen">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Voco Audio Bridge Test</CardTitle>
          </CardHeader>

          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">WebSocket</span>
              <Badge variant={isConnected ? "default" : "destructive"}>
                {isConnected ? "Connected" : "Disconnected"}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Microphone</span>
              <Badge variant={isCapturing ? "default" : "secondary"}>
                {isCapturing ? "Capturing" : "Inactive"}
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Barge-in</span>
              <span
                className={`inline-block h-3 w-3 rounded-full ${
                  bargeInActive
                    ? "bg-red-500 animate-pulse"
                    : "bg-muted-foreground/30"
                }`}
              />
            </div>
          </CardContent>

          <CardFooter className="gap-3">
            <Button
              onClick={startCapture}
              disabled={!isConnected || isCapturing}
            >
              Start Mic
            </Button>
            <Button
              variant="secondary"
              onClick={stopCapture}
              disabled={!isCapturing}
            >
              Stop Mic
            </Button>
          </CardFooter>
        </Card>
      </main>

      {renderOverlay()}
    </div>
  );
};

export default AppPage;
