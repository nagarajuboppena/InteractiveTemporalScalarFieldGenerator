import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from collections import defaultdict

def plot_tracking_timeline(events):
    """
    Plot timeline showing birth, continuation, and merge events.
    Timesteps and cluster IDs are automatically extracted.

    Args:
        events (list of dict): List of events, each with:
            {"type": "birth", "id": int, "time": float/int}
            or {"type": "merge", "sources": [..], "target": [..], "time": float/int}
    """

    # 1️⃣ Extract all unique timesteps and cluster IDs
    timesteps = sorted({e["time"] for e in events})
    cluster_ids = set()
    for e in events:
        if e["type"] == "birth":
            cluster_ids.add(e["id"])
        elif e["type"] == "merge":
            cluster_ids.update(e["sources"])
            cluster_ids.update(e["target"])
    cluster_ids = sorted(cluster_ids)

    # 2️⃣ Sort events chronologically and group by time
    events.sort(key=lambda e: e["time"])
    events_by_time = defaultdict(list)
    for e in events:
        events_by_time[e["time"]].append(e)

    # 3️⃣ Tracking state variables
    alive_clusters = set()      # clusters currently active
    last_time = {}              # last plotted time for each cluster
    cluster_colors = {}         # color map for consistent IDs
    color_map = plt.cm.get_cmap("tab10")
    color_index = 0

    # Store arrows for merges
    merge_arrows = []

    # 4️⃣ Setup plotting
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_title("Feature Tracking Timeline (Birth, Continuation, Merge)")
    ax.set_xlabel("Time")
    ax.set_ylabel("Cluster ID")

    # 5️⃣ Iterate through timesteps
    for t in timesteps:
        to_remove = set()  # sources to remove after plotting this timestep

        # --- Handle events at this timestep ---
        if t in events_by_time:
            for e in events_by_time[t]:
                if e["type"] == "birth":
                    cid = e["id"]
                    alive_clusters.add(cid)
                    if cid not in cluster_colors:
                        cluster_colors[cid] = color_map(color_index % 10)
                        color_index += 1
                    last_time[cid] = t  # start new cluster

                elif e["type"] == "merge":
                    sources = e["sources"]
                    targets = e["target"]

                    # Register arrows for visualization

                    print('sources:',sources)
                    print('targets:',targets)
                    for sid in sources:
                        for tid in targets:
                            merge_arrows.append((t, sid, tid))

                    # Ensure all sources/targets exist in alive set
                    for sid in sources:
                        alive_clusters.add(sid)
                        if sid not in cluster_colors:
                            cluster_colors[sid] = color_map(color_index % 10)
                            color_index += 1

                    for tid in targets:
                        alive_clusters.add(tid)
                        if tid not in cluster_colors:
                            cluster_colors[tid] = color_map(color_index % 10)
                            color_index += 1

                    # Defer removal of sources until after circles & arrows are drawn
                    to_remove.update(sources)

        # --- Draw circles & lines for all currently alive clusters ---
        for cid in sorted(alive_clusters):
            color = cluster_colors[cid]

            # Draw continuation line if cluster existed before
            if cid in last_time and last_time[cid] != t:
                ax.plot([last_time[cid], t], [cid, cid],
                        color=color, linewidth=2, alpha=0.7)

            # Draw circle at current time
            ax.scatter(t, cid, s=100, color=color,
                       edgecolor="black", zorder=3)

            last_time[cid] = t

        # --- Draw merge arrows (same timestep) ---
        for (mt, sid, tid) in [a for a in merge_arrows if a[0] == t]:
            if sid in last_time and tid in last_time:
                ax.annotate("",
                            xy=(t, tid), xytext=(t, sid),
                            arrowprops=dict(arrowstyle="->", lw=1.6,
                                            color="gray", alpha=0.8,
                                            shrinkA=6, shrinkB=6))

        # --- Now safe to remove merged sources after plotting ---
        for rid in to_remove:
            if rid in alive_clusters:
                alive_clusters.remove(rid)

    # 6️⃣ Final formatting
    ax.grid(True, linestyle="--", alpha=0.3)
    ax.legend(
        handles=[
            mpatches.Patch(color='white', label='● Circles: Alive Clusters'),
            mpatches.Patch(color='white', label='— Lines: Continuations'),
            mpatches.Patch(color='white', label='→ Arrows: Merges')
        ],
        loc="upper left", frameon=False
    )

    # ✅ Y-axis = discrete cluster IDs only
    ax.set_yticks(cluster_ids)
    ax.set_yticklabels([str(cid) for cid in cluster_ids])

    # ✅ X-axis = discrete time steps
    ax.set_xticks(timesteps)

    plt.tight_layout()
    plt.show()


# ---------------- Example Usage ----------------
if __name__ == "__main__":
    events = [
        {"type": "birth", "id": 1, "time": 0},
        {"type": "birth", "id": 2, "time": 1},
        {"type": "birth", "id": 3, "time": 2},
        {"type": "merge", "sources": [1, 2], "target": [4], "time": 3},
        {"type": "birth", "id": 5, "time": 4},
        {"type": "merge", "sources": [4, 3], "target": [6], "time": 5},
    ]

    plot_tracking_timeline(events)