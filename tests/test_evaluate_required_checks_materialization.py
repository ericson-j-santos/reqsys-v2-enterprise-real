from datetime import UTC, datetime
import pytest
from scripts.evaluate_required_checks_materialization import evaluate_materialization
NOW=datetime(2026,7,31,20,0,tzinfo=UTC); PROTECTION={'contexts':['CI','Evidence'],'checks':[{'context':'Security','app_id':1}]}
def evaluate(samples,protection=None): return evaluate_materialization(protection_payload=protection or PROTECTION,samples_payload={'samples':samples},observed_at=NOW)
def sample(sha,contexts,pr_number=1): return {'sha':sha,'contexts':contexts,'pr_number':pr_number}
def test_all():
    r=evaluate([sample('a',['CI','Evidence','Security']),sample('b',['CI','Evidence','Security'],2)]); assert r['decision']=='required_checks_materialized' and all(i['materialization_rate']==1.0 for i in r['materialization'])
def test_missing():
    r=evaluate([sample('a',['CI','Security']),sample('b',['CI','Evidence','Security'],2)]); assert r['decision']=='required_checks_missing_on_samples' and r['automatic_context_removal_allowed'] is False
def test_permission():
    r=evaluate([],{'unavailable':True,'reason':'403'}); assert r['decision']=='branch_protection_unavailable' and r['inconclusive'] is True
def test_no_config_or_samples():
    assert evaluate([sample('a',['CI'])],{'contexts':[],'checks':[]})['inconclusive'] is True
    assert evaluate([])['decision']=='no_pr_samples_available'
def test_dedup(): assert evaluate([sample('a',['CI','Evidence','Security'])],{'contexts':['CI','CI'],'checks':[{'context':'Security'},{'context':'Evidence'}]})['required_contexts']==['CI','Evidence','Security']
def test_invalid():
    with pytest.raises(ValueError): evaluate_materialization(protection_payload=PROTECTION,samples_payload={'samples':'x'})
