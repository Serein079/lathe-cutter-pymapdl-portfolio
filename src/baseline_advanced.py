"""PARAMETERIZED EXTENSION: executed and audited on MAPDL Student 26.1.
Reproduce the official Lathe Cutter model and export auditable results.

Reference: https://mapdl.docs.pyansys.com/version/stable/examples/
gallery_examples/00-mapdl-examples/lathe_cutter.html
The physical model, mesh controls, ten-point load table, and NLGEOM setting
follow the official example. Extra code exports results and checks convergence.
"""
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from pathlib import Path

import numpy as np

if __package__:
    from .mapdl_session import ROOT, launch_session
else:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from mapdl_session import ROOT, launch_session

REFERENCE = "https://mapdl.docs.pyansys.com/version/stable/examples/gallery_examples/00-mapdl-examples/lathe_cutter.html"


def plot_fields(grid, figures):
    import pyvista as pv
    for scalar, title, filename in (
        ("S1_psi", "1st principal stress (psi)", "principal_stress.png"),
        ("SEQV_psi", "von Mises stress (psi)", "von_mises_stress.png"),
        ("U_in", "Displacement magnitude (in)", "displacement.png"),
    ):
        plotter = pv.Plotter(off_screen=True, window_size=(1600, 1000))
        plotter.set_background("white")
        plotter.add_mesh(grid, scalars=scalar, cmap="viridis", show_edges=True,
                         scalar_bar_args={"title": title, "color": "black"})
        plotter.view_isometric()
        plotter.add_axes(color="black")
        plotter.show(screenshot=str(figures / filename), auto_close=True)


