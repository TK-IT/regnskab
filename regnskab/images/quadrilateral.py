import numpy as np
import scipy.ndimage


def _coeff_property(i, j):
    def fget(self):
        return self.A[i, j]

    def fset(self, v):
        self.A[i, j] = v

    return property(
        fget, fset, None,
        "The (%d, %d)-entry of the matrix" % (i, j))


def _coeff_properties(n, m):
    return tuple(_coeff_property(i, j) for i in range(n) for j in range(m))


class Quadrilateral(object):
    """
    Transformation between world coordinates (R x R)
    and quadrilateral-local coordinates ([0, 1] x [0, 1]).
    Quadrilateral corners are x0,y0 to x3,y3 in the world,
    and the transformation of (u, v) in the unit square
    to world coordinates is (x'/w, y'/w) given by
    [x']   [a  b  c] [u]
    [y'] = [d  e  f] [v]
    [w ]   [g  h  i] [1].

    Based on "Projective Mappings for Image Warping" by Paul Heckbert, 1999.
    """

    def __init__(self, xy):
        xy = np.asarray(xy)
        if xy.shape != (4, 2):
            raise TypeError(
                "xy must be (4, 2) with corners in rows, not %r"
                % (xy.shape,))
        x, y = xy.T
        self.A = np.eye(3)
        d1 = xy[1] - xy[2]
        d2 = xy[3] - xy[2]
        s = xy[0] - xy[1] + xy[2] - xy[3]

        self.c = x[0]
        self.f = y[0]
        self.i = 1

        if (s ** 2).sum() < 1e-6:
            # Parallelogram
            self.a = x[1] - x[0]
            self.b = x[2] - x[1]
            self.d = y[1] - y[0]
            self.e = y[2] - y[1]
            self.g = self.h = 0
        else:
            g1 = s[0] * d2[1] - d2[0] * s[1]
            h1 = d1[0] * s[1] - s[0] * d1[1]
            den = d1[0] * d2[1] - d2[0] * d1[1]
            self.g = g1 / den
            self.h = h1 / den
            self.a = x[1] - x[0] + self.g * x[1]
            self.b = x[3] - x[0] + self.h * x[3]
            self.d = y[1] - y[0] + self.g * y[1]
            self.e = y[3] - y[0] + self.h * y[3]

        self.A_inv = np.linalg.inv(self.A)

    def arg(self):
        return np.transpose(self.to_world(
            [[0, 1, 1, 0], [0, 0, 1, 1]]))

    @classmethod
    def from_vertices(cls, corners, vertices):
        return cls([vertices[i] for i in corners])

    (a, b, c,
     d, e, f,
     g, h, i) = _coeff_properties(3, 3)

    @staticmethod
    def _projective_transform(A, x):
        x = np.asarray(x)
        if x.shape[0] != 2 or x.ndim != 2:
            raise TypeError(
                "data matrix must have 2 rows; invalid shape is %r"
                % (x.shape,))
        x1 = np.asarray((x[0], x[1], np.ones_like(x[0])))
        Ax = np.dot(A, x1)
        res_x = Ax[0] / Ax[2]
        res_y = Ax[1] / Ax[2]
        return np.asarray((res_x, res_y))

    def to_world(self, uv):
        """
        Transform columns of uv in local space to columns of result in world.
        """
        return self._projective_transform(self.A, uv)

    def to_local(self, xy):
        """
        Transform columns of xy in world space to columns of result in local.
        """
        return self._projective_transform(self.A_inv, xy)


def extract_quadrilateral(im, q, width, height, output=None):
    y, x = np.mgrid[0:1:height*1j, 0:1:width*1j]
    xy = np.array((x.ravel(), y.ravel()))
    x, y = q.to_world(xy)
    if output is None:
        output = np.zeros((height, width) + im.shape[2:])
    if im.ndim > 2:
        cs = [(i,) for i in range(im.shape[2])]
    else:
        cs = [()]
    for c in cs:
        s = (slice(None), slice(None)) + c
        output[s] = scipy.ndimage.interpolation.map_coordinates(
            im[s], (y, x), order=1).reshape(
            (output.shape[0], output.shape[1]))
    return output
