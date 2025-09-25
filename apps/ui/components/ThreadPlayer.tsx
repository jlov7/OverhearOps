"use client";

import { useEffect } from "react";
import { AdaptiveCard, Container, TextBlock, registerAdaptiveStyles } from "./AdaptiveKit";

export type ChatMessage = {
  id: string;
  body: { content: string };
  from: { user: { displayName: string } };
  createdDateTime: string;
  replyToId?: string | null;
};

type ThreadPlayerProps = {
  messages: ChatMessage[];
};

export function ThreadPlayer({ messages }: ThreadPlayerProps) {
  useEffect(() => {
    registerAdaptiveStyles();
  }, []);

  return (
    <div className="section-card" style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <h2 style={{ margin: 0 }}>CI Flake Thread</h2>
      <Container>
        {messages.map((message) => (
          <AdaptiveCard key={message.id}>
            <TextBlock size="small" weight="bolder" text={`${message.from.user.displayName}`} />
            <TextBlock size="small" text={new Date(message.createdDateTime).toLocaleTimeString()} />
            <TextBlock text={message.body.content} />
          </AdaptiveCard>
        ))}
      </Container>
    </div>
  );
}
