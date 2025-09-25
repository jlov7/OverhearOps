# Teams Adapter & Agents Playground

## Why an adapter?
Our demo runs without tenant access by mirroring the **Microsoft Graph `chatMessage`** schema in NDJSON and rendering a Teams-style UI. When org access is granted, we can switch to the real APIs behind an adapter seam. This keeps the demo trustworthy and future-proof. (Graph `chatMessage` & Teams messaging overview). 

## Modes
- **demo (default)**: Local NDJSON stream shaped like `chatMessage`.  
- **graph**: Live Microsoft Graph once admin consent and scopes are in place.  
- **playground**: Export **Adaptive Card v1.5** snippets for paste-testing in **Microsoft 365 Agents Playground** (no tenant needed).

## Graph message shape
We mirror key fields: `id`, `from.user.displayName`, `body.content`, `createdDateTime`, `replyToId`. (See `chatMessage` resource.) 

## Required Graph scopes (later)
To read channel or chat messages: `ChannelMessage.Read.All` and/or `Chat.Read.All` (app-only or delegated; admin consent required). (See Teams messaging overview pages.) 

## Agents Playground workflow (no tenant)
Use **Microsoft 365 Agents Playground** to preview your bot/agent messages & Adaptive Cards without a Microsoft 365 developer account, tunnelling, or app registration. Paste the sample Plan Card we expose at `/playground/card/plan` into the Playground. (Agents Playground docs). 

> ⚠️ **Adaptive Cards v1.5**: Setting `version: "1.5"` enables Universal Actions but can be **incompatible with older clients** (Outlook/Teams). We constrain components to ≤ v1.5 and note client caveats. (Adaptive Cards 1.5 note). 

## Config
```

ADAPTER=demo|graph|playground
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OVERHEAROPS_DB=overhearops.db

```

## Risks & mitigations
- **Permission lockdown**: Use demo & playground; keep Graph adapter behind env switch.  
- **Rendering drift**: Stick to ≤ v1.5 patterns; test in Playground.  
- **PII**: Never ingest real tenant data in demo; if switched to Graph, enable redaction and minimise storage.

## References
- Microsoft Graph `chatMessage` resource (schema).  
- Teams messaging overview (which API to use, threading).  
- Agents Playground: test bots/agents and Adaptive Cards without tenant.  
- Adaptive Cards v1.5 compatibility note.
