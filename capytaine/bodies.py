#!/usr/bin/env python
# coding: utf-8
"""Floating bodies to be used in radiation-diffraction problems.

class FloatingBody
"""

import logging
import copy

import numpy as np

from meshmagick.mesh import Mesh
from meshmagick.geometry import Plane
from meshmagick.mesh_clipper import MeshClipper

import capytaine._Green as _Green
from capytaine.tools import MaxLengthDict


LOG = logging.getLogger(__name__)


class FloatingBody(Mesh):
    """A floating body described as a mesh and some degrees of freedom.

    The mesh structure is inherited from meshmagick Mesh class (see
    documentation of this class for more details). The degrees of freedom
    (dofs) are stored as a dict associating a name to a 1 dimensional array of
    length equal to the number of faces in the mesh.
    """

    #######################################
    #  Initialisation and transformation  #
    #######################################

    def __init__(self, *args, **kwargs):
        Mesh.__init__(self, *args, **kwargs)
        self._compute_radiuses()
        self.nb_matrices_to_keep = 1
        self.dofs = {}
        LOG.info(f"New floating body: {self.name}.")

    @staticmethod
    def from_file(filename, file_format):
        """Create a FloatingBody from a mesh file using meshmagick."""
        from meshmagick.mmio import load_mesh
        vertices, faces = load_mesh(filename, file_format)
        return FloatingBody(vertices, faces, name=filename)

    def __add__(self, body_to_add):
        """Create a new CollectionOfFloatingBody from the combination of two of them."""
        from capytaine.bodies_collection import CollectionOfFloatingBodies
        return CollectionOfFloatingBodies([self, body_to_add])

    def as_FloatingBody(self, name=None):
        if name is not None:
            LOG.debug(f"Rename {self.name} as {name}.")
            self.name = name
        return self

    def copy(self, name=None):
        new_body = copy.deepcopy(self)
        if name is None:
            new_body.name = f"copy_of_{self.name}"
            LOG.debug(f"Copy {self.name}.")
        else:
            new_body.name = name
            LOG.debug(f"Copy {self.name} under the name {name}.")
        return new_body

    def extract_faces(self, id_faces_to_extract, return_index=False):
        """Create a new FloatingBody by extracting some faces from the mesh."""
        if return_index:
            new_body, id_v = Mesh.extract_faces(self, id_faces_to_extract, return_index)
        else:
            new_body = Mesh.extract_faces(self, id_faces_to_extract, return_index)
        new_body.__class__ = FloatingBody
        new_body.nb_matrices_to_keep = self.nb_matrices_to_keep
        LOG.info(f"Extract floating body from {self.name}.")

        new_body.dofs = {}
        for name, dof in self.dofs.items():
            new_body.dofs[name] = dof[id_faces_to_extract]

        if return_index:
            return new_body, id_v
        else:
            return new_body

    def get_immersed_part(self, free_surface=0.0, sea_bottom=-np.infty):
        """Remove the parts of the body above the free surface or below the sea bottom."""
        clipped_mesh = MeshClipper(self,
                                   plane=Plane(normal=(0.0, 0.0, 1.0),
                                               scalar=free_surface)).clipped_mesh

        if sea_bottom > -np.infty:
            clipped_mesh = MeshClipper(clipped_mesh,
                                       plane=Plane(normal=(0.0, 0.0, -1.0),
                                                   scalar=-sea_bottom)).clipped_mesh

        clipped_mesh.remove_unused_vertices()

        LOG.info(f"Clip floating body {self.name}.")
        return FloatingBody(clipped_mesh.vertices, clipped_mesh.faces)

    def add_translation_dof(self, direction=(1.0, 0.0, 0.0), name=None):
        if name is None:
            name = f"Translation_dof_{self.nb_dofs}"
        self.dofs[name] = self.faces_normals @ direction

    def add_rotation_dof(self, axis_direction=(0.0, 0.0, 1.0), axis_point=(0.0, 0.0, 0.0), name=None):
        if name is None:
            name = f"Rotation_dof_{self.nb_dofs}"

        # TODO: Rewrite more efficiently and/or elegantly
        dof = np.empty((self.nb_faces, ), dtype=np.float32)
        for i, (cdg, normal) in enumerate(zip(self.faces_centers, self.faces_normals)):
            dof[i] = np.cross(axis_point - cdg, axis_direction) @ normal
        self.dofs[name] = dof

    ########################
    #  Various properties  #
    ########################

    @property
    def nb_dofs(self):
        """Number of degrees of freedom."""
        return len(self.dofs)

    @property
    def faces_radiuses(self):
        """Get the array of faces radiuses of the mesh."""
        if 'faces_radiuses' not in self.__internals__:
            self._compute_radiuses()
        return self.__internals__['faces_radiuses']

    def _compute_radiuses(self):
        """Compute the radiuses of the faces of the mesh.

        The radius is defined here as the maximal distance between the center
        of mass of a cell and one of its points."""
        from numpy.linalg import norm
        faces_radiuses = np.zeros(self.nb_faces, dtype=np.float32)
        for j in range(self.nb_faces): # TODO: optimize by array broadcasting
            faces_radiuses[j] = max(
                norm(self.faces_centers[j, 0:3] -
                     self.vertices[self.faces[j, 0], 0:3]),
                norm(self.faces_centers[j, 0:3] -
                     self.vertices[self.faces[j, 1], 0:3]),
                norm(self.faces_centers[j, 0:3] -
                     self.vertices[self.faces[j, 2], 0:3]),
                norm(self.faces_centers[j, 0:3] -
                     self.vertices[self.faces[j, 3], 0:3]),
                )
        self.__internals__["faces_radiuses"] = faces_radiuses

    #######################################
    #  Computation of influence matrices  #
    #######################################
    # TODO: move to Nemoh.py?

    def _build_matrices_0(self, body):
        """Compute the first part of the influence matrices of self on body."""
        if 'Green0' not in self.__internals__:
            self.__internals__['Green0'] = MaxLengthDict({}, max_length=self.nb_matrices_to_keep)
            LOG.debug(f"\t\tCreate Green0 dict (max_length={self.nb_matrices_to_keep}) in {self.name}")

        if body not in self.__internals__['Green0']:
            LOG.debug(f"\t\tComputing matrix 0 of {self.name} on {body.name}")
            S0, V0 = _Green.green_1.build_matrix_0(
                self.faces_centers, self.faces_normals,
                body.vertices,      body.faces + 1,
                body.faces_centers, body.faces_normals,
                body.faces_areas,   body.faces_radiuses,
                )

            self.__internals__['Green0'][body] = (S0, V0)
        else:
            LOG.debug(f"\t\tRetrieving stored matrix 0 of {self.name} on {body.name}")
            S0, V0 = self.__internals__['Green0'][body]

        return S0, V0

    def _build_matrices_1(self, body, free_surface, sea_bottom):
        """Compute the second part of the influence matrices of self on body."""
        if 'Green1' not in self.__internals__:
            self.__internals__['Green1'] = MaxLengthDict({}, max_length=self.nb_matrices_to_keep)
            LOG.debug(f"\t\tCreate Green1 dict (max_length={self.nb_matrices_to_keep}) in {self.name}")

        depth = free_surface - sea_bottom
        if (body, depth) not in self.__internals__['Green1']:
            LOG.debug(f"\t\tComputing matrix 1 of {self.name} on {body.name} for depth={depth:.2e}")
            def reflect_vector(x):
                y = x.copy()
                y[:, 2] = -x[:, 2]
                return y

            if depth == np.infty:
                def reflect_point(x):
                    y = x.copy()
                    y[:, 2] = 2*free_surface - x[:, 2]
                    return y
            else:
                def reflect_point(x):
                    y = x.copy()
                    y[:, 2] = 2*sea_bottom - x[:, 2]
                    return y

            S1, V1 = _Green.green_1.build_matrix_0(
                reflect_point(self.faces_centers), reflect_vector(self.faces_normals),
                body.vertices,      body.faces + 1,
                body.faces_centers, body.faces_normals,
                body.faces_areas,   body.faces_radiuses,
                )

            if depth == np.infty:
                self.__internals__['Green1'][(body, np.infty)] = (-S1, -V1)
                return -S1, -V1
            else:
                self.__internals__['Green1'][(body, depth)] = (S1, V1)
                return S1, V1
        else:
            S1, V1 = self.__internals__['Green1'][(body, depth)]
            LOG.debug(f"\t\tRetrieving stored matrix 1 of {self.name} on {body.name} for depth={depth:.2e}")
            return S1, V1


    def _build_matrices_2(self, body, free_surface, sea_bottom, wavenumber):
        """Compute the third part of the influence matrices of self on body."""
        if 'Green2' not in self.__internals__:
            self.__internals__['Green2'] = MaxLengthDict({}, max_length=self.nb_matrices_to_keep)
            LOG.debug(f"\t\tCreate Green2 dict (max_length={self.nb_matrices_to_keep}) in {self.name}")

        depth = free_surface - sea_bottom
        if (body, depth, wavenumber) not in self.__internals__['Green2']:
            LOG.debug(f"\t\tComputing matrix 2 of {self.name} on {body.name} for depth={depth:.2e} and k={wavenumber:.2e}")
            if depth == np.infty:
                S2, V2 = _Green.green_2.build_matrix_2(
                    self.faces_centers, self.faces_normals,
                    body.faces_centers, body.faces_areas,
                    wavenumber,         0.0,
                    self is body
                    )
            else:
                S2, V2 = _Green.green_2.build_matrix_2(
                    self.faces_centers, self.faces_normals,
                    body.faces_centers, body.faces_areas,
                    wavenumber,         depth,
                    self is body
                    )

            self.__internals__['Green2'][(body, depth, wavenumber)] = (S2, V2)
        else:
            S2, V2 = self.__internals__['Green2'][(body, depth, wavenumber)]
            LOG.debug(f"\t\tRetrieving stored matrix 2 of {self.name} on {body.name} for depth={depth:.2e} and k={wavenumber:.2e}")

        return S2, V2

    def build_matrices(self, body, free_surface=0.0, sea_bottom=-np.infty, wavenumber=1.0, **kwargs):
        """Return the influence matrices of self on body."""

        LOG.debug(f"\tEvaluating matrix of {self.name} on {body.name} for depth={free_surface-sea_bottom:.2e} and k={wavenumber:.2e}")

        S = np.zeros((self.nb_faces, body.nb_faces), dtype=np.complex64)
        V = np.zeros((self.nb_faces, body.nb_faces), dtype=np.complex64)

        S0, V0 = self._build_matrices_0(body)
        S += S0
        V += V0

        if free_surface < np.infty:

            S1, V1 = self._build_matrices_1(body, free_surface, sea_bottom)
            S += S1
            V += V1

            S2, V2 = self._build_matrices_2(body, free_surface, sea_bottom, wavenumber)
            S += S2
            V += V2

        return S, V
