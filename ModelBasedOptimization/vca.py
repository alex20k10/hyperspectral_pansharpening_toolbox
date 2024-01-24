import torch
import math
import torch.nn.functional as F


def vca(R, p=0, snr_input=False, verbose='off'):
    """
    Vertex Component Analysis Algorithm [VCA]

    Args:
    R (torch.Tensor): Input matrix with dimensions L(channels) x N(pixels).
    p (int): Number of endmembers in the scene.
    snr_input (bool): Whether to use user input SNR or estimate it.
    verbose (str): Verbose mode, 'on' or 'off'.

    Returns:
    Ae (torch.Tensor): Estimated mixing matrix (endmembers signatures).
    index (torch.Tensor): Pixels chosen to be the most pure.
    Rp (torch.Tensor): Data R projected on the identified signal subspace.
    """

    # Default parameters
    if p == 0:
        p = R.shape[0]
    snr = 0

    # Initializations
    L, N = R.shape
    if (p <= 0 or p > L or p != int(p)):
        raise ValueError("ENDMEMBER parameter must be an integer between 1 and L")

    if (L - p < p) and not snr_input:
        if verbose == 'on':
            print("I can not estimate SNR [(no bands)-p < p]")
            print("I will apply the projective projection")
        snr_input = True
        snr = 100

    # Compute mean, correlation, and the p-orth basis
    r_m = torch.mean(R, dim=1)
    Corr = torch.mm(R, R.t()) / N
    Ud, Sd, _ = torch.linalg.svd(Corr)
    Ud = Ud[:, :p]

    if not snr_input:
        # Estimate SNR
        Pt = torch.trace(Corr)
        Pp = torch.sum(Sd[:p])
        Pn = (Pt - Pp) / (1 - p / L)
        if Pn > 0:
            snr = 10 * torch.log10(Pp / Pn)
            if verbose == 'on':
                print(f'SNR estimated = {snr.item():.2f} [dB]')
        else:
            snr = 0
            if verbose == 'on':
                print('Input data belongs to a p-subspace')

    # SNR threshold to decide the projection
    SNR_th = 15 + 10 * math.log10(p)

    if snr < SNR_th:
        if verbose == 'on':
            print('Select proj. on the to (p-1) subspace.')
            print('I will apply the projective projection')

        d = p - 1
        Cov = Corr - torch.outer(r_m, r_m)
        Ud, Sd, _ = torch.svd(Cov)
        Ud = Ud[:, :d]
        R_o = R - r_m.view(-1, 1)
        x_p = -Ud.t() @  R_o

        if d > x_p.shape[0]:
            Rp = torch.mm(Ud, x_p) + r_m.view(-1, 1)
        else:
            Rp = torch.mm(Ud, x_p[:d]) + r_m.view(-1, 1)

        cos_angles = torch.sum(Rp * R, dim=0) / (torch.norm(Rp, dim=0) * torch.norm(R, dim=0))
        c = torch.norm(x_p, dim=0).max()
        y = torch.cat([x_p, c * torch.ones(1, N)], dim=0)
    else:
        if verbose == 'on':
            print('... Select the projective proj. (dpft)')

        d = p
        x_p = torch.mm(Ud.t(), R)
        Rp = torch.mm(Ud, x_p[:d])
        u = torch.mean(x_p, dim=1) * p
        scale = torch.sum(x_p * u.view(-1, 1), dim=0)
        th = 0.01
        mask = scale < th
        scale = scale * (~mask) + mask.float()
        y = x_p / scale

        pt_errors = torch.nonzero(mask).squeeze()
        u_norm = torch.norm(u)
        y[:, pt_errors] = (u / (u_norm ** 2)).unsqueeze(1).repeat(1, len(pt_errors))

    # VCA algorithm
    p = y.shape[0]
    index = torch.zeros(p, dtype=torch.long)
    A = torch.zeros((p, p), dtype=R.dtype, device=R.device)
    A[-1, 0] = 1

    for i in range(p):
        w = torch.rand(p, dtype=R.dtype, device=R.device)
        f = w - A @ torch.pinverse(A) @  w
        f = f / torch.norm(f)
        v = torch.mm(f[None, :], y)
        v_max, index[i] = torch.max(torch.abs(v), dim=1)
        A[:, i] = y[:, index[i]]

    Ae = Rp[:, index]

    return Ae, index, Rp


# Example usage
if __name__ == "__main__":
    # Create a sample R matrix (replace with your actual data)
    L = 6  # Number of bands (channels)
    N = 100  # Number of pixels
    R = torch.rand(L, N)

    # Call the vca function
    Ae, indice, Rp = vca(R, p=3, snr_input=False, verbose='on')

    # Print the results
    print("Estimated Mixing Matrix (Ae):")
    print(Ae)
    print("Indices of Most Pure Pixels:")
    print(indice)
    print("Data R Projected on Signal Subspace (Rp):")
    print(Rp)