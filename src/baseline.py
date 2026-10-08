"""Reproduce the official Lathe Cutter model and export auditable results.

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


def run(no_plots=False):
    geometry = ROOT / "data" / "geometry" / "LatheCutter.anf"
    if not geometry.is_file():
        raise FileNotFoundError(f"Missing geometry: {geometry}. See README.md.")
    mapdl, run_dir = launch_session("baseline")
    csv_dir, figures = run_dir / "csv", run_dir / "figures"
    csv_dir.mkdir()
    figures.mkdir()
    try:
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
        mapdl.mp("EX", 1, 1.0e7)
        mapdl.mp("NUXY", 1, 0.27)
        mapdl.et(1, 285)
        mapdl.smrtsize(4)
        mapdl.aesize(14, 0.0025)
        print("[2/5] Meshing SOLID285", flush=True)
        mapdl.vmesh(1)
        nodes, elements = int(mapdl.mesh.n_node), int(mapdl.mesh.n_elem)
        print(f"Mesh: {nodes} nodes, {elements} elements", flush=True)
        for area in (11, 16, 9, 10):
            mapdl.da(area, "SYMM")
        mapdl.cskp(11, 0, 2, 1, 13)
        mapdl.csys(1)
        x = np.arange(10, dtype=float) * length / 9
        pressure = 10000 * np.sin(np.pi * x / length)
        table = np.column_stack((x, pressure))
        np.savetxt(csv_dir / "pressure_table.csv", table, delimiter=",",
                   header="local_x_in,pressure_psi", comments="")
        mapdl.load_table("MY_PRESS", table, "X", csysid=11)
        mapdl.asel("S", "AREA", "", 14)
        mapdl.nsla("S", 1)
        loaded_nodes = int(mapdl.mesh.n_node)
        if loaded_nodes == 0:
            raise RuntimeError("Area 14 selected no nodes; pressure was not applied.")
        mapdl.sf("ALL", "PRES", "%MY_PRESS%")
        mapdl.allsel()
        mapdl.finish()
        mapdl.slashsolu()
        mapdl.nlgeom("ON")
        mapdl.save()
        print("[3/5] Solving nonlinear geometry baseline", flush=True)
        solve_output = mapdl.solve()
        (run_dir / "solve_output.txt").write_text(str(solve_output), encoding="utf-8")
        if not mapdl.solution.converged:
            raise RuntimeError("MAPDL solution did not converge. Inspect solver logs.")
        mapdl.finish()
        mapdl.post1()
        mapdl.set("LAST")
        mapdl.allsel()
        mapdl.csys(0)
        mapdl.rsys(0)
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
            "element": "SOLID285", "units": {"length": "in", "stress": "psi"},
            "youngs_modulus_psi": 1e7, "poissons_ratio": 0.27,
            "pressure_length_in": length, "nominal_pressure_peak_psi": 10000,
            "sampled_pressure_peak_psi": float(pressure.max()),
            "pressure_table_points": 10, "nlgeom": True,
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
    args = parser.parse_args()
    run(args.no_plots)
