"""Offline CLI: exercise approvals, rejection, expiry, binding and replay."""
import json
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from hitl.hitl import ConfidenceRouter
from hitl.approval import ActionGateway, ApprovalStore


def run_demo(output_dir=ROOT/'outputs'):
    output_dir = Path(output_dir)
    clock = [time.time()]
    store = ApprovalStore(output_dir/'hitl_approvals.json', clock=lambda: clock[0])
    gateway = ActionGateway(store, ConfidenceRouter())
    args = dict(requester_id='student', action_type='transfer_money', destination='https://api.vinbank.example/transfers',
                payload='approved transfer amount 500000', confidence=.99)
    cases = []
    def record(name, result, expected):
        if result['status'] != expected:
            raise AssertionError(name)
        cases.append({'scenario': name, 'result': result, 'passed': True})
    pending = gateway.execute(**args)
    record('high_risk_needs_human', pending, 'pending')
    aid = pending['approval_id']
    store.decide(aid, 'reviewer-1', True)
    record('approve', gateway.execute(**args, approval_id=aid), 'executed')
    record('reuse_denied', gateway.execute(**args, approval_id=aid), 'denied')
    aid = gateway.execute(**args)['approval_id']
    store.decide(aid, 'reviewer-1', False)
    record('reject', gateway.execute(**args, approval_id=aid), 'denied')
    aid = gateway.execute(**args)['approval_id']
    clock[0] += 901
    record('timeout', gateway.execute(**args, approval_id=aid), 'denied')
    aid = gateway.execute(**args)['approval_id']
    store.decide(aid, 'reviewer-1', True)
    record('changed_payload', gateway.execute(**{**args, 'payload': 'approved transfer amount 600000'}, approval_id=aid), 'denied')
    record('egress_cannot_be_overridden', gateway.execute(**{**args, 'destination': 'https://evil.example/send'}, approval_id=aid), 'blocked')
    record('medium_confidence', gateway.execute(**{**args, 'action_type': 'loan_advice', 'confidence': .8}), 'pending')
    record('low_confidence', gateway.execute(**{**args, 'action_type': 'loan_advice', 'confidence': .5}), 'pending')
    result = {'mode': 'simulation_only', 'model_calls': 0, 'confidence_source': 'explicit_scenarios',
              'passed': True, 'cases': cases, 'store': store.snapshot()}
    (output_dir/'hitl_demo.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    return result

if __name__ == '__main__':
    result = run_demo()
    print(f"HITL: {len(result['cases'])} scenarios passed, 0 API calls")
