from __future__ import annotations

import torch
import torch.nn.functional as F

from ..core.config import LOSS_RANKING, LOSS_REGRESSION, LOSS_SAFETY, RANK_MARGIN, SAFETY_FLOOR


def regression_loss(pred: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
    return F.smooth_l1_loss(pred, target)


def pairwise_ranking_loss(pred: torch.Tensor, target: torch.Tensor, margin: float = RANK_MARGIN, max_pairs: int = 2048) -> torch.Tensor:
    if pred.numel() < 2:
        return pred.sum() * 0.0
    n = pred.numel()
    if n > 128:
        idx = torch.randperm(n, device=pred.device)[: min(n, max_pairs * 2)]
        pred, target = pred[idx], target[idx]
        n = pred.numel()
    i = torch.randint(0, n, (max_pairs,), device=pred.device)
    j = torch.randint(0, n, (max_pairs,), device=pred.device)
    mask = target[i] != target[j]
    if not mask.any():
        return pred.sum() * 0.0
    i, j = i[mask], j[mask]
    ti, tj = target[i], target[j]
    pi, pj = pred[i], pred[j]
    pos = ti > tj
    if pos.any():
        loss_pos = F.margin_ranking_loss(pi[pos], pj[pos], torch.ones(pos.sum(), device=pred.device), margin=margin)
    else:
        loss_pos = 0.0
    neg = ti < tj
    if neg.any():
        loss_neg = F.margin_ranking_loss(pj[neg], pi[neg], torch.ones(neg.sum(), device=pred.device), margin=margin)
    else:
        loss_neg = 0.0
    if isinstance(loss_pos, float) and isinstance(loss_neg, float):
        return pred.sum() * 0.0
    if isinstance(loss_pos, float):
        return loss_neg
    if isinstance(loss_neg, float):
        return loss_pos
    return 0.5 * (loss_pos + loss_neg)


def safety_loss(pred: torch.Tensor, safety_mask: torch.Tensor, floor: float = SAFETY_FLOOR) -> torch.Tensor:
    if safety_mask is None or not safety_mask.any():
        return pred.sum() * 0.0
    masked = pred[safety_mask]
    return F.relu(floor - masked).mean()


def total_loss(pred, target, safety_mask=None, weights=(LOSS_REGRESSION, LOSS_RANKING, LOSS_SAFETY)):
    w_reg, w_rank, w_safe = weights
    loss = 0.0
    if w_reg:
        loss = loss + w_reg * regression_loss(pred, target)
    if w_rank:
        loss = loss + w_rank * pairwise_ranking_loss(pred, target)
    if w_safe and safety_mask is not None:
        loss = loss + w_safe * safety_loss(pred, safety_mask)
    return loss
