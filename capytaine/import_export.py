#!/usr/bin/env python
# coding: utf-8
"""
Import or export Nemoh.cal files for backward compatibility with Nemoh 2.
"""

import os

import numpy as np

from meshmagick.mmio import write_MAR
from capytaine.bodies import FloatingBody
from capytaine.problems import DiffractionProblem, RadiationProblem
from capytaine.bodies_collection import CollectionOfFloatingBodies

def import_cal_file(filepath):
    """
    Read a Nemoh.cal file and return a list of problems.
    """

    with open(filepath, 'r') as cal_file:

        cal_file.readline() # Unused line.
        rho = float(cal_file.readline().split()[0])
        g = float(cal_file.readline().split()[0])
        depth = float(cal_file.readline().split()[0])
        if depth == 0.0:
            sea_bottom = -np.infty
        else:
            sea_bottom = -depth
        xeff, yeff = (float(x) for x in cal_file.readline().split()[0:2])

        bodies = []

        cal_file.readline() # Unused line.
        nb_bodies = int(cal_file.readline().split()[0])
        for i_body in range(nb_bodies):
            cal_file.readline() # Unused line.
            mesh_file = cal_file.readline().split()[0].strip()
            cal_file.readline() # Number of points, number of panels (unused)

            body = FloatingBody.from_file(
                os.path.join(os.path.dirname(filepath), mesh_file), # mesh path are relative to Nemoh.cal
                'mar')

            nb_dofs = int(cal_file.readline().split()[0])
            for i_dof in range(nb_dofs):
                dof_data = cal_file.readline().split()
                if int(dof_data[0]) == 1:
                    direction = np.array([float(x) for x in dof_data[1:4]])
                    body.add_translation_dof(direction=direction)
                elif int(dof_data[0]) == 2:
                    direction = np.array([float(x) for x in dof_data[1:4]])
                    center_of_mass = np.array([float(x) for x in dof_data[4:7]])
                    body.add_rotation_dof(axis_direction=direction, axis_point=center_of_mass)

            nb_forces = int(cal_file.readline().split()[0])
            for i_force in range(nb_forces):
                force_data = cal_file.readline().split()
                if int(force_data[0]) == 1:
                    direction = np.array([float(x) for x in force_data[1:4]])
                elif int(force_data[0]) == 2:
                    direction = np.array([float(x) for x in force_data[1:4]])
                    center_of_mass = np.array([float(x) for x in force_data[4:7]])
            # TODO: use the generalize forces.

            nb_additional_lines = int(cal_file.readline().split()[0])
            for _ in range(nb_additional_lines):
                cal_file.readline() # The additional lines are just ignored.

            bodies.append(body)

        bodies = CollectionOfFloatingBodies(bodies)

        cal_file.readline() # Unused line.
        frequency_data = cal_file.readline().split()
        omega_range = np.linspace(float(frequency_data[1]), float(frequency_data[2]), int(frequency_data[0]))

        direction_data = cal_file.readline().split()
        direction_range = np.linspace(float(direction_data[1]), float(direction_data[2]), int(direction_data[0]))

        # The options below are not implemented yet.

        cal_file.readline() # Unused line.
        irf_data = cal_file.readline()
        show_pressure = cal_file.readline().split()[0] == "1"
        kochin_data = cal_file.readline().split()
        kochin_range = np.linspace(float(kochin_data[1]), float(kochin_data[2]), int(kochin_data[0]))
        free_surface_data = cal_file.readline().split()

    # Generate Capytaine's problem objects
    env_args = dict(body=bodies, rho=rho, sea_bottom=sea_bottom, g=g)
    problems = []
    for omega in omega_range:
        for direction in direction_range:
            problems.append(DiffractionProblem(angle=direction, omega=omega, **env_args))
        if bodies.nb_dofs > 0:
            problems.append(RadiationProblem(omega=omega, **env_args))

    return problems