def run(no_plots=False, *, case="advanced", element=285,
        tip_size=0.0025, global_size=None, pressure_peak=10000,
        ex=1e7, nu=0.27, load_points=10, nlgeom=True):
    if element not in (285, 187) or tip_size <= 0 or pressure_peak <= 0:
        raise ValueError("Invalid element, mesh size, or pressure")
    if global_size is not None and global_size <= 0:
        raise ValueError("global_size must be positive")
    if ex <= 0 or not (-1 < nu < 0.5) or load_points < 2:
        raise ValueError("Invalid material or table point count")
    geometry = ROOT / "data" / "geometry" / "LatheCutter.anf"
    if not geometry.is_file():
        raise FileNotFoundError(f"Missing geometry: {geometry}. See README.md.")
    mapdl, run_dir = launch_session(case)
    csv_dir, figures = run_dir / "csv", run_dir / "figures"
    csv_dir.mkdir()
    figures.mkdir()
    try:
        started = time.perf_counter()
        print("[1/5] Importing official geometry", flush=True)
        mapdl.clear()
        mapdl.input(str(geometry))
        mapdl.finish()
        length = float(mapdl.parameters["PRESS_LENGTH"])
        if not np.isclose(length, 0.055):
            raise ValueError(f"Unexpected pressure length: {length}")
        mapdl.units("BIN")
        mapdl.title("Lathe Cutter - official baseline reproduction")
        mapdl.prep7()
        mapdl.mp("EX", 1, ex)
        mapdl.mp("NUXY", 1, nu)
        mapdl.et(1, element)
        if global_size is None:
            mapdl.smrtsize(4)
        else:
            mapdl.smrtsize(0)
            mapdl.esize(global_size)
        if element == 187:
            mapdl.mshape(1, "3D")
            mapdl.mshkey(0)
        mapdl.aesize(14, tip_size)
        print(f"[2/5] Meshing SOLID{element}", flush=True)
        mapdl.vmesh(1)
        nodes, elements = int(mapdl.mesh.n_node), int(mapdl.mesh.n_elem)
        print(f"Mesh: {nodes} nodes, {elements} elements", flush=True)
        for area in (11, 16, 9, 10):
            mapdl.da(area, "SYMM")
        mapdl.cskp(11, 0, 2, 1, 13)
        mapdl.csys(0)
        keypoints = {str(k): [float(mapdl.get_value('KP', k, 'LOC', axis))
                            for axis in 'XYZ'] for k in (2, 1, 13)}
        mapdl.csys(1)
        x = np.linspace(0.0, length, load_points)
        pressure = pressure_peak * np.sin(np.pi * x / length)
        table = np.column_stack((x, pressure))
        np.savetxt(csv_dir / "pressure_table.csv", table, delimiter=",",
                   header="local_x_in,pressure_psi", comments="")
        mapdl.load_table("MY_PRESS", table, "X", csysid=11)
        mapdl.asel("S", "AREA", "", 14)
        mapdl.nsla("S", 1)
        loaded_nodes = int(mapdl.mesh.n_node)
        loaded_ids = mapdl.mesh.nnum.copy()
        (run_dir / 'load_definition.json').write_text(json.dumps({
            'keypoints_global_in': keypoints, 'loaded_node_ids': loaded_ids.tolist(),
            'coordinate_system': 'CSKP,11,0,2,1,13',
            'pressure_positive': 'inward', 'table_points': table.tolist()
        }, indent=2), encoding='utf-8')
        if loaded_nodes == 0:
            raise RuntimeError("Area 14 selected no nodes; pressure was not applied.")
        mapdl.sf("ALL", "PRES", "%MY_PRESS%")
        mapdl.allsel()
        mapdl.finish()
        mapdl.slashsolu()
        mapdl.nlgeom("ON" if nlgeom else "OFF")
        mapdl.save()
        print("[3/5] Solving nonlinear geometry baseline", flush=True)
        solve_output = mapdl.solve()
        solve_elapsed = time.perf_counter() - started
        (run_dir / "solve_output.txt").write_text(str(solve_output), encoding="utf-8")
        if nlgeom and not mapdl.solution.converged:
            raise RuntimeError("MAPDL solution did not converge. Inspect solver logs.")
        if not nlgeom and 'COMPLETED.' not in str(solve_output):
            raise RuntimeError('Linear load step did not complete')
        mapdl.finish()
        mapdl.post1()
        mapdl.set("LAST")
        mapdl.allsel()
        mapdl.csys(0)
        mapdl.rsys(0)
        mapdl.run('/FORMAT,10,E,22,14')
        (run_dir / "reaction_global.txt").write_text(
            str(mapdl.prrsol("F")), encoding="utf-8")
        print("[4/5] Exporting nodal results", flush=True)
        ids = mapdl.mesh.nnum.copy()
        xyz = mapdl.mesh.nodes.copy()
        post = mapdl.post_processing
        s1 = post.nodal_principal_stress("1")
        vm = post.nodal_eqv_stress()
        disp = np.column_stack([post.nodal_displacement(axis) for axis in "XYZ"])
        magnitude = np.linalg.norm(disp, axis=1)
        for values in (s1, vm, disp, xyz):
            if len(values) != len(ids) or not np.all(np.isfinite(values)):
                raise RuntimeError("Nodal result lengths or finite-value check failed.")
        data = np.column_stack((ids, xyz, s1, vm, disp, magnitude))
        np.savetxt(csv_dir / "nodal_results.csv", data, delimiter=",",
                   header="node,x_in,y_in,z_in,s1_psi,seqv_psi,ux_in,uy_in,uz_in,u_in",
                   comments="", fmt=["%d"] + ["%.12g"] * 9)
        grid = mapdl.mesh.grid.copy()
        # Use explicit node IDs rather than assuming VTK point order.
        vtk_ids = np.asarray(grid.point_data["ansys_node_num"])
        positions = {int(number): idx for idx, number in enumerate(ids)}
        order = np.array([positions[int(number)] for number in vtk_ids])
        for name, values in (("S1_psi", s1), ("SEQV_psi", vm), ("U_in", magnitude)):
            grid.point_data[name] = values[order]
        grid.point_data["Displacement_in"] = disp[order]
        grid.save(str(run_dir / "baseline.vtu"))
        summary = {
            "reference": REFERENCE, "converged": True,
            "nodes": nodes, "elements": elements, "loaded_nodes": loaded_nodes,
            "element": f"SOLID{element}", "units": {"length": "in", "stress": "psi"},
            "youngs_modulus_psi": ex, "poissons_ratio": nu,
            "pressure_length_in": length, "nominal_pressure_peak_psi": pressure_peak,
            "sampled_pressure_peak_psi": float(pressure.max()),
            "pressure_table_points": load_points, "nlgeom": nlgeom,
            "tip_size_in": tip_size, "global_size_in": global_size,
            "case": case, "vm_p95_psi": float(np.percentile(vm, 95)),
            "solution_validation": 'nonlinear CNVG plus finite results' if nlgeom else 'completed linear load step plus readable finite results',
            "solve_pipeline_seconds": solve_elapsed,
            "max_s1_psi": float(s1.max()), "max_seqv_psi": float(vm.max()),
            "max_u_in": float(magnitude.max()),
            "node_max_s1": int(ids[np.argmax(s1)]),
            "node_max_seqv": int(ids[np.argmax(vm)]),
            "geometry_sha256": hashlib.sha256(geometry.read_bytes()).hexdigest(),
            "pymapdl_version": importlib.metadata.version("ansys-mapdl-core"),
            "mapdl_version": str(mapdl.version),
            "run_directory": str(run_dir),
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2), flush=True)
        print("[5/5] Saving figures", flush=True)
        if not no_plots:
            plot_fields(grid, figures)
        mapdl.save()
    finally:
        mapdl.exit()
    print(f"Baseline complete: {run_dir}", flush=True)
    return run_dir


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--case", default="advanced")
    parser.add_argument("--element", type=int, choices=[285, 187], default=285)
    parser.add_argument("--tip-size", type=float, default=0.0025)
    parser.add_argument("--global-size", type=float)
    parser.add_argument("--pressure", type=float, default=10000)
    parser.add_argument("--ex", type=float, default=1e7)
    parser.add_argument("--nu", type=float, default=0.27)
    parser.add_argument("--load-points", type=int, default=10)
    parser.add_argument("--linear", action="store_true")
    args = parser.parse_args()
    run(args.no_plots, case=args.case, element=args.element,
        tip_size=args.tip_size, global_size=args.global_size,
        pressure_peak=args.pressure, ex=args.ex, nu=args.nu,
        load_points=args.load_points, nlgeom=not args.linear)
