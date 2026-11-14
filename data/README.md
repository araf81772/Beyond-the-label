# Research-only synthetic world inputs

These files contain deterministic worlds, including hidden uniform draws. They are experimental inputs, **not observed agent results**. Do not serialize a whole world or its research case envelope into a model request. Only the allowlisted deterministic renderer may construct model-visible messages.

Regenerate offline from the repository root:

```powershell
$env:PYTHONPATH = 'src'
python -m beyond_label.generate --output data
```

Pilot, smoke and main seed ranges remain separate. Each world stores two targets plus six potential distractors; load-2/load-8 selects the visible subset. The main load has not been selected because no real pilot has run. `manifest.json` hashes the generated world files. It is not an execution freeze.
