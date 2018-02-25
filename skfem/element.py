# -*- coding: utf-8 -*-
"""
Element classes define the finite element basis functions or DOF functionals.
"""
import numpy as np

class Element():
    n_dofs = 0
    f_dofs = 0
    i_dofs = 0
    e_dofs = 0
    dim = -1
    maxdeg = -1
    order = (-1, -1)  # 0 - scalar, 1 - vector, 2 - tensor, etc

    def orient(self, mapping, i, tind=None):
        """Orient basis functions. By default all = 1."""
        if tind is None:
            return 1 + 0*mapping.mesh.t[0, :]
        else:
            return 1 + 0*tind


class ElementH1(Element):
    order = (0, 1)

    def gbasis(self, mapping, X, i, tind=None):
        phi, dphi = self.lbasis(X, i)
        invDF = mapping.invDF(X, tind)
        if len(X.shape) == 2:
            return np.broadcast_to(phi, (invDF.shape[2], invDF.shape[3])),\
                   np.einsum('ijkl,il->jkl', invDF, dphi)
        elif len(X.shape) == 3:
            return np.broadcast_to(phi, (invDF.shape[2], invDF.shape[3])), \
                   np.einsum('ijkl,ikl->jkl', invDF, dphi)

    def lbasis(self, X, i):
        raise Exception("ElementH1 lbasis method not found.")


class ElementVectorH1(Element):
    order = (1, 2)

    def __init__(self, elem):
        self.dim = elem.dim
        self.elem = elem

        self.n_dofs = self.elem.n_dofs * self.dim
        self.f_dofs = self.elem.f_dofs * self.dim
        self.i_dofs = self.elem.i_dofs * self.dim
        self.e_dofs = self.elem.e_dofs * self.dim

        self.maxdeg = elem.maxdeg

    def gbasis(self, mapping, X, i, tind=None):
        ind = int(np.floor(float(i)/float(self.dim)))
        n = i - self.dim*ind
        phi, dphi = self.elem.gbasis(mapping, X, ind, tind)
        u = np.zeros((self.dim,) + phi.shape)
        du = np.zeros((self.dim,) + dphi.shape)
        u[n] = phi
        du[n] = dphi
        return u, du


class ElementHdiv(Element):
    order = (1, 0)

    def orient(self, mapping, i, tind=None):
        # TODO fix tind
        return -1 + 2*(mapping.mesh.f2t[0, mapping.mesh.t2f[i, :]] \
                       == np.arange(mapping.mesh.t.shape[1]))

    def gbasis(self, mapping, X, i, tind=None):
        phi, dphi = self.lbasis(X, i)
        DF = mapping.DF(X, tind)
        detDF = mapping.detDF(X, tind)
        orient = self.orient(mapping, i, tind)
        return np.einsum('ijkl,jl,kl->ikl', DF, phi, 1/np.abs(detDF)*orient[:, None]),\
               dphi/(np.abs(detDF)*orient[:, None])

    def lbasis(self, X, i):
        raise Exception("ElementHdiv lbasis method not found.")


class ElementHcurl(Element):
    """Note: only 3D support. Piola transformation
    is different in 2D."""
    order = (1, 1)

    def orient(self, mapping, i, tind=None):
        # TODO fix tind
        t1 = [0, 1, 0, 0, 1, 2][i]
        t2 = [1, 2, 2, 3, 3, 3][i]
        return 1 - 2*(mapping.mesh.t[t1, :] > mapping.mesh.t[t2, :])

    def gbasis(self, mapping, X, i, tind=None):
        phi, dphi = self.lbasis(X, i)
        DF = mapping.DF(X, tind)
        invDF = mapping.invDF(X, tind)
        detDF = mapping.detDF(X, tind)
        orient = self.orient(mapping, i, tind)
        return np.einsum('ijkl,il,k->jkl', invDF, phi, orient), \
               np.einsum('ijkl,jl,kl->ikl', DF, dphi, 1/detDF*orient[:, None])

    def lbasis(self, X, i):
        raise Exception("ElementHcurl lbasis method not found.")


