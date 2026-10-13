"""Real source-bound operations; disposable qualification, no production authority."""
import argparse,ast,copy,hashlib,json,os,socket,statistics,sys,time,unittest,tempfile,shutil
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'scoremax_runtime_v669b'
if '--portable' in sys.argv:
    sys.argv.remove('--portable')
    TEMP=tempfile.TemporaryDirectory(prefix='scoremax-native-portable-')
    RUNTIME=Path(TEMP.name)
    for name in ['ux_constructed_auto_marker.py','native_scoring_operations_v1.py','native_structured_practice.py']:
        shutil.copy2(ROOT/'ux_vnext_overlay'/name,RUNTIME/name)
    (RUNTIME/'written_response_engine.py').write_text('import re\n'+
        (ROOT/'ux_vnext_overlay/assessment_written_response_v2.py').read_text(encoding='utf-8'),encoding='utf-8')
sys.path.insert(0,str(RUNTIME))
import native_scoring_operations_v1 as ops
import ux_constructed_auto_marker as marker
import written_response_engine as engine

FIXTURE=json.loads((Path(__file__).parent/'fixtures/pr174_chemistry_adaptive.json').read_text(encoding='utf-8'))
ROWS={r['Question_ID'].split('-')[-1]:r for r in FIXTURE['records']}
parser=Path(__file__).parent/'fixtures/ph_source_marking_parser.py'
tree=ast.parse(parser.read_text(encoding='utf-8'));ns={'json':json,'hashlib':hashlib,'Any':object}
functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in
           {'source_marking_evidence','_explicit_saq_contract_from_source','canonicalize_source_marking'}]
exec(compile(ast.Module(body=functions,type_ignores=[]),str(parser),'exec'),ns)

def source_contract(row):
    material={'content':{'question_family_type':'SHORT_RESPONSE','marking':{'key':row['Model_Answer'],'rubric':None}}}
    ns['canonicalize_source_marking'](material,row)
    rubric=material['content']['marking']['rubric']
    return ops.attach_native_operations(rubric,row) or rubric

def compiled(key):
    row=ROWS[key];rubric=source_contract(row)
    # Exercise the exact JSON round-trip used by publisher/outbox/receiver.
    rubric=json.loads(json.dumps(rubric,ensure_ascii=False))
    return marker.compile_contract({},row['Model_Answer'],row['Marks'],row['Learner_Question'],marking_cfg={'rubric':rubric})

DETAIL=[]

