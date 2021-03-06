r"""Stokes equations.

.. note::
   This example requires the external package `dmsh <https://pypi.org/project/dmsh/>`_.

This solves for the creeping flow problem in the primitive variables,
i.e. velocity and pressure instead of the stream-function.  These are governed
by the Stokes momentum

.. math::
    0 = -\rho^{-1}\nabla p + \boldsymbol{f} + \nu\Delta\boldsymbol{u}
and continuity equations

.. math::
    \nabla\cdot\boldsymbol{u} = 0.
This is an example of a mixed problem because it contains two
different kinds of unknowns; pairs of elements for them have to be
chosen carefully.  One of the simplest workable choices is the
Taylor--Hood element: :math:`P_2` for velocity
and :math:`P_1` for pressure.

Once the velocity has been found, the stream-function :math:`\psi` can
be calculated by solving the Poisson problem

.. math::
    -\Delta\psi = \mathrm{rot}\,\boldsymbol{u},
where :math:`\mathrm{rot}\,\boldsymbol{u} \equiv
\partial u_y/\partial x - \partial u_x/\partial y`.
The boundary conditions are that the stream-function is constant
around the impermeable perimeter; this constant can be taken as zero
without loss of generality.  In the weak formulation

.. math::
    \left(\nabla\phi, \nabla\psi\right) = \left(\phi, \mathrm{rot}\,\boldsymbol{u}\right) \quad \forall \phi \in H^1_0(\Omega),
the right-hand side can be converted using Green's theorem and the
no-slip condition to not involve the derivatives of the velocity:

.. math::
     \left(\phi, \mathrm{rot}\,\boldsymbol{u}\right) = \left(\boldsymbol{rot}\,\phi, \boldsymbol{u}\right)
where :math:`\boldsymbol{rot}` is the adjoint of :math:`\mathrm{rot}`:

.. math::
    \boldsymbol{rot}\,\phi \equiv \frac{\partial\phi}{\partial y}\hat{i} - \frac{\partial\phi}{\partial x}\hat{j}.

"""
from skfem import *
from skfem.models.poisson import vector_laplace, mass, laplace
from skfem.models.general import divergence, rot

import numpy as np
from scipy.sparse import bmat

import dmsh

mesh = MeshTri(*map(np.transpose,
                    dmsh.generate(dmsh.Circle([0., 0.], 1.), .1)))

element = {'u': ElementVectorH1(ElementTriP2()),
           'p': ElementTriP1()}
basis = {variable: InteriorBasis(mesh, e, intorder=3)
         for variable, e in element.items()}


@LinearForm
def body_force(v, w):
    return w.x[0] * v.value[1]


A = asm(vector_laplace, basis['u'])
B = asm(divergence, basis['u'], basis['p'])
C = asm(mass, basis['p'])

K = bmat([[A, -B.T],
          [-B, 1e-6 * C]], 'csr')

f = np.concatenate([asm(body_force, basis['u']),
                    np.zeros(B.shape[0])])

uvp = solve(*condense(K, f, D=basis['u'].find_dofs()))

velocity, pressure = np.split(uvp, [A.shape[0]])

basis['psi'] = InteriorBasis(mesh, ElementTriP2())
A = asm(laplace, basis['psi'])
vorticity = asm(rot, basis['psi'],
                w=[basis['psi'].interpolate(velocity[i::2])
                   for i in range(2)])
psi = solve(*condense(A, vorticity, D=basis['psi'].find_dofs()))


if __name__ == '__main__':

    from os.path import splitext
    from sys import argv

    from matplotlib.tri import Triangulation

    from skfem.visuals.matplotlib import plot, draw, savefig

    name = splitext(argv[0])[0]

    mesh.save(f'{name}_velocity.vtk',
              {'velocity': velocity[basis['u'].nodal_dofs].T})

    print(basis['psi'].interpolator(psi)(np.zeros((2, 1)))[0],
          '(cf. exact 1/64)')

    print(basis['p'].interpolator(pressure)(np.array([[-0.5, 0.5],
                                                      [0.5, 0.5]])),
          '(cf. exact -/+ 1/8)')

    ax = draw(mesh)
    plot(basis['p'], pressure, ax=ax)
    savefig(f'{name}_pressure.png')

    ax = draw(mesh)
    velocity1 = velocity[basis['u'].nodal_dofs]
    ax.quiver(*mesh.p, *velocity1, mesh.p[0, :])  # colour by buoyancy
    savefig(f'{name}_velocity.png')

    ax = draw(mesh)
    ax.tricontour(Triangulation(*mesh.p, mesh.t.T),
                  psi[basis['psi'].nodal_dofs.flatten()])
    savefig(f'{name}_stream-function.png')