class ElementH2(Element):
    order = (0, 3)
    V = None  # For caching inverse Vandermonde matrix

    def gbasis(self, mapping, X, i, tind=None):
        # initialize power basis
        self._pbasis_init(self.maxdeg)
        N = len(self._pbasis)

        if self.V is None:
            # construct Vandermonde matrix and invert it
            self.V = np.linalg.inv(self._eval_dofs(mapping.mesh, tind=tind))

        x = mapping.F(X, tind=tind)
        u = np.zeros(x[0].shape)
        du = np.zeros((2, 2, 2) + x[0].shape)

        # loop over new basis
        for itr in range(N):
            u += self.V[:, itr, i][:, None]\
                 * self._pbasis[itr](x[0], x[1])
            du[0, 0, 0] += self.V[:, itr, i][:, None]\
                           * self._pbasisdx[itr](x[0], x[1])
            du[0, 0, 1] += self.V[:, itr, i][:,None]\
                           * self._pbasisdy[itr](x[0], x[1])
            du[1, 0, 0] += self.V[:, itr, i][:, None]\
                           * self._pbasisdxx[itr](x[0], x[1])
            du[1, 0, 1] += self.V[:, itr, i][:, None]\
                           * self._pbasisdxy[itr](x[0], x[1])
            du[1, 1, 1] += self.V[:, itr, i][:, None]\
                           * self._pbasisdyy[itr](x[0], x[1])

        # dxy = dyx
        du[1, 1, 0] = du[1, 0, 1]

        # Empty
        du[0, 1, 0] = u + np.nan
        du[0, 1, 1] = u + np.nan

        return u, du

    def _pbasis_init(self, N):
        """Define power bases (for 2D)."""
        if not hasattr(self, '_pbasis' + str(N)):
            import sympy as sp
            from sympy.abc import x, y
            R = list(range(N+1))
            ops = {
                '': lambda a: a,
                'dx': lambda a: sp.diff(a, x),
                'dy': lambda a: sp.diff(a, y),
                'dxx': lambda a: sp.diff(a, x, 2),
                'dyy': lambda a: sp.diff(a, y, 2),
                'dxy': lambda a: sp.diff(sp.diff(a, x), y),
            }
            for name, op in ops.items():
                pbasis = [sp.lambdify((x,y), op(x**i*y**j), "numpy")
                          for i in R for j in R if i+j<=N]
                # workaround for constant shape bug in SymPy
                for itr in range(len(pbasis)):
                    const = pbasis[itr](np.zeros(2), np.zeros(2))
                    if type(const) is int:
                        pbasis[itr] = lambda X, Y, const=const: const*np.ones(X.shape)
                setattr(self, '_pbasis'+name, pbasis)

    def _eval_dofs(self, mesh, tind=None):
        if tind is None:
            tind = np.arange(mesh.t.shape[1])
        N = len(self._pbasis)

        V = np.zeros((len(tind), N, N))

        if mesh.t.shape[0] == 3:
            # vertices, edges, tangents, normals
            v = np.empty((3, 2, len(tind)))
            e = np.empty((3, 2, len(tind)))
            n = np.empty((3, 2, len(tind)))

            # vertices
            for itr in range(3):
                v[itr] = mesh.p[:, mesh.t[itr, tind]]

            # edge midpoints
            e[0] = 0.5*(v[0] + v[1])
            e[1] = 0.5*(v[1] + v[2])
            e[2] = 0.5*(v[0] + v[2])

            # normal vectors
            n[0] = v[0] - v[1]
            n[1] = v[1] - v[2]
            n[2] = v[0] - v[2]

            for itr in range(3):
                n[itr] = np.array([n[itr, 1, :], -n[itr, 0, :]])
                n[itr] /= np.linalg.norm(n[itr], axis=0)
        else:
            raise NotImplementedError("The used mesh type not supported in ElementH2.")

        # evaluate dofs, gdof implemented in subclasses
        for itr in range(N):
            for jtr in range(N):
                u = self._pbasis[itr]
                du = [self._pbasisdx[itr], self._pbasisdy[itr]]
                ddu = [self._pbasisdxx[itr], self._pbasisdxy[itr], self._pbasisdyy[itr]]
                V[:, jtr, itr] = self.gdof(u, du, ddu, v, e, n, jtr)

        return V

