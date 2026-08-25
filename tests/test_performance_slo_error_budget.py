from __future__ import annotations
import unittest
from datetime import UTC, datetime, timedelta
from scripts.performance_slo_error_budget import build_report, build_slos, detect_sustained_degradation
NOW=datetime(2026,8,25,17,0,tzinfo=UTC)
def _iso(v): return v.isoformat().replace('+00:00','Z')
def _snapshot(offset,*,p95=100.0,p99=120.0,throughput=20.0,error_rate=0.0,lcp=2000.0):
    return {'observed_at':_iso(NOW-timedelta(hours=offset)),'run_id':f'run-{offset}','head_branch':'main','mode':'scheduled-baseline','api':{'/health':{'p95_ms':p95,'p99_ms':p99,'throughput_rps':throughput,'error_rate_percent':error_rate}},'browser':{'event_loop_lag_p95_ms':1.0,'event_loop_lag_max_ms':2.0,'max_long_task_ms':40.0,'lcp_ms':lcp,'heap_after_gc_mb':9.0,'gc_roundtrip_ms':20.0}}
def _policy(minimum_samples=5):
    return {'policy_version':'test','browser':{'max_event_loop_lag_p95_ms':100,'max_event_loop_lag_max_ms':250,'max_long_task_ms':250,'max_lcp_ms':4000,'max_heap_after_gc_mb':128,'max_gc_roundtrip_ms':750},'history':{'regression':{'max_latency_increase_percent':30,'max_throughput_drop_percent':30,'max_error_rate_increase_pp':1,'max_browser_metric_increase_percent':30}},'performance_slo':{'window_days':7,'minimum_samples':minimum_samples,'error_budget_warning_remaining_percent':25,'targets':{'api_latency_good_percent':95,'api_reliability_good_percent':99,'api_capacity_good_percent':95,'browser_runtime_good_percent':95},'sustained_degradation':{'required_consecutive':3,'reference_window_days':7,'minimum_reference_samples':5}},'endpoints':[{'path':'/health','budget':{'max_p95_ms':1500,'max_p99_ms':2500,'max_error_rate_percent':0,'min_throughput_rps':2}}]}
def _history(snapshots,regressions=None):
    ordered=sorted(snapshots,key=lambda i:i['observed_at']); return {'current':ordered[-1],'snapshots':ordered,'regressions':regressions or []}
class Tests(unittest.TestCase):
    def test_insufficient(self):
        self.assertTrue(all(i['status']=='no_data' for i in build_slos(_history([_snapshot(1),_snapshot(0)]),_policy(),environment='prod')))
    def test_error_budget_boundary_warns(self):
        snaps=[_snapshot(i) for i in range(20)]; snaps[19]=_snapshot(19,p95=2000,p99=2600); latency=next(i for i in build_slos(_history(snaps),_policy(),environment='prod') if i['slo_id']=='performance_api_latency'); self.assertEqual(latency['actual_percent'],95.0); self.assertEqual(latency['error_budget_remaining_percent'],0.0); self.assertFalse(latency['breach']); self.assertTrue(latency['warning'])
    def test_breach_blocks(self):
        snaps=[_snapshot(i) for i in range(10)]; snaps[9]=_snapshot(9,error_rate=5); r=build_report(history_report=_history(snaps),policy=_policy()); self.assertEqual(r['status'],'blocked')
    def test_three_consecutive(self):
        ref=[_snapshot(i+3,p95=100) for i in range(5)]; tail=[_snapshot(2,p95=150),_snapshot(1,p95=150),_snapshot(0,p95=150)]; r=detect_sustained_degradation(_history(ref+tail),_policy()); self.assertTrue(any(i['metric']=='p95_ms' for i in r['findings']))
        tail=[_snapshot(2,p95=150),_snapshot(1,p95=100),_snapshot(0,p95=150)]; self.assertEqual(detect_sustained_degradation(_history(ref+tail),_policy())['findings'],[])
    def test_single_regression_watch(self):
        snaps=[_snapshot(i) for i in range(8)]; r=build_report(history_report=_history(snaps,[{'metric':'p95_ms'}]),policy=_policy()); self.assertEqual(r['status'],'watch')
    def test_sustained_blocks(self):
        ref=[_snapshot(i+3,p95=100) for i in range(5)]; tail=[_snapshot(2,p95=150),_snapshot(1,p95=150),_snapshot(0,p95=150)]; r=build_report(history_report=_history(ref+tail),policy=_policy()); self.assertEqual(r['status'],'blocked'); self.assertGreater(r['summary']['sustained_degradations_total'],0)
if __name__=='__main__': unittest.main()
