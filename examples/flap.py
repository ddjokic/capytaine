#!/usr/bin/env python
# coding: utf-8
"""
Example computation: added mass and damping of an oscillating flap.
"""

import os
import glob
import logging

import numpy as np
import matplotlib.pyplot as plt

from capytaine.reference_bodies import (generate_open_rectangular_parallelepiped,
                                        generate_clever_open_rectangular_parallelepiped)
from capytaine.problems import RadiationProblem
from capytaine.Nemoh import Nemoh

result_directory = os.path.join(os.path.dirname(__file__), "flap_results")


def solve_flap(clever=True, resolution=2):
    """Solve the flap problem for a given resolution.

    Parameters:
    resolution: int
        the number of cells in the mesh will be proportional to this coefficient
    """
    # Load reference range of frequencies
    T_range, _, _ = np.loadtxt(os.path.join(os.path.dirname(__file__), "data/flap_mu_nu.tsv")).T

    depth = 10.9

    # Create mesh
    if clever:
        # Use prismatic shape to speed up computations.
        flap = generate_clever_open_rectangular_parallelepiped(
            height=depth, width=3.0, thickness=0.001,
            nh=int(10*resolution), nw=int(3*resolution))
    else:
        # Do not use prismatic shape to speed up computations.
        flap = generate_open_rectangular_parallelepiped(
            height=depth, width=3.0, thickness=0.001,
            nh=int(10*resolution), nw=int(3*resolution))

    flap.translate_z(-depth)

    # Set oscillation degree of freedom
    flap.dofs["Oscillation"] = np.asarray([
        flap.faces_normals[j, 1] *
        (flap.faces_centers[j, 2] + 9.4) * np.heaviside(flap.faces_centers[j, 2] + 9.4, 0.0)
        for j in range(flap.nb_faces)])

    # Set up problems and initialise solver
    problems = [RadiationProblem(body=flap, omega=omega, sea_bottom=-depth) for omega in 2*np.pi/T_range]
    solver = Nemoh()

    # Solve problems
    results = np.asarray(solver.solve_all(problems, processes=1))

    # Create directory to store results
    if not os.path.isdir(result_directory):
        os.mkdir(result_directory)

    # Save result in csv file
    result_file_path = os.path.join(os.path.dirname(__file__), "flap_results",
                                    f"Results_{'clever_' if clever else ''}{30*resolution**2}_cells.csv")
    if os.path.exists(result_file_path):
        LOG.warning(f"Overwriting {result_file_path}")

    np.savetxt(result_file_path, np.asarray(results))


def plot_flap_results():
    """Plot the results of all the csv files in result directory."""

    # Load reference result
    T_range, mu, nu = np.loadtxt(os.path.join(os.path.dirname(__file__), "data/flap_mu_nu.tsv")).T

    # Plot reference results
    plt.figure(1)
    plt.plot(T_range, mu, linestyle="--", label="Reference added mass")

    plt.figure(2)
    plt.plot(T_range, nu, linestyle="--", label="Reference added damping")

    # Plot all results in result directory
    for fichier in glob.glob(os.path.join(result_directory, "*.csv")):
        mu, nu = np.loadtxt(fichier).T

        nb_cells = int(fichier.split('_')[-2])

        plt.figure(1)
        plt.plot(T_range, mu, label=f"Added mass ({nb_cells} cells)")

        plt.figure(2)
        plt.plot(T_range, nu, label=f"Added damping ({nb_cells} cells)")

    plt.figure(1)
    plt.xlabel("Wave period (s)")
    plt.legend()
    plt.tight_layout()

    plt.figure(2)
    plt.xlabel("Wave period (s)")
    plt.legend()
    plt.tight_layout()

    plt.show()


if __name__ == "__main__":
    from datetime import datetime

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s:\t%(message)s", datefmt="%H:%M:%S")
    LOG = logging.getLogger(__name__)

    start_time = datetime.now()
    solve_flap(resolution=2, clever=True)
    end_time = datetime.now()
    LOG.info(f"Duration: {end_time - start_time}")

    plot_flap_results()