# Triangular

class ElementTriP1(ElementH1):
    n_dofs = 1
    dim = 2
    maxdeg = 1

    def lbasis(self, X, i):
        x, y = X[0, :], X[1, :]

        if i == 0:
            phi = 1 - x - y
            dphi = np.array([-1 + 0*x, -1 + 0*x])
        elif i == 1:
            phi = x
            dphi = np.array([1 + 0*x, 0*x])
        elif i == 2:
            phi = y
            dphi = np.array([0*x, 1 + 0*x])
        else:
            raise Exception("!")

        return phi, dphi


class ElementTriP0(ElementH1):
    i_dofs = 1
    dim = 2
    maxdeg = 0

    def lbasis(self, X, i):
        return 1 + 0*X[0, :], 0*X


class ElementTriRT0(ElementHdiv):
    f_dofs = 1
    dim = 2
    maxdeg = 1

    def lbasis(self, X, i):
        x, y = X[0, :], X[1, :]

        if i == 0:
            phi = np.array([x, y-1])
            dphi = 2 + 0*x
        elif i == 1:
            phi = np.array([x, y])
            dphi = 2 + 0*x
        elif i == 2:
            phi = np.array([x-1, y])
            dphi = 2 + 0*x
        else:
            raise Exception("!")

        return phi, dphi


class ElementMorley(ElementH2):
    n_dofs = 1
    f_dofs = 1
    dim = 2
    maxdeg = 2

    def gdof(self, u, du, ddu, v, e, n, i):
        if i == 0:
            return u(*v[0])
        elif i == 1:
            return u(*v[1])
        elif i == 2:
            return u(*v[2])
        elif i == 3:
            return du[0](*e[0])*n[0, 0] + du[1](*e[0])*n[0, 1]
        elif i == 4:
            return du[0](*e[1])*n[1, 0] + du[1](*e[1])*n[1, 1]
        elif i == 5:
            return du[0](*e[2])*n[2, 0] + du[1](*e[2])*n[2, 1]
        else:
            raise Exception("!")

# Quadilateral

class ElementQ1(ElementH1):
    n_dofs = 1
    dim = 2
    maxdeg = 2

    def lbasis(self, X, i):
        x, y = X[0, :], X[1, :]

        if i == 0:
            phi = 0.25*(1 - x)*(1 - y)
            dphi = np.array([0.25*(-1 + y), 0.25*(-1 + x)])
        elif i == 1:
            phi = 0.25*(1 + x)*(1 - y)
            dphi = np.array([0.25*(1 - y), 0.25*(-1 - x)])
        elif i == 2:
            phi = 0.25*(1 + x)*(1 + y)
            dphi = np.array([0.25*(1 + y), 0.25*(1 + x)])
        elif i == 3:
            phi = 0.25*(1 - x)*(1 + y)
            dphi = np.array([0.25*(-1 - y), 0.25*(1 - x)])
        else:
            raise Exception("!")

        return phi, dphi

