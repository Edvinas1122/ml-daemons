# LLM + Function Calling

Pure text gen daemon. Tool orchestration lives in an external agent layer.

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│  User /  │     │   Agent      │     │   LLM    │
│  Client  │     │  Software    │     │  Daemon  │
└────┬─────┘     └──────┬───────┘     └────┬─────┘
     │                  │                  │
     │  1. request      │                  │
     │─────────────────►│                  │
     │                  │  2. forward      │
     │                  │─────────────────►│
     │                  │                  │
     │                  │  3. tool call    │
     │                  │◄─────────────────│
     │  4. report       │                  │
     │◄─────────────────│                  │
     │                  │                  │
     │  5. fetch result │                  │
     │─────────────────►│                  │
     │                  │  6. re-feed      │
     │                  │─────────────────►│
     │                  │                  │
     │                  │  7. response     │
     │                  │◄─────────────────│
     │  8. final reply  │                  │
     │◄─────────────────│                  │
     │                  │                  │
```

## What the daemon does

Single request → response. It has no concept of tools.

```json
// in:  {"messages": [{"role": "user", "content": "..."}]}
// out: {"content": "..."}
```

## What the agent does

- Holds the tool definitions in its system prompt
- Sends user message to LLM daemon
- Checks if response is a tool call or final answer
- Executes tools, re-feeds results to LLM daemon
- Returns final answer to user
