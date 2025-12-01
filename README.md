# Scalar Field Generation and Feature Tracking Toolkit

This project provides tools to **generate, visualize, and analyze 2D scalar fields** using a variety of mathematical distributions. It also includes interactive visualization using **VTK** and a GUI built with **PyQt5**.

The system allows users to:

* Generate scalar fields using Gaussian, Cauchy, Mexican Hat, Exponential Decay, and other custom functions.
* Add multiple noise models including Gaussian noise, salt-and-pepper noise,  Gaussian White noise and Gaussian blobs noise.
* Visualize scalar fields, contour lines, and vector fields.
* Track Gaussian features over time.

---

## 📌 Features

### **1. Scalar Field Generators**

The following 2D distributions are supported:

* **Gaussian**
* **Cauchy (Lorentzian)**
* **Mexican Hat (Laplacian of Gaussian)**
* **Exponential Decay**
* **Anisotropic Gaussian**

Each distribution can be placed at arbitrary positions with configurable:

* Amplitude
* Variance / scale
* Orientation

---

### **2. Noise Models**

You can apply noise to scalar fields:

* Gaussian (white) noise
* Salt noise
* Pepper noise
* Salt-and-pepper noise
* Gaussian White noise
* **Gaussian-Few Noise** (multiple small Gaussian bumps)

---


### **4. GUI (PyQt5)**

Includes:

* List of Gaussian sources
* Controls to add/remove/modify distributions
* Buttons to generate fields and apply noise
* Real-time visualization updates

---

## 📦 Dependencies

Install the following Python packages:

```
Python 3.8+
PyQt5
VTK
numpy
math
```

Install with pip:

```bash
pip install PyQt5 vtk numpy noise
```

---

## ▶️ How to Run the Application

### **1. Clone the Repository**

```bash
git clone https://github.com/yourusername/your-repo.git
cd your-repo
```

### **2. Install Dependencies**


### **3. Run the Application**

```bash
python main.py
```



## 🎯 Real‑World Applications

This toolkit can simulate real patterns seen in:

* **Ocean eddies** (Gaussian-like extrema)
* **Weather systems** (pressure highs/lows)
* **Diffusion phenomena** (Gaussian)
* **Signal processing / edge detection** (Mexican-Hat)
* **Nuclear/chemical decay** (exponential)
* **Spectral line analysis** (Cauchy)
* **Multiple interacting sources** (superposition of peaks)

This makes the project useful for:

* Visualization research
* Feature tracking experiments
* Synthetic dataset generation
* Scalar field topology studies

---

## Authors:
Boppena Nagaraju
Akshay B M

## 🙏 Acknowledgements

This work was developed as part of a project under the guidance of **Prof. Vijay Natarajan**, IISc Bangalore.

We thank him for the opportunity, feedback, and support.

---

## ❓ Questions

Feel free to raise issues or contribute on GitHub!

---