class ElementQ2(ElementH1):
    n_dofs = 1
    f_dofs = 1
    i_dofs = 1
    dim = 2
    maxdeg = 3

    def lbasis(self, X, i):
        x, y = X[0, :], X[1, :]

        if i == 0:
            phi = 0.25*(x**2-x)*(y**2-y)
            dphi = np.array([((-1 + 2*x)*(-1 + y)*y)/4., ((-1 + x)*x*(-1 + 2*y))/4.])
        elif i == 1:
            phi = 0.25*(x**2+x)*(y**2-y)
            dphi = np.array([((1 + 2*x)*(-1 + y)*y)/4.,(x*(1 + x)*(-1 + 2*y))/4. ])
        elif i == 2:
            phi = 0.25*(x**2+x)*(y**2+y)
            dphi = np.array([((1 + 2*x)*y*(1 + y))/4., (x*(1 + x)*(1 + 2*y))/4.])
        elif i == 3:
            phi = 0.25*(x**2-x)*(y**2+y)
            dphi = np.array([((-1 + 2*x)*y*(1 + y))/4., ((-1 + x)*x*(1 + 2*y))/4.])
        elif i == 4:
            phi = 0.5*(y**2-y)*(1-x**2)
            dphi = np.array([-(x*(-1 + y)*y), -((-1 + x**2)*(-1 + 2*y))/2.])
        elif i == 5:
            phi = 0.5*(x**2+x)*(1-y**2)
            dphi = np.array([-((1 + 2*x)*(-1 + y**2))/2., -(x*(1 + x)*y)])
        elif i == 6:
            phi = 0.5*(y**2+y)*(1-x**2)
            dphi = np.array([-(x*y*(1 + y)), -((-1 + x**2)*(1 + 2*y))/2.])
        elif i == 7:
            phi = 0.5*(x**2-x)*(1-y**2)
            dphi = np.array([-((-1 + 2*x)*(-1 + y**2))/2., -((-1 + x)*x*y)])
        elif i == 8:
            phi = (1-x**2)*(1-y**2)
            dphi = np.array([2*x*(-1 + y**2), 2*(-1 + x**2)*y])
        else:
            raise Exception("!")

        return phi, dphi

# Tetrahedral

class ElementTetP0(ElementH1):
    i_dofs = 1
    dim = 3
    maxdeg = 0

    def lbasis(self, X, i):
        return 1 + 0*X[0, :], 0*X


class ElementTetRT0(ElementHdiv):
    f_dofs = 1
    dim = 3
    maxdeg = 1

    def lbasis(self, X, i):
        x, y, z = X[0, :], X[1, :], X[2, :]

        if i == 0:
            phi = np.array([x, y, z-1])
            dphi = 3 + 0*x
        elif i == 1:
            phi = np.array([x, y-1, z])
            dphi = 3 + 0*x
        elif i == 2:
            phi = np.array([x-1, y, z])
            dphi = 3 + 0*x
        elif i == 3:
            phi = np.array([x, y, z])
            dphi = 3 + 0*x
        else:
            raise Exception("!")

        return phi, dphi


class ElementTetN0(ElementHcurl):
    e_dofs = 1
    dim = 3
    maxdeg = 1

    def lbasis(self, X, i):
        x, y, z = X[0, :], X[1, :], X[2, :]

        if i == 0:
            phi = np.array([1-z-y, x, x])
            dphi = np.array([0*x, -2 + 0*x, 2 + 0*x])
        elif i == 1:
            phi = np.array([-y, x, 0*z])
            dphi = np.array([0*x, 0*x, 2 + 0*x])
        elif i == 2:
            phi = np.array([y, 1-z-x, y])
            dphi = np.array([2 + 0*x, 0*x, -2 + 0*x])
        elif i == 3:
            phi = np.array([z, z, 1-x-y])
            dphi = np.array([-2 + 0*x, 2 + 0*x, 0*x])
        elif i == 4:
            phi = np.array([-z, 0*y, x])
            dphi = np.array([0*x, -2 + 0*x, 0*x])
        elif i == 5:
            phi = np.array([0*x, -z, y])
            dphi = np.array([2 + 0*x, 0*x, 0*x])
        else:
            raise Exception("!")

        return phi, dphi
