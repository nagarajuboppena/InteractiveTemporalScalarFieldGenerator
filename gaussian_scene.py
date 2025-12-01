import math
import random
from vtkmodules.vtkCommonDataModel import vtkImageData
import vtk

try:
    from noise import pnoise2
    PERLIN_AVAILABLE = True
except:
    PERLIN_AVAILABLE = False


class GaussianScene:
    def __init__(self, width=200, height=200):
        self.width = width
        self.height = height
        self.spacing = 1.0
        self.gaussians = []
        self._next_id = 1

        # NEW: selected distribution
        self.distribution_type = "Gaussian"

        # Path system
        self.paths = {}
        self.path_index = {}
        self.path_speed = 0.5

    def updateWidthHeight(self, w, h, space=1.0):
        self.width = w
        self.height = h
        self.spacing = space


    def clear(self):
        """
        Clear all Gaussians from the scene.
        """
        self.gaussians = []
        self._next_id = 1


    # =============================================================
    # ADDING GAUSSIAN-LIKE SOURCES
    # =============================================================
    def add_gaussian(self, x=None, y=None, amplitude=1.0, variance=100.0):
        if x is None:
            x = random.uniform(0.2, 0.8) * self.width * self.spacing
        if y is None:
            y = random.uniform(0.2, 0.8) * self.height * self.spacing

        g = {
            "id": self._next_id,
            "x": x,
            "y": y,
            "amp": amplitude,
            "var": variance,
            # extra params for some distributions
            "sx": math.sqrt(variance),
            "sy": math.sqrt(variance/10),
            "theta": 40.0,
            "gamma": variance,  # Cauchy scale
            "lambda": math.sqrt(variance),
        }
        self.gaussians.append(g)
        self._next_id += 1

    # =============================================================
    # DISTRIBUTION FUNCTIONS
    # =============================================================

    def f_gaussian(self, x, y, g):
        r2 = (x - g['x'])**2 + (y - g['y'])**2
        return g['amp'] * math.exp(-r2 / (2*g['var']))

    def f_cauchy(self, x, y, g):
        r2 = (x - g['x'])**2 + (y - g['y'])**2
        return g['amp'] / (1 + r2 / g["gamma"])

    def f_mexican_hat(self, x, y, g):
        r2 = (x - g['x'])**2 + (y - g['y'])**2
        sigma = g['var']
        return g['amp'] * (1 - r2 / sigma**2) * math.exp(-r2/(2*sigma**2))

    def f_exponential_decay(self, x, y, g):
        r = math.sqrt((x - g['x'])**2 + (y - g['y'])**2)
        return g['amp'] * math.exp(-r / g["lambda"])

    def f_plateau(self, x, y, g):
        r = math.sqrt((x - g['x'])**2 + (y - g['y'])**2)
        return g['amp'] / (1 + (r / math.sqrt(g['var']))**3)

    def f_anisotropic(self, x, y, g):
        cx, cy = g['x'], g['y']
        sx, sy = g['sx'], g['sy']
        t = g['theta']
        xp = (x-cx)*math.cos(t) + (y-cy)*math.sin(t)
        yp = -(x-cx)*math.sin(t) + (y-cy)*math.cos(t)
        return g['amp'] * math.exp(-(xp*xp)/(2*sx*sx) - (yp*yp)/(2*sy*sy))

    def f_multi_lobe(self, x, y, g):
        r2 = (x - g['x'])**2 + (y - g['y'])**2
        base = g['amp'] * math.exp(-r2/(2*g['var']))
        angle = math.atan2(y - g['y'], x - g['x'])
        return base * (1 + 0.3 * math.sin(4 * angle))

    def f_ridge(self, x, y, g):
        r = math.sqrt((x - g['x'])**2 + (y - g['y'])**2)
        return g['amp'] * (1 - abs(math.sin(r)))

    def f_perlin(self, x, y, g):
        if not PERLIN_AVAILABLE:
            return 0.0
        scale = 0.05
        return g['amp'] * pnoise2(x * scale, y * scale)

    # =============================================================
    # MAIN FIELD GENERATOR
    # =============================================================
    def generate_image_data(self):
        S = 2
        W = self.width * S
        H = self.height * S
        dx = self.spacing / S

        img = vtkImageData()
        img.SetDimensions(W, H, 1)
        img.SetSpacing(dx, dx, 1)
        img.AllocateScalars(vtk.VTK_DOUBLE, 1)

        # Select distribution function
        dist_map = {
            "Gaussian": self.f_gaussian,
            "Cauchy": self.f_cauchy,
            "Mexican Hat": self.f_mexican_hat,
            "Exponential": self.f_exponential_decay,
            "Plateau": self.f_plateau,
            "Anisotropic Gaussian": self.f_anisotropic,
            "Multi-Lobe": self.f_multi_lobe,
            "Ridge": self.f_ridge,
            "Perlin Noise": self.f_perlin,
        }
        #print("Distribution Type:",self.distribution_type)

        #print("paths aare : ",self.paths)

        dist_fn = dist_map[self.distribution_type]

        for j in range(H):
            for i in range(W):
                x = i * dx
                y = j * dx

                val = 0.0
                # use max of components (or sum if you want)
                for g in self.gaussians:
                    val = max(val, dist_fn(x, y, g))

                img.SetScalarComponentFromDouble(i, j, 0, 0, val)

        return img


    def move_gaussians_by_vector_field(self, vector_field, speed=1.0):
        """
        Move Gaussians according to the given VTK vector field (vtkImageData).

        Args:
            vector_field (vtkImageData): Vector field grid with 3-component vectors.
            speed (float): Scaling factor for motion step.
        """

        #print("Moving gaussians by vector field...")
        if vector_field is None:
            return

        dims = vector_field.GetDimensions()
        spacing = vector_field.GetSpacing()
        vectors = vector_field.GetPointData().GetVectors()
        if vectors is None:
            return

        width, height = dims[0], dims[1]

        def get_vector(ix, iy):
            # clamp indices to grid
            ix = max(0, min(ix, width - 1))
            iy = max(0, min(iy, height - 1))
            idx = iy * width + ix
            return vectors.GetTuple3(idx)

        def bilinear_sample(x, y):
            """
            Bilinearly interpolate the velocity vector at fractional world position (x, y).
            """
            # Convert world coordinates → grid coordinates
            gx = x / spacing[0]
            gy = y / spacing[1]

            # Integer grid cell corners
            i0 = int(math.floor(gx))
            j0 = int(math.floor(gy))
            i1 = min(i0 + 1, width - 1)
            j1 = min(j0 + 1, height - 1)

            # Fractional parts
            dx = gx - i0
            dy = gy - j0

            # Fetch vectors at 4 neighboring grid points
            v00 = get_vector(i0, j0)
            v10 = get_vector(i1, j0)
            v01 = get_vector(i0, j1)
            v11 = get_vector(i1, j1)

            # Bilinear interpolation for each component
            vx = (
                v00[0] * (1 - dx) * (1 - dy)
                + v10[0] * dx * (1 - dy)
                + v01[0] * (1 - dx) * dy
                + v11[0] * dx * dy
            )
            vy = (
                v00[1] * (1 - dx) * (1 - dy)
                + v10[1] * dx * (1 - dy)
                + v01[1] * (1 - dx) * dy
                + v11[1] * dx * dy
            )
            vz =0.0
            return vx, vy, vz

        for g in self.gaussians:
            # compute grid indices
            gx = int(g['x'] / spacing[0])
            gy = int(g['y'] / spacing[1])
            vx, vy, _ = bilinear_sample(g['x'], g['y'])

            # normalize (optional)
            mag = (vx**2 + vy**2) ** 0.5 + 1e-8
            vx, vy = vx / mag, vy / mag

            # update positions
            g['x'] += speed * vx
            g['y'] += speed * vy

            # clamp within bounds
            g['x'] = min(max(g['x'], 0), self.width*self.spacing - 1)
            g['y'] = min(max(g['y'], 0), self.height*self.spacing - 1)


    def move_gaussians_by_custom_path(self, vector_field, speed=1.0):
        """
        Move Gaussians according to the given VTK vector field (vtkImageData).

        Args:
            vector_field (vtkImageData): Vector field grid with 3-component vectors.
            speed (float): Scaling factor for motion step.
        """
        #print("Moving gaussians by custom paths...")
        for g in self.gaussians:
            gid = g['id']

            # if this gaussian has a custom path
            if gid in self.paths and len(self.paths[gid]) > 0:

                idx = self.path_index.get(gid, 0)
                tx, ty = self.paths[gid][idx]

                # compute movement
                dx = tx - g['x']
                dy = ty - g['y']
                dist = math.sqrt(dx*dx + dy*dy)

                if dist < 0.5:
                    self.path_index[gid] = idx + 1
                    if self.path_index[gid] >= len(self.paths[gid]):
                        self.path_index[gid] = 0  # or stop
                    continue

                g['x'] += self.path_speed * dx / dist
                g['y'] += self.path_speed * dy / dist
