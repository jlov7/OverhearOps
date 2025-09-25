"""
Teams Graph adapter (stub)

This adapter outlines how we'd fetch Teams messages via Microsoft Graph once tenant
access is granted. It intentionally avoids real auth calls; instead it validates config and
raises informative errors.

Reference:
- chatMessage resource & Teams messaging overview (schemas and APIs)
- Scopes: Chat.Read.All, ChannelMessage.Read.All (admin consent likely)

In demo mode, DO NOT CALL these functions; use the NDJSON demo adapter instead.
"""
import os
from collections.abc import Generator, Iterable
from typing import Any


class TeamsGraphAdapter:
    def __init__(self):
        self.tenant_id = os.getenv("MS_TENANT_ID")
        self.client_id = os.getenv("MS_CLIENT_ID")
        self.client_secret = os.getenv("MS_CLIENT_SECRET")  # or use certificate auth with MSAL
        self._validate()

    def _validate(self):
        # Fail fast with a clear message if creds are not provided
        if not (self.tenant_id and self.client_id and self.client_secret):
            raise RuntimeError(
                "TeamsGraphAdapter not configured. Set MS_TENANT_ID, MS_CLIENT_ID, "
                "MS_CLIENT_SECRET and ensure admin consent for Chat.Read.All / "
                "ChannelMessage.Read.All."
            )

    def list_messages(self, team_id: str, channel_id: str) -> Iterable[dict[str, Any]]:
        """
        Placeholder: return an empty iterable for now.
        In a real implementation, use MSAL to obtain a token and call:
          GET /teams/{team-id}/channels/{channel-id}/messages
        or GET /chats/{chat-id}/messages
        Include fields: id, from.user.displayName, body.content, createdDateTime, replyToId
        """
        return []

    def stream_thread(self, conversation_id: str) -> Generator[dict[str, Any], None, None]:
        """
        Placeholder generator. In production, poll the Graph delta endpoints or subscribe 
        to change notifications (webhooks) for chat messages, yielding chatMessage-shaped dicts.
        """
        if False:
            # Example structure:
            # {'id': ..., 'from': {'user': {'displayName': ...}}, 'body': {'content': ...}, ...}
            yield {}
        return
