import json
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from execute_advanced import validate_plan, resolve_campaign, completed_summary, ROOT
from src.mapdl_session import session_options
from verify_evidence import verify, check_manifest
from build_manifest import publication_files


class WorkflowTests(unittest.TestCase):
    def test_readme_edits_preserve_evidence_integrity_check(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'evidence').mkdir()
            (root/'README.md').write_text('Original landing page', encoding='utf-8')
            evidence = root/'evidence/result.csv'
            evidence.write_bytes(b'value\n1\n')
            entries = {name:dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                       for name,path in publication_files(root)}
            self.assertNotIn('README.md', entries)
            (root/'evidence/file_manifest.json').write_text(json.dumps(dict(files=entries)), encoding='utf-8')
            (root/'README.md').write_text('Edited on GitHub', encoding='utf-8')
            self.assertEqual(check_manifest(root), 1)
            evidence.write_bytes(b'value\n2\n')
            with self.assertRaisesRegex(ValueError, 'SHA256 differs'):
                check_manifest(root)

    def test_full_plan_count(self):
        plan = validate_plan(json.loads((ROOT/'plans/full_campaign.json').read_text()))
        self.assertEqual(sum(map(len, plan.values())), 48)

    def test_invalid_inputs_before_solver_import(self):
        cases = [dict(case='x', pressure=float('nan')), dict(case='x', load_points=2.5),
                 dict(case='../x'), dict(case='x', unknown=2), dict(case='x', linear='false')]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_plan({'load': [case]})
        with self.assertRaises(ValueError):
            validate_plan({'load': [dict(case='x'), dict(case='x')]})

    def test_campaign_stays_in_results(self):
        self.assertEqual(resolve_campaign('results/campaigns/review').parent, ROOT/'results/campaigns')
        for value in ('evidence/review', 'results/campaigns/../../outside'):
            with self.assertRaises(ValueError):
                resolve_campaign(value)

    def test_launcher_configuration_and_jobname(self):
        with patch.dict(os.environ, {'PYMAPDL_MAPDL_EXEC':'', 'PYMAPDL_NPROC':'2'}):
            options = session_options('review_'+'x'*80)
            self.assertNotIn('exec_file', options)
            self.assertEqual(len(options['jobname']), 32)
            with self.assertRaises(ValueError):
                session_options('../bad')
        with patch.dict(os.environ, {'PYMAPDL_MAPDL_EXEC':'missing-mapdl.exe'}):
            with self.assertRaises(FileNotFoundError):
                session_options('review')

    def test_resume_rejects_changed_inputs(self):
        expected = validate_plan({'load':[dict(case='x')]})['load'][0]
        summary = dict(case='review_load_x',converged=True, element='SOLID285', tip_size_in=.0025,global_size_in=None,
                       nominal_pressure_peak_psi=10000.,youngs_modulus_psi=1e7,poissons_ratio=.27,
                       pressure_table_points=10,nlgeom=True,max_u_in=.1,max_s1_psi=2.,max_seqv_psi=3.)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder/'summary.json').write_text(json.dumps(summary))
            (folder/'baseline.vtu').write_text('test fixture')
            record = dict(summary,status='solved',run_directory=str(folder))
            completed_summary(record, expected)
            with self.assertRaises(ValueError):
                completed_summary(record, {**expected,'pressure':20000.})
            with self.assertRaises(ValueError):
                completed_summary({**record,'max_u_in':.2}, expected)

    def test_published_evidence_consistency(self):
        self.assertEqual(verify(manifest=False)['png_files'],165)


if __name__ == '__main__':
    unittest.main()
