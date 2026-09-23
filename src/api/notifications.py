from __future__ import annotations
import json, os
from urllib.request import Request, urlopen
from .config import settings
from .jobs import queue
class Notifier:
    def notify(self,event,payload): raise NotImplementedError
class ConsoleNotifier(Notifier):
    def notify(self,event,payload): print(f'[notification] {event}: {json.dumps(payload,default=str)}')
class WebhookNotifier(Notifier):
    def __init__(self,url): self.url=url
    def notify(self,event,payload):
        req=Request(self.url,data=json.dumps({'event':event,'payload':payload}).encode(),headers={'Content-Type':'application/json'},method='POST')
        with urlopen(req,timeout=5): pass
class CompositeNotifier(Notifier):
    def __init__(self): self.items=[ConsoleNotifier()]
    def notify(self,event,payload):
        for n in self.items:
            try:n.notify(event,payload)
            except Exception:pass
notifier=CompositeNotifier()
if settings.webhook_url:notifier.items.append(WebhookNotifier(settings.webhook_url))

def enqueue_notification(event,payload): queue.enqueue('notification',{'event':event,'payload':payload})