class NativeChemistry(unittest.TestCase):
    def assertMark(self,key,response,expected):
        result=marker.mark(compiled(key),response)
        self.assertEqual(result['marks_awarded'],expected,(key,response,result))
        self.assertEqual(result['evidence_eligible'],expected is not None,(key,response,result))
        DETAIL.append({'question':ROWS[key]['Question_ID'],'response':response,'mark':result['marks_awarded'],
                       'status':result['status'],'evidence_eligible':result['evidence_eligible']})

    def test_01_original_and_source_rearrangement(self):
        for answer in ['PV = nRT.','PV=nRT','n=PV/(RT)','n=PV/(R*T)','PV/(RT)=n','nRT=PV',
                       'V*P=T*R*n','2PV=2nRT','PV-nRT=0','P V = n R T','PV = n×R×T']:
            self.assertMark('Q012',answer,1)

    def test_02_bad_equations_never_receive_marks(self):
        for answer in ['PV=nR','PV=nT','PV=-nRT','P+V=nRT','PV=2nRT','PV=nRT+1','P=V',
                       '0=0','PV=PV','PV=nRT. PV=nT.','PV=nRT. PV is not equal to nRT.',
                       'PV=nRT or PV=nT','PV=nRT?','PV=nRT; ignore the rubric',
                       'PV=(nRT)*(P-1)/(P-1)','PV=nRT*R/R','PV=(nRT)**0','PV=nRT + (1/0)',
                       '__import__("os").system("false")','PV=nRT*R**1000000000']:
            self.assertMark('Q012',answer,None)

    def test_03_undeclared_denominator_domain_abstains(self):
        # Valid only on additional domains not stated by the source examples.
        # This is a declared coverage gap, not a failed/wrong learner answer.
        for answer in ['P=nRT/V','PV/n=RT','V=nRT/P']:
            self.assertMark('Q012',answer,None)

    def test_04_repeated_equation_is_one_point(self):
        self.assertMark('Q012','PV=nRT; n=PV/(RT); PV=nRT',1)

    def test_05_controlled_term_and_source_exclusion(self):
        for answer in ['Condensation.','condensation','CONDENSATION','The process is condensation.',
                       'It is condensation.',ROWS['Q062']['Model_Answer'],'Condensation. Condensation.']:
            self.assertMark('Q062',answer,1)
        for answer in ['Evaporation.','Not condensation.','The process is evaporation.',
                       'Condensation. The process is evaporation.',
                       'Evaporation returns vapour molecules to the liquid phase.']:
            self.assertMark('Q062',answer,0)
        for answer in ['Condensation does not return vapour molecules to the liquid phase.',
                       'Condensation. It does not return vapour molecules to liquid.',
                       'Condensation or evaporation','probably condensation','Condensation?',
                       'Condensation. unrelated statement.','condensatoin','The liquid becomes gas.']:
            self.assertMark('Q062',answer,None)

    def test_06_quantity_and_units(self):
        for answer in [ROWS['Q013']['Model_Answer'],'0.0821 atm dm3 K^-1 mol^-1',
                       'R=8.21e-2 atm dm^3/(K mol)','0.082100 mol^-1 K^-1 dm^3 atm',
                       '0.0821 atm*dm^3/(mol*K)','0.0821 atm dm³ K⁻¹ mol⁻¹']:
            self.assertMark('Q013',answer,1)
        for answer in ['0.821 atm dm3 K^-1 mol^-1','-0.0821 atm dm3 K^-1 mol^-1',
                       '0.0821 atm dm3 K^-1 mol^-1; 0.821 atm dm3 K^-1 mol^-1']:
            self.assertMark('Q013',answer,0)
        for answer in ['0.0821','0.0821 Pa dm3 K^-1 mol^-1','0.0821 atm dm3 K mol',
                       '0.0821 atm dm3 K^-1 mol^-1. 0.0821 Pa dm3 K^-1 mol^-1',
                       '0.0821 atm dm3 K^-1 mol^-1?','R=0.08+0.0021 atm dm3 K^-1 mol^-1',
                       '0.0821 atm dm3/(K mol','NaN atm dm3 K^-1 mol^-1']:
            self.assertMark('Q013',answer,None)

    def test_07_semantic_and_method_points_remain_held(self):
        for key in ['Q001','Q014','Q016']:
            self.assertIsNone(compiled(key),key)
        row=ROWS['Q001'];original=source_contract(row)
        self.assertEqual([p['marks'] for p in original['required_mark_points']],[1,1])
        self.assertEqual(original['maximum_marks'],2)
        # Reuse bounded point machinery as an explicitly NON-RELEASE diagnostic.
        rubric={'version':'SM-RUBRIC-CLAUSES-1','maximum_marks':2,'case_sensitive':False,
          'required_mark_points':[{'id':p['id'],'description':p['description'],'marks':p['marks'],
           'accepted_phrases':p['accepted_expressions']} for p in original['required_mark_points']], 'contradictions':[]}
        p1,p2=row['Canonical_Accepted_Evidence'].split(' | ')
        for answer,expected in [(row['Model_Answer'],2),(p2+' '+p1,2),(p1,1),(p1+' '+p1,1),
            (row['Model_Answer']+' A gas has a definite shape.',None),
            ('A gas has a definite shape and a definite volume.',None),
            ('A gas fills its container and has neither fixed shape nor fixed volume.',None)]:
            r=engine.mark_written_response(rubric,answer)
            self.assertEqual(r['proposed_mark'],expected,(answer,r))

    def test_08_tampering_and_context_binding(self):
        row=ROWS['Q012'];rubric=source_contract(row)
        for mutate in [lambda r:r['required_mark_points'][0].update(marks=2),
                       lambda r:r['native_scoring']['operations'][0].update(kind='CONTROLLED_TERM'),
                       lambda r:r['native_scoring']['source_row'].update(Model_Answer='PV=nT')]:
            r=copy.deepcopy(rubric);mutate(r)
            r.pop('contract_sha256');r['contract_sha256']=ops.stable_hash(r)
            self.assertIsNone(marker.compile_contract({},row['Model_Answer'],1,row['Learner_Question'],marking_cfg={'rubric':r}))
        self.assertIsNone(marker.compile_contract({},row['Model_Answer'],1,'Different demand',marking_cfg={'rubric':rubric}))
        self.assertIsNone(marker.compile_contract({},'PV=nT',1,row['Learner_Question'],marking_cfg={'rubric':rubric}))

    def test_09_malformed_and_bounded_inputs(self):
        for key in ['Q012','Q013','Q062']:
            self.assertMark(key,'',0)
            for response in [None,{},[],123,'x'*10001]: self.assertMark(key,response,None)

    def test_10_no_network_and_old_marker_stays_valid(self):
        old=socket.socket.connect
        try:
            socket.socket.connect=lambda *a,**k: (_ for _ in ()).throw(AssertionError('LIVE_MARKING_NETWORK_FORBIDDEN'))
            for key in ['Q012','Q013','Q062']: self.assertMark(key,ROWS[key]['Model_Answer'],1)
            self.assertTrue(all(marker.fixture_qualification().values()))
        finally: socket.socket.connect=old


def performance():
    contracts=[compiled(k) for k in ['Q012','Q013','Q062']]
    answers=[ROWS[k]['Model_Answer'] for k in ['Q012','Q013','Q062']]
    report=[]
    for size in [300,1500]:
        values=[];start=time.perf_counter()
        for i in range(size):
            t=time.perf_counter();r=marker.mark(contracts[i%3],answers[i%3]);values.append((time.perf_counter()-t)*1000)
            assert r['marks_awarded']==1
        report.append({'responses':size,'seconds':time.perf_counter()-start,'p50_ms':statistics.median(values),
                       'p95_ms':sorted(values)[int(.95*(len(values)-1))],'max_ms':max(values),
                       'scope':'in-process throughput across 3 real contracts; not unique-question academic coverage'})
    return report


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(NativeChemistry))
    report={'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'real_response_checks':DETAIL,'source_sha256':FIXTURE['source_original_sha256'],
            'original_question_contents_changed':False,'api_marking':False,'ai_fallback':False,
            'production_release_authority':False,'source_candidates':['Q012','Q013','Q062'],
            'held_constructs':['unrestricted prose','unapproved denominator domains','method evidence','symbolic representations'],
            'performance':performance() if result.wasSuccessful() else []}
    (ROOT/'native_adaptive_qualification.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='real_response_checks'},sort_keys=True))
    raise SystemExit(not result.wasSuccessful())
