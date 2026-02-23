# Core Features & Capabilities

## Voice Interface

### 🎙️ Voice-to-Context Engine
- **Sub-300ms Voice Pipeline**
  - Deepgram STT for real-time transcription
  - Silero VAD for voice activity detection
  - Cartesia TTS for instant voice feedback

### 🔄 Barge-In Support
- Interrupt AI mid-sentence
- Audio buffer management
- Instant context switching
- Continuous conversation flow

### 🧠 LangGraph State Machine
- Multi-model routing (Sonnet/Haiku)
- Speculative pre-fetching
- Background job queue
- Stateful conversation context

## Desktop Integration

### 🔒 Zero-Trust Security
- Tauri v2 secure sandbox
- Filesystem scope validation
- Human-in-the-loop approval
- JWT-based authentication
- Row-level security (RLS)

### 💻 Terminal Integration
- Command execution via Tauri
- Real-time output streaming
- Background job tracking
- Error handling & recovery

### 📊 Logic Ledger
- Visual decision DAG
- Supabase sync & persistence
- Team workspace support
- Audit logging

## Enterprise Features

### 💳 "Seat + Meter" Billing
- $19/month per seat
- $0.02 per voice turn
- Stripe integration
- Usage analytics

### 🔐 Security & Compliance
- SOC 2 compliance ready
- JWT authentication
- Row-level security
- Audit logging

### 🌐 Team Features
- Shared workspaces
- Project context sync
- Usage monitoring
- Role-based access

## Development Tools

### 🔍 Local Search
- Ripgrep integration
- Project-wide indexing
- Instant results
- Code-aware context

### 🛠️ IDE Integration
- WebSocket bridge
- State persistence
- Settings sync
- API key management

### 📦 Project Management
- Package.json scanning
- Directory tree analysis
- Dependency tracking
- Version management