def export_as_Nemoh_directory(problem, directory_name, omega_range=None):
    """
    Export radiation problems as Nemoh 2.0 directory (experimental).

    TODO: Diffraction problem.

    Parameters
    ----------
    problem: RadiationProblem
        the problem that should be exported
    directory_name: string
        path to the directory
    omega_range: list of float or array of float
        the exported problem will be set up with the following linear range:
        linspace(min(omega_range), max(omega_range), len(omega_range))
    """

    if os.path.isdir(directory_name):
        warn(f"""Exporting problem in already existing directory: {directory_name}
             You might be overwriting existing files!""")
    else:
        os.makedirs(directory_name)

    # Export the mesh
    write_MAR(
        os.path.join(directory_name, f'{problem.body.name}.dat'),
        problem.body.vertices,
        problem.body.faces,
        # xOz_symmetry=isinstance(problem.body, ReflectionSymmetry)
    )

    # Set range of frequencies
    if omega_range is None:
        omega_nb_steps = 1
        omega_start = omega
        omega_stop = omega
    else:
        omega_nb_steps = len(omega_range)
        omega_start = min(omega_range)
        omega_stop = max(omega_range)

    # Write Nemoh.cal
    with open(os.path.join(directory_name, "Nemoh.cal"), "w") as nemoh_cal:
        nemoh_cal.write(
                DEFAULT_NEMOH_CAL.format(
                    rho=problem.rho,
                    g=problem.g,
                    depth=problem.depth,
                    mesh_filename=f'{problem.body.name}.dat',
                    mesh_vertices=problem.body.nb_vertices,
                    mesh_faces=problem.body.nb_faces,
                    omega_nb_steps=omega_nb_steps,
                    omega_start=omega_start,
                    omega_stop=omega_stop,
                    )
                )

    # Write input.txt
    with open(os.path.join(directory_name, "input.txt"), "w") as input_txt:
        input_txt.write(DEFAULT_INPUT_TXT)

    # Write ID.dat
    with open(os.path.join(directory_name, "ID.dat"), "w") as id_dat:
        id_dat.write(f"1\n.")


DEFAULT_NEMOH_CAL = """--- Environment ------------------------------------------------------------------------------------------------------------------
{rho}			! RHO			! KG/M**3	! Fluid specific volume
{g}				! G			! M/S**2	! Gravity
{depth}			! DEPTH			! M		! Water depth
0.	0.			! XEFF YEFF		! M		! Wave measurement point
--- Description of floating bodies -----------------------------------------------------------------------------------------------
1				! Number of bodies
--- Body 1 -----------------------------------------------------------------------------------------------------------------------
{mesh_filename}
{mesh_vertices} {mesh_faces}
1				! Number of degrees of freedom
1 0. 0. 1. 0. 0. 0.		! Heave
1				! Number of resulting generalised forces
1 0. 0. 1. 0. 0. 0.		! Heave
0				! Number of lines of additional information
--- Load cases to be solved -------------------------------------------------------------------------------------------------------
{omega_nb_steps} {omega_start} {omega_stop} ! Frequencies range
0	0.	0.		! Number of wave directions, Min and Max (degrees)
--- Post processing ---------------------------------------------------------------------------------------------------------------
0	0.1	10.		! IRF				! IRF calculation (0 for no calculation), time step and duration
0				! Show pressure
0	0.	180.		! Kochin function		! Number of directions of calculation (0 for no calculations), Min and Max (degrees)
0	0	100.	100.	! Free surface elevation	! Number of points in x direction (0 for no calcutions) and y direction and dimensions of domain in x and y direction
"""

DEFAULT_INPUT_TXT="""--- Calculation parameters ------------------------------------------------------------------------------------
1				! Indiq_solver		! -		! Solver (0) Direct Gauss (1) GMRES (2) GMRES with FMM acceleration (2 not implemented yet)
20				! IRES			! -		! Restart parameter for GMRES
5.E-07				! TOL_GMRES		! -		! Stopping criterion for GMRES
100				! MAXIT			! -		! Maximum iterations for GMRES
1				! Sav_potential		! -		! Save potential for visualization
"""
