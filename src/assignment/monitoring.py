"""Aggregate request decisions and report threshold transitions."""
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


def default_metrics_path():
    return str(Path(__file__).resolve().parents[2] / 'outputs/metrics.json')


@dataclass
class Alert:
    metric: str
    value: float
    threshold: float
    message: str


@dataclass
class MonitoringAlert:
    block_rate_threshold: float = .5
    rate_limit_hit_threshold: int = 5
    judge_fail_rate_threshold: float = .3
    alerts: list = field(default_factory=list)
    total_requests: int = 0
    blocked_requests: int = 0
    rate_limit_hits: int = 0
    judge_checks: int = 0
    judge_fails: int = 0
    redacted_requests: int = 0
    error_requests: int = 0
    _active: set = field(default_factory=set, repr=False)

    def check_metrics(self):
        values = self.snapshot()
        new = []
        for metric, value, threshold in [('block_rate', values['block_rate'], self.block_rate_threshold),
             ('rate_limit_hits', self.rate_limit_hits, self.rate_limit_hit_threshold),
             ('judge_fail_rate', values['judge_fail_rate'], self.judge_fail_rate_threshold)]:
            if value > threshold and metric not in self._active:
                alert = Alert(metric, value, threshold, f'{metric} exceeded configured threshold')
                self.alerts.append(alert)
                new.append(alert)
                self._active.add(metric)
            elif value <= threshold:
                self._active.discard(metric)
        return new

    def snapshot(self):
        return {"total_requests": self.total_requests, "blocked_requests": self.blocked_requests,
                "block_rate": self.blocked_requests/self.total_requests if self.total_requests else 0,
                "rate_limit_hits": self.rate_limit_hits, "judge_checks": self.judge_checks, "judge_fails": self.judge_fails,
                "judge_fail_rate": self.judge_fails/self.judge_checks if self.judge_checks else 0,
                "redacted_requests": self.redacted_requests, "error_requests": self.error_requests,
                "alerts": [asdict(a) for a in self.alerts]}

    def export_json(self, filepath=None):
        self.check_metrics()
        path = Path(filepath or default_metrics_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.snapshot(), ensure_ascii=False, indent=2), encoding='utf-8')
        return path
