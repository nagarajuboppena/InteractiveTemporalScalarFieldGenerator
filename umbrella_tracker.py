#!/usr/bin/env python3
"""
umbrella_clustering.py
Performs umbrella clustering on GaussianScene gaussians, computes
cluster correspondences between consecutive timesteps (rooted by Gaussian IDs),
and detects birth/merge events for visualization.
"""

import os
import json
import math
import numpy as np
from vtk.util import numpy_support as vnp


# ---------------------------------------------------------
# Umbrella clustering with Gaussian-ID roots
# ---------------------------------------------------------
def umbrella_clusters_with_roots(gaussians):
    """
    Compute umbrella clusters using max-field (umbrella) criterion.
    Returns:
        clusters_dict: { root_gaussian_id : [gaussian_ids] }
        clusters_list: [[gaussian_ids], ...]
    """
    n = len(gaussians)
    if n == 0:
        return {}, []

    ids = [g['id'] for g in gaussians]
    xs = np.array([g['x'] for g in gaussians])
    ys = np.array([g['y'] for g in gaussians])
    amps = np.array([g['amp'] for g in gaussians])
    vars_ = np.array([g['var'] for g in gaussians])

    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # umbrella merge criterion
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            dx = xs[i] - xs[j]
            dy = ys[i] - ys[j]
            dist2 = dx * dx + dy * dy
            rhs = amps[j] * math.exp(-dist2 / (2.0 * vars_[j]))
            if amps[i] <= rhs:
                union(i, j)

    clusters = {}
    for idx in range(n):
        root_idx = find(idx)
        root_id = ids[root_idx]  # use Gaussian ID as cluster root
        clusters.setdefault(root_id, []).append(ids[idx])

    return clusters, list(clusters.values())


# ---------------------------------------------------------
# Correspondence matrix with root IDs
# ---------------------------------------------------------
def correspondence_matrix_with_roots(prev_clusters, curr_clusters):
    prev_roots = list(prev_clusters.keys())
    curr_roots = list(curr_clusters.keys())
    M = np.zeros((len(prev_roots), len(curr_roots)), dtype=int)

    for i, r_prev in enumerate(prev_roots):
        prev_ids = set(prev_clusters[r_prev])
        for j, r_curr in enumerate(curr_roots):
            curr_ids = set(curr_clusters[r_curr])
            if prev_ids & curr_ids:
                M[i, j] = 1

    return M, prev_roots, curr_roots


# ---------------------------------------------------------
# Event detection (births, merges)
# ---------------------------------------------------------
def detect_events(timesteps, clusters_history):
    """
    Detects cluster-level birth and merge events across timesteps.
    Returns list of event dicts.
    """
    events = []
    alive_clusters = set()

    for i, clusters in enumerate(clusters_history):
        t = timesteps[i]
        curr_roots = set(clusters.keys())

        # --- Births ---
        new_clusters = curr_roots - alive_clusters
        for c in new_clusters:
            events.append({"type": "birth", "root": c, "time": t,"id": c})
        alive_clusters |= new_clusters

        # --- Merges ---
        if i == 0:
            continue
        prev_clusters = clusters_history[i - 1]
        prev_roots = list(prev_clusters.keys())

        # map each Gaussian ID to its previous root
        prev_owner = {}
        for r, members in prev_clusters.items():
            for gid in members:
                prev_owner[gid] = r

        for r_curr, members in clusters.items():
            prev_sources = {prev_owner[g] for g in members if g in prev_owner}
            prev_sources.discard(None)
            if len(prev_sources) > 1:
                events.append({
                    "type": "merge",
                    "sources": sorted(prev_sources),
                    "target": r_curr,
                    "time": t
                })
                # Mark merged clusters as dead
                alive_clusters -= prev_sources
                alive_clusters.add(r_curr)

    return events

