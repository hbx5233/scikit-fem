from typing import Optional

import numpy as np
from numpy import ndarray

from skfem.quadrature import get_quadrature

from .global_basis import GlobalBasis


class InteriorBasis(GlobalBasis):
    """Global basis functions evaluated at integration points inside the
    elements.

    Attributes
    ----------
    phi : numpy array
        Global basis functions at global quadrature points.
    dphi : numpy array
        Global basis function derivatives at global quadrature points.
    X : numpy array of size Ndim x Nqp
        Local quadrature points.
    W : numpy array of size Nqp
        Local quadrature weights.
    nelems : int
    dx : numpy array of size Nelems x Nqp
        Can be used in computing global integrals elementwise.
        For example, np.sum(u**2*dx, axis=1) where u is also
        a numpy array of size Nelems x Nqp.
    mapping : an object of the type skfem.mapping.Mapping
    elem : an object of the type skfem.element.Element
    Nbfun : int
    intorder : int
    dim : int
    nt : int
    mesh : an object of the type skfem.mesh.Mesh
    refdom : string
    brefdom : string

    Examples
    --------

    InteriorBasis object is a combination of Mesh, Element,
    and Mapping:

    >>> from skfem import *
    >>> from skfem.models.poisson import laplace
    >>> m = MeshTri.init_symmetric()
    >>> e = ElementTriP1()
    >>> ib = InteriorBasis(m, e, MappingAffine(m))

    The resulting objects are used in the assembly.

    >>> K = asm(laplace, ib)
    >>> K.shape
    (5, 5)

    """
    def __init__(self, mesh, elem, mapping=None, intorder=None):
        super(InteriorBasis, self).__init__(mesh, elem, mapping, intorder)

        self.X, self.W = get_quadrature(self.refdom, self.intorder)

        self.basis = list(zip(*[self.elem.gbasis(self.mapping, self.X, j) for j in range(self.Nbfun)]))

        self.nelems = self.nt
        self.dx = np.abs(self.mapping.detDF(self.X)) * np.tile(self.W, (self.nelems, 1))

    def default_parameters(self):
        return {'x':self.global_coordinates(),
                'h':self.mesh_parameters()}

    def global_coordinates(self) -> ndarray:
        return self.mapping.F(self.X)

    def mesh_parameters(self) -> ndarray:
        return np.abs(self.mapping.detDF(self.X)) ** (1.0 / self.mesh.dim())

    def refinterp(self, interp: ndarray, Nrefs: Optional[int] = 1):
        """Refine and interpolate (for plotting)."""
        # mesh reference domain, refine and take the vertices
        meshclass = type(self.mesh)
        m = meshclass.init_refdom()
        m.refine(Nrefs)
        X = m.p

        # map vertices to global elements
        x = self.mapping.F(X)

        # interpolate some previous discrete function at the vertices
        # of the refined mesh
        w = 0.0*x[0]

        for j in range(self.Nbfun):
            basis = self.elem.gbasis(self.mapping, X, j)
            w += interp[self.element_dofs[j, :]][:, None]*basis[0]

        nt = self.nt
        t = np.tile(m.t, (1, nt))
        dt = np.max(t)
        t += (dt+1)*np.tile(np.arange(nt), (m.t.shape[0]*m.t.shape[1], 1)).flatten('F').reshape((-1, m.t.shape[0])).T

        if X.shape[0]==1:
            p = np.array([x.flatten()])
        else:
            p = x[0].flatten()
            for itr in range(len(x)-1):
                p = np.vstack((p, x[itr+1].flatten()))

        M = meshclass(p, t, validate=False)

        return M, w.flatten()