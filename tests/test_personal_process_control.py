import importlib.util, json, tempfile, unittest, zipfile
from datetime import date
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('ppc',ROOT/'scripts/personal_process_control.py'); ppc=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(ppc)
class Tests(unittest.TestCase):
 def setUp(self):
  b=ROOT/'governance/personal-process'; self.d=json.loads((b/'demandas.json').read_text()); self.l=json.loads((b/'biblioteca.json').read_text()); self.a=json.loads((b/'automacoes.json').read_text())
 def test_seed(self): self.assertEqual([],ppc.validate_demands(self.d)); self.assertEqual([],ppc.validate_library(self.l)); self.assertEqual([],ppc.validate_automations(self.a)); self.assertTrue(all(x['id'].startswith('EXT-') for x in self.d))
 def test_source_required(self):
  e=ppc.validate_demands([dict(self.d[0],origem='',estado_evidenciado_em='')]); self.assertTrue(any('origem' in x for x in e)); self.assertTrue(any('estado_evidenciado_em' in x for x in e))
 def test_open_next(self): self.assertTrue(any('sem proxima_acao' in x for x in ppc.validate_demands([dict(self.d[0],proxima_acao='')])))
 def test_concluded_evidence(self): self.assertTrue(any('concluido sem evidencia' in x for x in ppc.validate_demands([dict(self.d[0],status='Concluido',evidencia='')])))
 def test_blocker(self): self.assertTrue(any('bloqueado sem tipo_bloqueio' in x for x in ppc.validate_demands([dict(self.d[1],tipo_bloqueio='Nenhum')])))
 def test_pareto(self):
  f=ppc.pareto(self.d,ppc.demand_score); s=ppc.pareto(list(reversed(self.d)),ppc.demand_score); self.assertEqual([x['id'] for x in f],[x['id'] for x in s]); self.assertEqual('EXT-002',f[0]['id']); self.assertEqual('P1 - Alta',ppc.priority(f[0]['indice']))
 def test_modes(self): self.assertEqual('semanal_aprofundado',ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,7))[0]['mode']); self.assertEqual('diario',ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,4))[0]['mode'])
 def test_hash(self): self.assertEqual(ppc.canonical_sha256({'b':2,'a':1}),ppc.canonical_sha256({'a':1,'b':2}))
 def test_history_idempotent(self):
  s,p=ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,4)); r=ppc.history_record(s,p); h=ppc.merge_history([],r); self.assertEqual(h,ppc.merge_history(h,r)); self.assertEqual(1,len(h))
 def test_history_order(self):
  s1,p1=ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,4)); s2,p2=ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,5)); h=ppc.merge_history([],ppc.history_record(s2,p2)); h=ppc.merge_history(h,ppc.history_record(s1,p1)); self.assertEqual(['2026-09-04','2026-09-05'],[x['as_of'] for x in h])
 def test_xlsx(self):
  s,p=ppc.build_snapshot(self.d,self.l,self.a,date(2026,9,4)); h=ppc.merge_history([],ppc.history_record(s,p))
  with tempfile.TemporaryDirectory() as t:
   a=Path(t)/'a.xlsx'; b=Path(t)/'b.xlsx'; ppc.write_xlsx(a,s,self.d,self.l,self.a,h); ppc.write_xlsx(b,s,self.d,self.l,self.a,h); self.assertEqual(a.read_bytes(),b.read_bytes())
   with zipfile.ZipFile(a) as z: self.assertIsNone(z.testzip()); self.assertIn('xl/worksheets/sheet5.xml',z.namelist())
if __name__=='__main__': unittest.main()
