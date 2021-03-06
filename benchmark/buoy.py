#!/usr/bin/env python
# coding: utf-8

import datetime
from itertools import count, product

import numpy as np
import pandas as pd

from capytaine.symmetries import ReflectionSymmetry, xOz_Plane
from capytaine.reference_bodies import generate_axi_symmetric_body

from benchmark import *

WORKING_DIRECTORY = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")

ID = count()


def shape(z):
    return 0.1*(-(z+1)**2 + 16)


def full_resolution_Nemoh(nb_slices, nz, omega_range):
    buoy = generate_axi_symmetric_body(shape, z_range=np.linspace(-5.0, 0.0, nz+1), nphi=nb_slices)
    buoy.dofs["Heave"] = buoy.faces_normals @ (0, 0, 1)
    buoy = buoy.as_FloatingBody(name="buoy")
    return profile_Nemoh(buoy, omega_range,
                         f"{WORKING_DIRECTORY}/{next(ID):03}_Nemoh_{nz*nb_slices}")


def full_Capytaine(nb_slices, nz, omega_range):
    buoy = generate_axi_symmetric_body(shape, z_range=np.linspace(-5.0, 0.0, nz+1), nphi=nb_slices)
    buoy.dofs["Heave"] = buoy.faces_normals @ (0, 0, 1)
    buoy = buoy.as_FloatingBody(name="buoy")
    return profile_capytaine(buoy, omega_range,
                             f"{WORKING_DIRECTORY}/{next(ID):03}_capy_{nz*nb_slices}")


def sym_Capytaine(nb_slices, nz, omega_range):
    buoy = generate_axi_symmetric_body(shape, z_range=np.linspace(-5.0, 0.0, nz+1), nphi=nb_slices)
    buoy.dofs["Heave"] = buoy.faces_normals @ (0, 0, 1)
    buoy = buoy.as_FloatingBody()
    half_buoy = buoy.extract_faces(np.where(buoy.faces_centers[:, 1] > 0)[0]) # Keep y > 0
    buoy = ReflectionSymmetry(half_buoy, xOz_Plane)
    buoy.name = "buoy"
    return profile_capytaine(buoy, omega_range,
                             f"{WORKING_DIRECTORY}/{next(ID):03}_sym_capy_{nz*nb_slices}")


def rot_Capytaine(nb_slices, nz, omega_range):
    buoy = generate_axi_symmetric_body(shape, z_range=np.linspace(-5.0, 0.0, nz+1), nphi=nb_slices)
    buoy.dofs["Heave"] = buoy.faces_normals @ (0, 0, 1)
    buoy.name = "buoy"
    return profile_capytaine(buoy, omega_range,
                             f"{WORKING_DIRECTORY}/{next(ID):03}_rot_capy_{nz*nb_slices}")


# ===============================================================
# ===============================================================
# ===============================================================

if __name__ == "__main__":

    nb_repetitions = 3
    nb_cells_range = 2*(np.sqrt(np.linspace(200, 3000, 15))//2)
    nz_range = [int(x) for x in nb_cells_range]
    nb_slices_range = [int(x) for x in nb_cells_range]
    omega_range = np.linspace(0.1, 4.0, 40)

    cases = {
        # "Nemoh 2.0":                full_resolution_Nemoh,
        "Capytaine":                full_Capytaine,
        "Capytaine + symmetry":     sym_Capytaine,
        "Capytaine + axisymmetry":  rot_Capytaine,
        }

    # ===========================

    times = pd.DataFrame(
        index=range(nb_repetitions*len(nb_slices_range)),
        columns=["nb_cells"] + list(cases.keys()),
    )

    for i, ((nb_slices, nz), k) in enumerate(product(zip(nb_slices_range, nz_range), range(nb_repetitions))):
        print(f"====> {nb_slices}×{nz} cells, Repetition: {k+1}/{nb_repetitions}")
        times["nb_cells"][i] = nb_slices*nz
        for name, function in cases.items():
            print("\t\t" + name)
            times[name][i] = function(nb_slices, nz, omega_range)

    print(times)
    times.to_csv(f'{WORKING_DIRECTORY}/times.csv')
