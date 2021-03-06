#!/usr/bin/env python
# coding: utf-8

import sys
import os
import glob

import numpy as np
from scipy.stats import linregress
from scipy.optimize import curve_fit
import pandas as pd
import matplotlib.pyplot as plt

#######################################################################
#                              Plot time                              #
#######################################################################
def compare_all_total_times(directory):
    times = pd.read_csv(os.path.join(directory, 'times.csv'), index_col=0)

    # print(times)

    times = times.groupby('nb_cells').aggregate(np.min)
    ax = times.plot(logx=True, logy=True)
    ax.set(
        xlabel='number of cells in mesh $N$',
        ylabel='computation time (seconds)',
    )

    # labels = []

    # def expFunc(x, a, b):
    #     return a * np.power(x, b)

    # x = np.asarray(times.index)
    # for column in times.columns:
    #     y = np.asarray(times[column])
    #     popt, pcov = curve_fit(expFunc, x, y)

    #     # plt.plot(x, expFunc(x, *popt), 'k--',
    #     #          label="({0:.3f}*N**{1:.3f}) + {2:.3f}".format(*popt))

    #     if column == 'Capytaine':
    #         # labels.append('No symmetry ($\sim {0:.1e} \cdot N^{{{1:.2f}}}$)'.format(*popt))
    #         # labels.append('No symmetry ($\sim N^{{{1:.2f}}}$)'.format(*popt))
    #         labels.append('No symmetry')
    #     elif '+ symmetry' in column:
    #         # labels.append('One vertical symmetry plane ($\sim {0:.1e} \cdot N^{{{1:.2f}}}$)'.format(*popt))
    #         # labels.append('One vertical symmetry plane ($\sim N^{{{1:.2f}}}$)'.format(*popt))
    #         labels.append('One vertical symmetry plane')
    #     else:
    #         # labels.append('Axial symmetry ($\sim {0:.1e} \cdot N^{{{1:.2f}}}$)'.format(*popt))
    #         # labels.append('Axial symmetry ($\sim N^{{{1:.2f}}}$)'.format(*popt))
    #         labels.append('Axial symmetry')

    # plt.legend(labels=labels)
    plt.grid()
    plt.tight_layout()


#######################################################################
#                            Time details                             #
#######################################################################
def plot_detailed_time(directory):
    dirs = glob.glob(os.path.join(directory, '*capy*'))

    # Initialization.
    detailed_time = pd.DataFrame(
        index=dirs,
        columns=['method', 'nb_cells', 'evaluate matrices', 'solve linear problem', 'total', 'other'],
    )

    for result_dir in dirs:

        # Get the number of cells and the method from the directory name.
        detailed_time['nb_cells'][result_dir] = int(result_dir.split('_')[-1])
        detailed_time['method'][result_dir] = '_'.join(result_dir.split('_')[2:-1])

        # Read profile log.
        with open(os.path.join(result_dir, 'profile.log'), 'r') as profile_file:
            for entry in profile_file.readlines():
                if '(build_matrices)' in entry:
                    detailed_time['evaluate matrices'][result_dir] = float(entry.split()[3])
                elif '(solve)' in entry and 'Toeplitz_matrices' in entry:
                    detailed_time['solve linear problem'][result_dir] = float(entry.split()[3])
                # elif 'benchmark.py:35' in entry:
                #     detailed_time['total'][result_dir] = float(entry.split()[3])
                elif 'function calls' in entry:
                    detailed_time['total'][result_dir] = float(entry.split()[-2])

    # Deduce other computation time.
    detailed_time['other'] = detailed_time['total'] - detailed_time['evaluate matrices'] - detailed_time['solve linear problem']

    # print(detailed_time)

    # For each method and mesh, keep only the fastest computation
    detailed_time = detailed_time.sort_values(by='nb_cells')
    idx = detailed_time.groupby(["method", "nb_cells"])['total'].transform(min) == detailed_time['total']
    detailed_time = detailed_time[idx]

    # Just regroup data.
    detailed_time = detailed_time.groupby(['method', 'nb_cells']).aggregate(np.min)

    print(detailed_time)

    # linreg = {}
    # for method in detailed_time.index.levels[0]:
    #     linreg[method] = {}
    #     for column in ['solve linear problem', 'evaluate matrices']:
    #         dt = detailed_time.T[method].T[column]
    #         linreg[method][column] = linregress(np.log(dt.index), np.log(np.asarray(dt)))

    max_time = detailed_time['total'].max()
    nb_methods = len(detailed_time.index.levels[0])
    fig, axs = plt.subplots(1, nb_methods, sharex=True, sharey=True)

    for i, method in enumerate(detailed_time.index.levels[0]):
        dt = detailed_time.T[method].T
        dt.plot.area(
            ax=axs[i],
            y=['solve linear problem', 'evaluate matrices', 'other'],
            legend=False,
        )
        axs[i].set(
            ylim=(0.0, 1.05*max_time),
            xlabel='number of cells in mesh',
            ylabel='computation time (seconds)',
        )

        # alpha1 = linreg[method]['evaluate matrices'].slope
        # alpha2 = linreg[method]['solve linear problem'].slope
        # plt.title(f"{method} {alpha1:.2f} {alpha2:.2f}")

        axs[i].grid(zorder=3)

    axs[-1].legend()
    plt.tight_layout()


#######################################################################
#                            Check values                             #
#######################################################################
def compare_results(directory):
    omega_range = np.linspace(0.1, 4.0, 40)

    nemoh_dirs = glob.glob(os.path.join(directory, '*Nemoh*'))
    capy_dirs = glob.glob(os.path.join(directory, '*capy*'))

    case_names = sorted(os.path.basename(name) for name in nemoh_dirs+capy_dirs)

    added_mass = pd.DataFrame(index=omega_range, columns=case_names)
    damping = pd.DataFrame(index=omega_range, columns=case_names)

    for nemoh_dir in nemoh_dirs:
        mesh = int(nemoh_dir.split('_')[-1])
        results = np.genfromtxt(os.path.join(nemoh_dir, "results", "Forces.dat"))
        added_mass[os.path.basename(nemoh_dir)] = results[::2]
        damping[os.path.basename(nemoh_dir)] = results[1::2]

    for capy_dir in capy_dirs:
        mesh = int(capy_dir.split('_')[-1])
        results = np.genfromtxt(os.path.join(capy_dir, "results.csv"))
        added_mass[os.path.basename(capy_dir)] = results[:, 0]
        damping[os.path.basename(capy_dir)] = results[:, 1]

    added_mass.plot(y=[name for name in case_names if '900' in name])
    # print(added_mass[[name for name in case_names if '600' in name]])
    damping.plot(y=[name for name in case_names if '900' in name])


if __name__ == "__main__":
    if len(sys.argv) > 1:
        compare_all_total_times(sys.argv[1])
        # plot_detailed_time(sys.argv[1])
        # compare_results(sys.argv[1])
    else:
        directory = max([path for path in os.listdir() if "201" in path])
        compare_all_total_times(directory)
        # plot_detailed_time(directory)
        # compare_results(directory)

    plt.show()

