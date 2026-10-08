"""EXECUTED TEACHING EXAMPLE, not the Lathe Cutter physical model.

Uses metres, N, Pa, W and degC; material values are synthetic.
Confirm element pairing in your MAPDL version before interpreting results.
"""
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent/'src'))
from mapdl_session import launch_session


def main():
    mapdl, run_dir = launch_session('thermal_demo')
    try:
        mapdl.clear()
        mapdl.prep7()
        mapdl.et(1,87)
        mapdl.mp('KXX',1,45)
        mapdl.block(0,0.03,0,0.01,0,0.005)
        mapdl.mshape(1,'3D')
        mapdl.mshkey(0)
        mapdl.esize(0.002)
        mapdl.vmesh('ALL')
        mapdl.nsel('S','LOC','X',0)
        mapdl.d('ALL','TEMP',20)
        mapdl.nsel('S','LOC','X',0.03)
        mapdl.d('ALL','TEMP',100)
        mapdl.allsel()
        mapdl.finish()
        mapdl.slashsolu()
        mapdl.antype('STATIC')
        thermal_log=mapdl.solve()
        if 'COMPLETED.' not in str(thermal_log):
            raise RuntimeError('Thermal solve did not converge')
        mapdl.finish()
        mapdl.post1()
        mapdl.set('LAST')
        ids=mapdl.mesh.nnum.copy()
        temperatures=mapdl.post_processing.nodal_temperature()
        if len(ids)!=len(temperatures) or not np.all(np.isfinite(temperatures)):
            raise RuntimeError('Temperature output is incomplete')
        if temperatures.min()<19.99 or temperatures.max()>100.01:
            raise RuntimeError('Temperature outside prescribed bounds')
        import pyvista as pv
        grid=mapdl.mesh.grid.copy()
        xyz=mapdl.mesh.nodes.copy()
        mapping={int(n):i for i,n in enumerate(ids)}
        order=np.array([mapping[int(n)] for n in grid['ansys_node_num']])
        grid['Temperature_degC']=temperatures[order]
        thermal_error=float(np.max(np.abs(temperatures-(20+80*xyz[:,0]/.03))))
        if thermal_error>.01: raise RuntimeError('Analytical temperature check failed')
        np.savetxt(run_dir/'temperature_degC.csv',np.column_stack((ids,temperatures)),
                   delimiter=',',header='node,temperature_degC',comments='')
        mapdl.finish()
        mapdl.prep7()
        mapdl.allsel()
        mapdl.ddele('ALL','TEMP')
        mapdl.etchg('TTS')
        element_listing=str(mapdl.etlist())
        (run_dir/'element_after_conversion.txt').write_text(element_listing,encoding='utf-8')
        if '187' not in element_listing:
            raise RuntimeError('Inspect ETCHG pairing: expected SOLID187')
        mapdl.mp('EX',1,70e9)
        mapdl.mp('NUXY',1,0.27)
        mapdl.mp('ALPX',1,12e-6)
        mapdl.tref(20)
        # Transfer temperatures on exactly the same node IDs.
        mapdl.input_strings([f'BF,{int(n)},TEMP,{t:.12g}'
                             for n,t in zip(ids,temperatures)])
        mapdl.nsel('S','LOC','X',0)
        mapdl.d('ALL','ALL',0)
        mapdl.allsel()
        mapdl.finish()
        mapdl.slashsolu()
        mapdl.antype('STATIC')
        mapdl.nlgeom('OFF')
        structural_log=mapdl.solve()
        if 'COMPLETED.' not in str(structural_log):
            raise RuntimeError('Thermal structural solve did not converge')
        mapdl.finish()
        mapdl.post1()
        mapdl.set('LAST')
        mapdl.rsys(0)
        displacement=mapdl.post_processing.nodal_displacement('NORM')
        stress=mapdl.post_processing.nodal_eqv_stress()
        vector=np.column_stack([mapdl.post_processing.nodal_displacement(a) for a in 'XYZ'])
        for field in (stress,displacement,vector):
            if not np.all(np.isfinite(field)): raise RuntimeError('Nonfinite structural result')
        grid['U_m']=displacement[order]
        grid['SEQV_Pa']=stress[order]
        grid['Displacement_m']=vector[order]
        grid.save(run_dir/'thermal_structural.vtu')
        figures=run_dir/'figures';figures.mkdir()
        for scalar,title,file in [('Temperature_degC','Temperature (degC)','temperature.png'),
                ('U_m','Displacement (m)','displacement.png'),
                ('SEQV_Pa','von Mises (Pa)','von_mises_stress.png')]:
            plotter=pv.Plotter(off_screen=True,window_size=(1600,1000))
            plotter.set_background('white')
            plotter.add_mesh(grid,scalars=scalar,show_edges=True,cmap='viridis',
                scalar_bar_args={'title':title,'color':'black'})
            plotter.view_isometric();plotter.add_axes(color='black')
            plotter.show(screenshot=str(figures/file),auto_close=True)
        np.savetxt(run_dir/'structural_nodal_results.csv',
            np.column_stack((ids,xyz,temperatures,stress,vector,displacement)),delimiter=',',
            header='node,x_m,y_m,z_m,T_degC,vm_Pa,ux_m,uy_m,uz_m,u_m',comments='')
        summary=dict(model='synthetic SI teaching block, not cutter',
                     thermal_converged=True, structural_converged=True,
                     tmin_degC=float(temperatures.min()),tmax_degC=float(temperatures.max()),
                     max_u_m=float(displacement.max()),max_seqv_Pa=float(stress.max()),
                     nodes=len(ids),elements=grid.n_cells,
                     max_temperature_analytical_error_degC=thermal_error,
                     run_directory=str(run_dir),
                     inputs=dict(k_W_mK=45,E_Pa=70e9,nu=0.27,alpha_per_K=12e-6,Tref_degC=20))
        (run_dir/'teaching_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
        (run_dir/'thermal_solve.txt').write_text(str(thermal_log),encoding='utf-8')
        (run_dir/'structural_solve.txt').write_text(str(structural_log),encoding='utf-8')
        mapdl.save()
        print(json.dumps(summary,indent=2),flush=True)
        print(f'Results: {run_dir}',flush=True)
    finally:
        mapdl.exit()


if __name__=='__main__':
    main()
