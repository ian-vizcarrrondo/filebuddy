"""Drop-in replacement for torchmcubes.marching_cubes using scikit-image.
Returns vertices in torchmcubes order (x = last axis), which TripoSR then
re-orders with v[..., [2, 1, 0]]."""
import numpy as np
import torch


def marching_cubes(vol, thresh):
    from skimage import measure

    v = vol.detach().float().cpu().numpy()
    verts, faces, _, _ = measure.marching_cubes(v, level=float(thresh))
    verts = np.ascontiguousarray(verts[:, ::-1])           # (i,j,k) -> (k,j,i)
    faces = np.ascontiguousarray(faces)
    return (torch.from_numpy(verts.astype(np.float32)),
            torch.from_numpy(faces.astype(np.int64)))
