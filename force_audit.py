"""Independent triangular-face pressure integration for SOLID285 only."""
import argparse, json, re
from pathlib import Path
import numpy as np
import pyvista as pv

def audit(path, output=None):
    path=Path(path); summary=json.loads((path/'summary.json').read_text())
    if summary['element']!='SOLID285': raise ValueError('Audit requires four-node tetrahedra')
    grid=pv.read(path/'baseline.vtu')
    definition=json.loads((path/'load_definition.json').read_text())
    loaded=set(definition['loaded_node_ids'])
    kp=definition['keypoints_global_in']; origin=np.array(kp['2'])
    axis=np.array(kp['1'])-origin; axis/=np.linalg.norm(axis)
    local_x=(grid.points-origin)@axis
    table=np.array(definition['table_points'])
    pressure=np.interp(local_x,table[:,0],table[:,1])
    faces={}
    for i in range(grid.n_cells):
        cell=list(grid.get_cell(i).point_ids)
        if len(cell)!=4: raise ValueError('Expected four-node tetrahedral cells')
        for opposite in range(4):
            face=tuple(sorted(cell[j] for j in range(4) if j!=opposite))
            faces.setdefault(face,[]).append(cell[opposite])
    original_force=np.zeros(3); deformed_force=np.zeros(3); area=0.; count=0
    deformed=grid.points+grid['Displacement_in']
    for face,other in faces.items():
        if len(other)!=1 or not all(int(grid['ansys_node_num'][n]) in loaded for n in face): continue
        q=grid.points[list(face)]; cross=np.cross(q[1]-q[0],q[2]-q[0])/2
        if np.dot(cross,grid.points[other[0]]-q.mean(axis=0))>0: cross=-cross
        mean=float(pressure[list(face)].mean())
        original_force-=cross*mean
        qd=deformed[list(face)]; cd=np.cross(qd[1]-qd[0],qd[2]-qd[0])/2
        if np.dot(cd,deformed[other[0]]-qd.mean(axis=0))>0: cd=-cd
        deformed_force-=cd*mean
        area+=np.linalg.norm(cross); count+=1
    reaction_text=(path/'reaction_global.txt').read_text()
    total=re.search(r'TOTAL VALUES\s*VALUE([^\n]+)',reaction_text)
    if not total: raise ValueError('Missing reaction total')
    reaction=np.array([float(x.replace('D','E')) for x in re.findall(
        r'[-+]?\d*\.\d+(?:[ED][-+]?\d+)?',total.group(1))])
    if len(reaction)!=3: raise ValueError('Reaction parse failed')
    result=dict(run_directory=str(path),area_in2=float(area),loaded_triangles=count,
        integrated_pressure_force_lbf=original_force.tolist(),reaction_global_lbf=reaction.tolist(),
        residual_initial_geometry=np.linalg.norm(original_force+reaction)/np.linalg.norm(original_force),
        residual_deformed_geometry=np.linalg.norm(deformed_force+reaction)/np.linalg.norm(deformed_force),
        deformed_pressure_force_lbf=deformed_force.tolist(),nlgeom=summary['nlgeom'],
        method='Boundary tetra faces on area-14 node set; piecewise-linear nodal pressure; global PRRSOL F total',
        scope='Force resultant only. Nonlinear deformed integration assumes pressure values retained from initial coordinates.')
    target=Path(output) if output else Path(__file__).resolve().parent/'results'/'audits'/(path.name+'.json')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    audit(args.run_directory,args.output)
