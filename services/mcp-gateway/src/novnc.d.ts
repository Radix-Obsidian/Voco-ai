declare module "@novnc/novnc/core/rfb.js" {
  interface RFBOptions {
    credentials?: { password?: string };
    shared?: boolean;
    wsProtocols?: string[];
  }

  export default class RFB {
    constructor(target: HTMLElement, urlOrChannel: string, options?: RFBOptions);

    scaleViewport: boolean;
    resizeSession: boolean;
    background: string;
    viewOnly: boolean;

    disconnect(): void;
    sendCredentials(credentials: { password: string }): void;
    sendKey(keysym: number, code: string | null, down?: boolean): void;
    focus(): void;
    blur(): void;

    addEventListener(event: "connect", listener: () => void): void;
    addEventListener(event: "disconnect", listener: (e: { detail: { clean: boolean } }) => void): void;
    addEventListener(event: "credentialsrequired", listener: () => void): void;
    addEventListener(event: "clipboard", listener: (e: { detail: { text: string } }) => void): void;
    addEventListener(event: "bell", listener: () => void): void;
    addEventListener(event: "desktopname", listener: (e: { detail: { name: string } }) => void): void;
    addEventListener(event: string, listener: (e: unknown) => void): void;

    removeEventListener(event: string, listener: (e: unknown) => void): void;
  }
}
