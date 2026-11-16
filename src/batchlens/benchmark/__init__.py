"""The benchmark: the findings scored against the generator's ground truth over many seeded
batches (``batchlens benchmark``, docs/verification-report.md).

This package reads the ground truth, which ``calc`` and ``analysis`` never do: it is the
examiner, not the analysis. Nothing here is served by the API or stored.
"""
