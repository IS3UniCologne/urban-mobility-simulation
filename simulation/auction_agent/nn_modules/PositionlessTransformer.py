class SetTransformerBlock(nn.Module):
    def __init__(self, dim, nhead):
        super().__init__()

        self.attn = nn.MultiheadAttention(dim, nhead, batch_first=True)

        self.norm1 = nn.LayerNorm(dim)
        self.norm2 = nn.LayerNorm(dim)

        self.ff = nn.Sequential(
            nn.Linear(dim, dim * 4),
            nn.ReLU(),
            nn.Linear(dim * 4, dim),
        )

    def forward(self, x, key_padding_mask=None):
        # Self-attention (permutation equivariant)
        attn_out, _ = self.attn(
            x, x, x,
            key_padding_mask=key_padding_mask,
            need_weights=False
        )

        x = self.norm1(x + attn_out)

        ff_out = self.ff(x)
        x = self.norm2(x + ff_out)

        return x