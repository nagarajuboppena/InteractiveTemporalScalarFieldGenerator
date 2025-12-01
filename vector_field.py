#!/usr/bin/env python3
"""
vector_field.py

Contains the VectorFieldGenerator class for creating a 2D vector field.
Generates a vtkImageData object with vector components for visualization.

Dependencies:
- VTK
- math
"""

import math
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkCommonCore import vtkDoubleArray

class VectorFieldGenerator:
    """
    Generates a 2D vector field stored as vtkImageData with 3-component vectors.
    """
    @staticmethod
    def create_vector_field(width=20, height=20, spacing=1.0,field_type="Circular"):
        """
        Create a 2D vector field with a circular pattern around the center.

        Args:
            width (int): Grid width (default: 20).
            height (int): Grid height (default: 20).
            spacing (float): Grid spacing (default: 1.0).

        Returns:
            vtkImageData: Image data with vector components.
        """
        img = vtkImageData()
        img.SetDimensions(width, height, 1)
        img.SetOrigin(0, 0, 0)
        img.SetSpacing(spacing, spacing, 1)

        vecs = vtkDoubleArray()
        vecs.SetNumberOfComponents(3)
        vecs.SetNumberOfTuples(width * height)
        vecs.SetName('Vectors')

        cx = (width - 1) * spacing / 2.0
        cy = (height - 1) * spacing / 2.0

        for j in range(height):
            for i in range(width):

                x = i*spacing
                y = j*spacing

                dx = x-cx
                dy = y-cy

                if field_type == "Circular":
                    vx = -dy
                    vy = dx
                elif field_type == "Sink":
                    vx = -dx
                    vy = -dy
                elif field_type == "Source":
                    vx = dx
                    vy = dy
                elif field_type == "Saddle":
                    vx = dx
                    vy = -dy
                else:
                    vx, vy = 0.0, 0.0


                mag = math.sqrt(vx * vx + vy * vy) + 1e-6
                s = 1.0 / (1.0 + 0.1 * math.sqrt(dx * dx + dy * dy))
                vecs.SetTuple3(j * width + i, s * vx / mag, s * vy / mag, 0.0)

        img.GetPointData().SetVectors(vecs)
        return img