def detect_events_from_correspondence_matrix(M, prev_roots, curr_roots,time):
    """
    Detect birth and merge events directly from the correspondence matrix.

    Args:
        M (np.ndarray): Correspondence matrix (rows = prev roots, cols = curr roots)
        prev_roots (list): Root Gaussian IDs at previous timestep
        curr_roots (list): Root Gaussian IDs at current timestep

    Returns:
        events (list of dict): Each event is {'type': ..., 'sources': ..., 'target': ..., 'time': ... (optional)}
        births (list): List of root IDs that are newly born
    """

    events = []
    births = []

    # --- Births ---
    # Any current root not appearing in prev_roots is a new cluster
    new_roots = [r for r in curr_roots if r not in prev_roots]
    for r in new_roots:
        births.append(r)
        events.append({
            "time": time,
            "type": "birth",
            "target": [r],
            "id": r,
            "sources": [],
        })
        print(f"Detected birth of cluster {r}")

    # --- Merges ---
    # Any column (curr cluster) having >1 connection → merge
    for j, curr_root in enumerate(curr_roots):
        contributing = np.where(M[:, j] == 1)[0]
        if len(contributing) > 1:
            merged_sources = [prev_roots[i] for i in contributing]
            events.append({
                "time": time,
                "type": "merge",
                "target": [curr_root],
                "sources": merged_sources,
            })
            print(f"Detected merge into cluster {curr_root} from sources {merged_sources}")

    return events, births


# ---------------------------------------------------------
# VTK to numpy helper
# ---------------------------------------------------------
def vtk_image_to_numpy(img):
    dims = img.GetDimensions()
    w, h = dims[0], dims[1]
    scalars = img.GetPointData().GetScalars()
    arr = vnp.vtk_to_numpy(scalars)
    arr = arr.reshape((h, w))
    return arr


import os
import json
import numpy as np

def update_umbrella_tracking(scene, output_dir="umbrella_output", timestep=0):
    """
    Perform umbrella clustering for the current timestep.
    Keeps previous clusters stored inside the scene object
    (scene._prev_clusters) for next-time correspondence.
    """

    # --- Ensure output folder exists ---
    os.makedirs(output_dir, exist_ok=True)

    # --- Extract Gaussian parameters ---
    gaussians = scene.gaussians
    gcopy = [{
        'id': g['id'],
        'x': float(g['x']),
        'y': float(g['y']),
        'amp': float(g.get('amp', 1.0)),
        'var': float(g.get('var', 1.0))
    } for g in gaussians]

    # --- Compute current umbrella clusters ---
    clusters_dict, _ = umbrella_clusters_with_roots(gcopy)

    # --- Retrieve previous clusters from scene (if any) ---
    prev_clusters = getattr(scene, "_prev_clusters", None)

    # --- Compute correspondence matrix ---
    if prev_clusters is not None:
        C, prev_root_ids, curr_root_ids = correspondence_matrix_with_roots(prev_clusters, clusters_dict)
        events_detected, births = detect_events_from_correspondence_matrix(C, prev_root_ids, curr_root_ids,timestep)        
        for e in events_detected:
            print(f"[Umbrella] Detected event at t={timestep}: {e}")
    else:
        C = np.zeros((0, len(clusters_dict)))
        prev_root_ids, curr_root_ids = [], list(clusters_dict.keys())
        events_detected, births = [], list(clusters_dict.keys())  # first frame = all births
    
        for id in curr_root_ids:
            events_detected.append({"type": "birth", "root": id, "time": timestep,"id": id})

    # --- Save or print results ---
    meta = {
        'timestep': timestep,
        'clusters': {str(k): v for k, v in clusters_dict.items()},
        'correspondence_matrix': C.tolist(),
        'prev_root_ids': prev_root_ids,
        'curr_root_ids': curr_root_ids,
        #'events': events
    }
    json_path = os.path.join(output_dir, f"clusters_t{timestep:04d}.json")
    with open(json_path, 'w') as f:
        json.dump(meta, f, indent=2)

    #print(f"[Umbrella] t={timestep}: clusters={list(clusters_dict.values())}")
    #for ev in events:
    #    print("  ", ev)

    # --- Store current clusters for next timestep ---
    scene._prev_clusters = clusters_dict

    #return clusters_dict, C, events
    return events_detected