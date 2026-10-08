"""Read-only integrity and consistency checks; Python standard library only."""
import argparse
import ast
import csv
import hashlib
import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GEOMETRY_SHA256 = '3224b465091948b2f9bd2d3bd41f8564f0c313fa5ac38920481f17551fa39553'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_rows(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def inside(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), f'Path escapes repository: {relative}')
    require(path.exists(), f'Missing file/directory: {relative}')
    return path


def check_manifest(root):
    manifest = root / 'evidence' / 'file_manifest.json'
    require(manifest.is_file(), 'Missing publication manifest')
    entries = json.loads(manifest.read_text(encoding='utf-8'))['files']
    for relative, expected in entries.items():
        path = inside(root, relative)
        require(path.stat().st_size == expected['bytes'], f'Size differs: {relative}')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256'], f'SHA256 differs: {relative}')
    return len(entries)


def verify(root=ROOT, manifest=True):
    root = Path(root)
    geometry = root / 'data/geometry/LatheCutter.anf'
    require(hashlib.sha256(geometry.read_bytes()).hexdigest() == GEOMETRY_SHA256, 'Geometry hash differs')
    for name in ('LICENSE', 'NOTICE.md', 'third_party/PYMAPDL_LICENSE.txt', 'third_party/EXAMPLE_DATA_LICENSE.txt'):
        inside(root, name)
    rows = read_rows(root / 'evidence/all_cases.csv')
    require(len(rows) == 47, 'Expected 47 advanced structural records')
    require(len({r['case'] for r in rows}) == 47, 'Duplicate advanced case')
    require(len({r['study'] for r in rows}) == 10, 'Expected 10 study groups')
    fields = ('nodes', 'elements', 'max_u_in', 'max_s1_psi', 'max_seqv_psi',
              'nominal_pressure_peak_psi', 'youngs_modulus_psi', 'pressure_table_points')
    for row in rows:
        folder = inside(root, row['run_directory'])
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        require(row['status'] == 'solved' and summary['converged'] is True, f'Unverified case: {row["case"]}')
        require(row['geometry_sha256'] == GEOMETRY_SHA256, 'CSV geometry hash differs')
        require(summary['case'] == row['case'] and summary['element'] == row['element'], 'Case identity differs')
        for field in fields:
            number = float(row[field])
            require(math.isfinite(number), f'Nonfinite {field}')
            require(math.isclose(number, float(summary[field]), rel_tol=1e-10), f'CSV/summary mismatch: {field}')
    folders = list((root / 'evidence/cases').iterdir())
    require(len(folders) == 48, 'Expected 48 case folders including parity')
    snapshots = read_rows(root / 'evidence/snapshots.csv')
    require(len(snapshots) == 4, 'Expected four full mesh snapshots')
    total_nodes = 0
    for row in snapshots:
        folder = inside(root, row['run_directory'])
        inside(root, (folder / 'baseline.vtu').relative_to(root))
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        nodal = read_rows(folder / 'csv/nodal_results.csv')
        require(len(nodal) == summary['nodes'], 'Nodal count differs')
        require(len({r['node'] for r in nodal}) == len(nodal), 'Duplicate node IDs')
        for field, metric in (('u_in', 'max_u_in'), ('s1_psi', 'max_s1_psi'), ('seqv_psi', 'max_seqv_psi')):
            values = [float(r[field]) for r in nodal]
            require(all(math.isfinite(v) for v in values), f'Nonfinite nodal field: {field}')
            require(math.isclose(max(values), summary[metric], rel_tol=2e-10), f'Nodal maximum differs: {field}')
        total_nodes += len(nodal)
    images = list((root / 'evidence').rglob('*.png')) + list((root / 'docs/assets').glob('*.png'))
    require(len(images) == 165, 'Expected 165 retained PNGs')
    for path in images:
        header = path.read_bytes()[:24]
        require(header[:8] == b'\x89PNG\r\n\x1a\n', f'Invalid PNG: {path.name}')
        width, height = struct.unpack('>II', header[16:24])
        require(width >= 600 and height >= 400, f'Unexpected small figure: {path.name}')
    metrics = json.loads((root / 'evidence/metrics.json').read_text(encoding='utf-8'))
    for name in ('force_balance_linear', 'force_balance_nonlinear'):
        audit = metrics[name]
        inside(root, audit['run_directory'])
        force = audit['integrated_pressure_force_lbf']
        reaction = audit['reaction_global_lbf']
        residual = math.sqrt(sum((a+b)**2 for a,b in zip(force,reaction))) / math.sqrt(sum(a*a for a in force))
        require(math.isclose(residual, audit['residual_initial_geometry'], rel_tol=1e-10), 'Force residual differs')
    dense = {r['case']: r for r in read_rows(root / 'evidence/studies/dense_mesh/study_results.csv')}
    probe = {r['case']: r for r in read_rows(root / 'evidence/studies/dense_mesh/analysis/fixed_point_results.csv')}
    for change in metrics['dense_mesh']['last_two_changes']:
        old, new = change['from_case'], change['to_case']
        for dataset, field, name in ((dense, 'max_u_in', 'displacement_change_percent'),
                                     (dense, 'max_seqv_psi', 'peak_vm_change_percent'),
                                     (probe, 'probe_vm_psi', 'fixed_vm_change_percent')):
            a,b = float(dataset[old][field]), float(dataset[new][field])
            require(math.isclose(abs(b-a)/abs(b)*100, change[name], rel_tol=1e-9), f'Dense mesh metric differs: {name}')
    # Parsing never imports solver or plotting dependencies.
    sources = list(root.glob('*.py')) + list((root / 'src').glob('*.py')) + list((root / 'tests').glob('*.py'))
    for path in sources:
        ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    files = check_manifest(root) if manifest else 0
    return dict(advanced_records=47, structural_cases=48, png_files=len(images),
                snapshot_nodes_checked=total_nodes, source_files_parsed=len(sources), manifest_files=files)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-manifest', action='store_true', help='Use only while intentionally updating publication files')
    args = parser.parse_args()
    print('PASS: ' + json.dumps(verify(manifest=not args.skip_manifest)))
    print('Integrity checks do not replace physical validation or a new MAPDL solve.')
