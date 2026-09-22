from datetime import UTC, datetime
import pytest
from scripts.analyze_workflow_flakiness import analyze_flakiness
NOW=datetime(2026,7,31,20,0,tzinfo=UTC)
def run(name,conclusion='success',status='completed',attempt=1): return {'name':name,'status':status,'conclusion':conclusion,'run_attempt':attempt}
def evaluate(runs): return analyze_flakiness(runs_payload={'workflow_runs':runs},observed_at=NOW)
def test_low():
    i=evaluate([run('CI') for _ in range(10)])['workflows'][0]; assert i['risk']=='low' and i['first_cycle_success_rate']==1.0
def test_high():
    runs=[run('Evidence') for _ in range(5)]+[run('Evidence','failure') for _ in range(2)]+[run('Evidence',attempt=2) for _ in range(3)]; i=evaluate(runs)['workflows'][0]; assert i['risk']=='high' and i['terminal_failure_rate']==0.2 and i['rerun_rate']==0.3
def test_medium_cancel():
    i=evaluate([run('Scanner') for _ in range(8)]+[run('Scanner','cancelled') for _ in range(2)])['workflows'][0]; assert i['risk']=='medium'
def test_insufficient(): assert evaluate([run('Rare'),run('Rare','failure')])['workflows'][0]['risk']=='insufficient_sample'
def test_incomplete():
    i=evaluate([run('CI',None,'in_progress') for _ in range(5)])['workflows'][0]; assert i['incomplete']==5 and i['failures']==0
def test_invalid():
    with pytest.raises(ValueError): analyze_flakiness(runs_payload={'workflow_runs':'x'})
