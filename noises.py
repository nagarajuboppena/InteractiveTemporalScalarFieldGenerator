
from vtk.util import numpy_support as vnp
import numpy as np
from noise import pnoise2
import vtk



def add_salt_noise(field, amount=0.02):
    noisy = field.copy()
    num = int(amount * field.size)
    coords = (np.random.randint(0, field.shape[0], num),
              np.random.randint(0, field.shape[1], num))
    noisy[coords] = 1.0
    return noisy

def add_pepper_noise(field, amount=0.02):
    noisy = field.copy()
    num = int(amount * field.size)
    coords = (np.random.randint(0, field.shape[0], num),
              np.random.randint(0, field.shape[1], num))
    noisy[coords] = 0.0
    return noisy

def add_salt_pepper_noise(field, amount=0.05, salt_ratio=0.5):
    noisy = field.copy()
    num_salt = int(amount * field.size * salt_ratio)
    num_pepper = int(amount * field.size * (1 - salt_ratio))
    # Salt
    coords = (np.random.randint(0, field.shape[0], num_salt),
              np.random.randint(0, field.shape[1], num_salt))
    noisy[coords] = 1.0
    # Pepper
    coords = (np.random.randint(0, field.shape[0], num_pepper),
              np.random.randint(0, field.shape[1], num_pepper))
    noisy[coords] = 0.0
    return noisy

def add_gaussian_noise(field, mean=0.0, std=0.05):
    noise = np.random.normal(mean, std, field.shape)
    return np.clip(field + noise, 0, 1)


def add_gaussian_few_noise(field, num_gaussians=5, amplitude=0.05, sigma=3.0):
    h, w = field.shape
    noisy = field.copy()

    # pre-generate meshgrid
    X, Y = np.meshgrid(np.arange(w), np.arange(h))

    for _ in range(num_gaussians):
        # random center
        cx = np.random.uniform(0, w)
        cy = np.random.uniform(0, h)

        # Gaussian bump
        gauss = amplitude * np.exp(-((X - cx)**2 + (Y - cy)**2) / (2 * sigma**2))

        noisy += gauss

    # ensure remains in range [0,1]
    return np.clip(noisy, 0, 1)


def add_poisson_noise(field):
    vals = len(np.unique(field))
    vals = 2 ** np.ceil(np.log2(vals))
    noisy = np.random.poisson(field * vals) / float(vals)
    return np.clip(noisy, 0, 1)

def add_speckle_noise(field, var=0.04):
    noise = np.random.randn(*field.shape) * np.sqrt(var)
    return np.clip(field + field * noise, 0, 1)

def add_uniform_noise(field, low=-0.1, high=0.1):
    noise = np.random.uniform(low, high, field.shape)
    return np.clip(field + noise, 0, 1)

def add_laplace_noise(field, scale=0.05):
    noise = np.random.laplace(0, scale, field.shape)
    return np.clip(field + noise, 0, 1)





def add_perlin_noise(field, scale=10.0, amplitude=0.1):
    h, w = field.shape
    perlin = np.zeros_like(field)
    for i in range(h):
        for j in range(w):
            perlin[i, j] = pnoise2(i / scale, j / scale, repeatx=w, repeaty=h)
    perlin = (perlin - perlin.min()) / (perlin.max() - perlin.min())
    return np.clip(field + amplitude * (perlin - 0.5), 0, 1)

def apply_noise_to_scalar_field(vtk_image, noise_type='Gaussian (White)', amount=0.05):
    """
    Apply selected noise type to vtkImageData scalar field while preserving its original range.
    """
    if (noise_type == 'None'):
        return vtk_image

    # Extract numpy array from vtkImageData
    scalars = vnp.vtk_to_numpy(vtk_image.GetPointData().GetScalars())
    dims = vtk_image.GetDimensions()
    field = scalars.reshape(dims[1], dims[0]).astype(np.float32)

    # Save original range
    orig_min, orig_max = field.min(), field.max()

    # Normalize to [0,1]
    field_norm = (field - orig_min) / (orig_max - orig_min + 1e-8)

    # === Apply selected noise ===
    if noise_type == 'Salt':
        field_noisy = add_salt_noise(field_norm, amount)
    elif noise_type == 'Pepper':
        field_noisy = add_pepper_noise(field_norm, amount)
    elif noise_type == 'Salt and Pepper':
        field_noisy = add_salt_pepper_noise(field_norm, amount)
    elif noise_type == 'Gaussian (White)':
        field_noisy = add_gaussian_noise(field_norm, std=amount)
    elif noise_type == 'Gaussian blobs':
        field_noisy = add_gaussian_few_noise(field_norm, amplitude=amount)
    elif noise_type == 'Poisson':
        field_noisy = add_poisson_noise(field_norm)
    elif noise_type == 'Speckle':
        field_noisy = add_speckle_noise(field_norm, var=amount)
    elif noise_type == 'Uniform':
        field_noisy = add_uniform_noise(field_norm, -amount, amount)
    elif noise_type == 'Laplace':
        field_noisy = add_laplace_noise(field_norm, scale=amount)
    elif noise_type == 'Perlin':
        field_noisy = add_perlin_noise(field_norm, scale=20.0, amplitude=amount)
    else:
        field_noisy = field_norm  # No noise

    # === Restore original range ===
    field_restored = field_noisy * (orig_max - orig_min) + orig_min
    field_restored = np.clip(field_restored, orig_min, orig_max)

    # Convert back to vtkImageData
    flat = field_restored.ravel(order='C')
    vtk_arr = vnp.numpy_to_vtk(num_array=flat, deep=True, array_type=vtk.VTK_FLOAT)
    vtk_image.GetPointData().SetScalars(vtk_arr)
    vtk_image.Modified()

    return vtk_image
