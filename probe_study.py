"""Extract interpolated results at a fixed interior point from study VTUs.

Default point: centroid of a baseline tetrahedron adjacent to node 716.
It is a diagnostic location, not proof of peak-stress convergence.
"""
import argparse
import csv
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent

DEFAULT_POINT=(-0.05771153017614537,0.18891918500115723,-0.21029335472554514)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path',type=Path)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results'/'probes')
    parser.add_argument('--point',type=float,nargs=3,default=DEFAULT_POINT,
                        metavar=('X_IN','Y_IN','Z_IN'))
    args=parser.parse_args()
    import numpy as np
    import pyvista as pv
    rows=list(csv.DictReader(args.csv_path.open(encoding='utf-8-sig')))
    if not rows:
        raise ValueError('Study CSV is empty')
    point=np.asarray([args.point],dtype=float)
    result=[]
    fields={'probe_s1_psi':'S1_psi','probe_vm_psi':'SEQV_psi','probe_u_in':'U_in'}
    for row in rows:
        if row.get('status')!='solved' or row.get('converged') not in ('True','true'):
            raise ValueError(f"Unverified case: {row.get('case')}")
        directory=Path(row['run_directory'])
        directory=ROOT/directory if not directory.is_absolute() else directory
        path=directory/'baseline.vtu'
        if not path.is_file():
            raise FileNotFoundError(f'Missing mesh snapshot: {path}; use evidence/snapshots.csv or new solver results')
        grid=pv.read(path)
        probe=pv.PolyData(point).sample(grid)
        if int(probe['vtkValidPointMask'][0])!=1:
            raise ValueError(f"Point outside case {row['case']}; choose and document another point")
        output={key:row.get(key,'') for key in (
            'case','element','tip_size_in','global_size_in','nodes','elements',
            'nominal_pressure_peak_psi','youngs_modulus_psi','pressure_table_points','nlgeom')}
        for name,scalar in fields.items():
            value=float(probe[scalar][0])
            if not np.isfinite(value):
                raise ValueError(f"Invalid {scalar} for {row['case']}")
            output[name]=value
        result.append(output)
    outdir=args.output_dir
    outdir.mkdir(parents=True,exist_ok=True)
    metadata={'point_in':list(args.point),
              'method':'VTK sample on nodal-averaged fields; vtkValidPointMask required',
              'scope':'fixed-location diagnostic, not a maximum-stress convergence certificate'}
    definition=outdir/'probe_definition.json'
    if definition.exists():
        previous=json.loads(definition.read_text(encoding='utf-8'))
        if previous['point_in']!=metadata['point_in']:
            raise ValueError('Existing probe definition differs; use a separate study directory')
    definition.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    target=outdir/'fixed_point_results.csv'
    with target.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(result[0]))
        writer.writeheader();writer.writerows(result)
    print(f'Fixed point (in): {list(args.point)}')
    print(f'PASS: valid interpolated results for {len(result)} cases')
    print(f'CSV: {target}')


if __name__=='__main__':
    main()
