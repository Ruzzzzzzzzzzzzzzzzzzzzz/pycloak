import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

N = 280
TRAIL = 18
DT = 0.05
FPS = 240

rng = np.random.default_rng(7)

radius0 = rng.uniform(0.15, 1.0, N)
theta0 = rng.uniform(0, 2 * np.pi, N)
omega = 0.75 / radius0
phase = rng.uniform(0, 2 * np.pi, N)
base_size = rng.uniform(2, 26, N)
base_hue = rng.uniform(0, 1, N)

cmap = plt.get_cmap('cool')
base_rgba = cmap(base_hue)

age = np.arange(TRAIL)
alpha_w = np.exp(-age / 4.5)
alpha_w /= alpha_w.max()

flat_alphas = (0.95 * alpha_w[:, None] * np.ones((TRAIL, N))).ravel()

sizes = base_size[None, :] * (0.35 + 0.65 * alpha_w[:, None])
flat_sizes = sizes.ravel()

flat_rgba = np.repeat(base_rgba[None, :, :], TRAIL, axis=0).reshape(-1, 4)
flat_rgba[:, 3] = flat_alphas

fig, ax = plt.subplots(figsize=(8, 8), facecolor='black')
fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
ax.set_facecolor('black')
ax.set_xlim(-1.45, 1.45)
ax.set_ylim(-1.45, 1.45)
ax.set_aspect('equal')
ax.axis('off')

ax.scatter([0], [0], s=260, c='white', alpha=0.25, edgecolors='none')

scat = ax.scatter(np.zeros(TRAIL * N), np.zeros(TRAIL * N),
                  s=flat_sizes, facecolors=flat_rgba, edgecolors='none')


def update(frame):
    t = frame * DT
    tt = t - age * DT

    theta = theta0[None, :] + omega[None, :] * tt[:, None]
    r = radius0[None, :] * (1 + 0.10 * np.sin(1.7 * tt[:, None] + phase[None, :]))

    x = (r * np.cos(theta)).ravel()
    y = (r * np.sin(theta)).ravel()
    scat.set_offsets(np.column_stack([x, y]))
    return (scat,)


anim = FuncAnimation(fig, update, frames=None, interval=1000 / FPS,
                     blit=True, cache_frame_data=False)

plt.show()