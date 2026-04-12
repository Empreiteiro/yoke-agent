# Custom evaluation metrics

Drop Python files in this directory to add domain-specific metrics that run
alongside the built-in RAGAS metrics. Each file must expose a module-level
`metrics` dict mapping a metric name to a callable:

```python
# answer_length.py
def answer_length(row):
    ans = row.get("answer") or ""
    return min(len(ans) / 500, 1.0)

metrics = {"answer_length": answer_length}
```

Each callable receives a dict with `question`, `answer`, `contexts`, and
`ground_truth` (when available) and must return a float in `[0, 1]` or
`None` to skip the row. Exceptions inside a metric are caught and logged —
the row simply gets `None` for that metric and the experiment continues.

Files whose name starts with `_` are ignored. To use a different directory,
set the `CUSTOM_METRICS_DIR` environment variable before starting the
backend.

See `example_answer_length.py.template` and `example_keyword_coverage.py.template`
for starting points. Rename the copy you want to enable to drop the
`.template` suffix — the loader only picks up real `.py` files.
