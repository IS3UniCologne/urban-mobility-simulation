import torch
import torch.nn as nn
import torch.nn.functional as F

class BiasedCrossAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads
        
        assert self.head_dim * num_heads == embed_dim, "embed_dim must be divisible by num_heads"

        # Projection matrices
        self.q_proj = nn.Linear(embed_dim, embed_dim)
        self.k_proj = nn.Linear(embed_dim, embed_dim)
        self.v_proj = nn.Linear(embed_dim, embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)

    def forward(self, query, key, value, attn_bias=None, key_padding_mask=None):

        B, V_len, _ = query.shape
        _, Target_len, _ = key.shape

        # 1. Project and split into multi-heads
        # Shape trace: (B, L, d) -> (B, L, H, d_h) -> (B, H, L, d_h)
        q = self.q_proj(query).view(B, V_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(B, Target_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(B, Target_len, self.num_heads, self.head_dim).transpose(1, 2)

        # 2. Compute raw attention scores: (B, H, V_len, Target_len)
        scaling = 1.0 / (self.head_dim ** 0.5)
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) * scaling

        # 3. Inject the distance bias matrix
        if attn_bias is not None:
            # attn_bias shape must be: (B, H, V_len, Target_len)
            attn_scores = attn_scores + attn_bias

        # --- NEW: Apply Key Padding Mask ---
        if key_padding_mask is not None:
            # Expected shape for key_padding_mask: (B, Target_len)
            # True indicates padded tokens that need to be masked out.
            # Broadcast to match attn_scores shape: (B, 1, 1, Target_len)
            mask = key_padding_mask.unsqueeze(1).unsqueeze(2)
            attn_scores = attn_scores.masked_fill(mask, float('-inf'))

        # 4. Softmax and Attention Weighting
        attn_weights = F.softmax(attn_scores, dim=-1)
        attn_weights = torch.nan_to_num(attn_weights, nan=0.0)
        context = torch.matmul(attn_weights, v) # (B, H, V_len, d_h)

        # 5. Concatenate heads and project out
        context = context.transpose(1, 2).contiguous().view(B, V_len, self.embed_dim)
        return self.out_proj(context)