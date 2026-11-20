"""Local approval workflow for simulated actions; no banking/network side effects."""
import copy
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from core.file_lock import exclusive_lock


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def redact(value):
    from guardrails.output_guardrails import content_filter
    return content_filter(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False))['redacted']


class ApprovalError(ValueError):
    pass


class ApprovalStore:
    def __init__(self, path, *, ttl_seconds=900, clock=time.time):
        if ttl_seconds <= 0:
            raise ValueError('TTL must be positive')
        self.path, self.ttl, self.clock = Path(path), ttl_seconds, clock
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def transaction(self):
        with exclusive_lock(self.path.with_suffix('.lock')):
            data = json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else {'approvals': {}, 'audit': []}
            now = self.clock()
            for row in data['approvals'].values():
                if row['status'] in {'pending', 'approved'} and now >= row['expires_at']:
                    row['status'] = 'expired'
                    data['audit'].append({'event': 'expired', 'approval_id': row['id'], 'timestamp': now})
            try:
                yield data, now
            finally:
                temp = self.path.with_suffix('.tmp')
                temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
                os.chmod(temp, 0o600)
                os.replace(temp, self.path)

    def submit(self, requester_id, action_type, destination, payload, *, context=None):
        if not all(isinstance(v, str) and v.strip() for v in [requester_id, action_type, destination]):
            raise ValueError('Requester, action and destination required')
        with self.transaction() as (data, now):
            aid = 'HITL-' + uuid.uuid4().hex.upper()
            row = {'id': aid, 'status': 'pending', 'created_at': now, 'expires_at': now+self.ttl,
                   'requester_hash': digest(requester_id), 'binding': digest([requester_id, action_type, destination, payload]),
                   'action_type': redact(action_type), 'destination': redact(destination),
                   'payload_preview': redact(payload), 'context': redact(context or {})}
            data['approvals'][aid] = row
            data['audit'].append({'event': 'submitted', 'approval_id': aid, 'timestamp': now})
            return copy.deepcopy(row)

    def get(self, aid):
        with self.transaction() as (data, now):
            if aid not in data['approvals']:
                raise ApprovalError('Unknown approval')
            return copy.deepcopy(data['approvals'][aid])

    def decide(self, aid, reviewer_id, approve, *, note=''):
        if not isinstance(approve, bool) or not isinstance(reviewer_id, str) or not reviewer_id.strip():
            raise ValueError('Valid reviewer and boolean decision required')
        with self.transaction() as (data, now):
            row = data['approvals'].get(aid)
            if not row or row['status'] != 'pending':
                raise ApprovalError('Approval is not pending')
            if digest(reviewer_id) == row['requester_hash']:
                raise ApprovalError('Requester cannot self-approve')
            row.update(status='approved' if approve else 'rejected', reviewer=redact(reviewer_id),
                       reviewed_at=now, note=redact(note))
            data['audit'].append({'event': row['status'], 'approval_id': aid, 'timestamp': now})
            return copy.deepcopy(row)

    def consume(self, aid, requester_id, action_type, destination, payload):
        with self.transaction() as (data, now):
            row = data['approvals'].get(aid)
            if not row or row['status'] != 'approved':
                raise ApprovalError('Approval is not approved or has expired/been consumed')
            if row['binding'] != digest([requester_id, action_type, destination, payload]):
                raise ApprovalError('Approval does not match proposed action')
            row.update(status='consumed', consumed_at=now)
            data['audit'].append({'event': 'consumed', 'approval_id': aid, 'timestamp': now})
            return copy.deepcopy(row)

    def snapshot(self):
        with self.transaction() as (data, now):
            return copy.deepcopy(data)

    def event(self, event, details):
        with self.transaction() as (data, now):
            data['audit'].append({'event': event, 'timestamp': now, 'details': redact(details)})


class ActionGateway:
    def __init__(self, store, router):
        self.store, self.router = store, router

    def execute(self, *, requester_id, action_type, destination, payload, response='', confidence=1., approval_id=None):
        from assignment.pipeline import is_egress_allowed
        if not is_egress_allowed(destination, payload):
            self.store.event('egress_blocked', {'destination': destination})
            return {'status': 'blocked', 'reason': 'egress_denied'}
        decision = self.router.route(response, confidence, action_type)
        if decision.requires_human and not approval_id:
            row = self.store.submit(requester_id, action_type, destination, payload,
                                     context={'response': response, 'confidence': confidence, 'confidence_source': 'caller_supplied'})
            return {'status': 'pending', 'approval_id': row['id'], 'routing_action': decision.action}
        if approval_id:
            try:
                self.store.consume(approval_id, requester_id, action_type, destination, payload)
            except ApprovalError:
                self.store.event('execution_denied', {'approval_id': approval_id})
                return {'status': 'denied', 'approval_id': approval_id}
        receipt = {'status': 'executed', 'simulated': True, 'receipt_id': 'sim-'+uuid.uuid4().hex}
        self.store.event('simulated_execution', receipt)
        return receipt
