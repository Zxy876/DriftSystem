# Ideal City Mods Directory

Clone or extract modular content packs here. Each mod must live in its own
subdirectory with a manifest file named `mod.json`. The helper script
`python tools/sync_mods.py` copies these directories into the running server
(`server/idealcity_mods/` by default), calls the backend to refresh manifests,
and prints the pending build plan queue so operators can execute the steps.

Example layout:

```
mods/
  idealcity.core/
    mod.json
    schematics/
      plaza_entrance.nbt
    scripts/
      welcome.groovy
```

## `mod.json` schema

```json
{
  "mod_id": "idealcity.core",
  "name": "Core Civic Library",
  "version": "1.0.0",
  "description": "Baseline civic structures and scripts for Ideal City.",
  "authors": ["Ideal City Archives"],
  "tags": ["structure", "civic"],
  "assets": {
    "schematics": ["schematics/plaza_entrance.nbt"],
    "structures": [],
    "scripts": ["scripts/welcome.groovy"],
    "textures": []
  },
  "entry_points": {
    "build": "scripts/welcome.groovy"
  },
  "metadata": {
    "website": "https://example.com/mod"
  }
}
```

The backend loads manifests automatically and makes them available to the
build plan scheduler. Invalid manifests or directories without a `mod.json`
file are ignored. Restarting the backend or calling the `/ideal-city/mods`
endpoint refreshes the manifest cache.
