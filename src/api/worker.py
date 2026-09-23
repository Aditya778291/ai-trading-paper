from __future__ import annotations
import json, logging, os, time
from .jobs import queue
from .notifications import notifier
log=logging.getLogger(__name__)

def run_worker(poll_seconds: float=1.0):
    log.info('worker_started backend=%s', queue.backend)
    while True:
        raw=queue.pop(timeout=max(1, int(poll_seconds)))
        if raw is None: continue
        try:
            job=json.loads(raw)
            if job.get('name')=='notification':
                p=job.get('payload',{}); notifier.notify(p.get('event','notification'),p)
            else: log.warning('unknown_job name=%s',job.get('name'))
        except Exception:
            log.exception('job_failed')

if __name__=='__main__': run_worker(float(os.getenv('WORKER_POLL_SECONDS','1')))
