# validate-action — Busbar config validation for CI

A GitHub Action that runs `busbar --validate` on your `config.yaml` and **fails the job on any error** — the same load → resolve → validate the gateway runs at boot. Keep your Busbar config in git and this catches a bad edit before it ships.

It runs the official [`getbusbar/busbar`](https://hub.docker.com/r/getbusbar/busbar) image, so there is nothing to install and no separate binary to keep current. The provider catalog ships inside the image, so a bare `config.yaml` validates out of the box.

## Usage

```yaml
name: validate
on: [push, pull_request]
jobs:
  busbar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: GetBusbar/validate-action@v1
        with:
          config: config.yaml        # optional (default: config.yaml)
          # providers: providers.yaml # optional custom catalog; omit to use the baked-in one
          # version: "1.5.3"          # optional; pin to the version you deploy
```

A malformed config, an unknown provider/model reference, or any semantic error fails the step.

## Inputs

| Input | Default | Description |
| --- | --- | --- |
| `config` | `config.yaml` | Path to your config, relative to the repo root. |
| `providers` | *(baked-in catalog)* | Optional path to a custom `providers.yaml`. |
| `version` | `latest` | Busbar image tag. **Pin to the version you deploy** for reproducible validation; `latest` rides the newest release. |
| `secret_env` | *(none)* | Names of variables your config references as `{ env: NAME }`, whitespace or comma separated. See below. |

## If your config references secrets

From busbar **1.5.3**, `--validate` RESOLVES `env:` and `file:` secret references and fails when one
cannot resolve. That is deliberate: a gateway whose credentials are missing fails every upstream
request, and it is better to hear that before it boots than after. It does mean a config using the
recommended `{ env: NAME }` form needs that variable present when you validate.

Name the variables and set them on the step:

```yaml
      - uses: GetBusbar/validate-action@v1
        with:
          config: config.yaml
          secret_env: ANTHROPIC_KEY OPENAI_KEY
        env:
          ANTHROPIC_KEY: x
          OPENAI_KEY: x
```

**Placeholders are enough.** Validation checks that a reference RESOLVES, not that the credential
works, so `x` proves your config's shape without handing the job a real key. Use real secrets only if
you want to, and prefer placeholders in workflows that run on pull requests from forks.

Validating with the variable genuinely absent still fails, which is the point: it catches the config
that would have booted a gateway with no credentials.

## What it does

The action mounts your checked-out repo into the image and runs:

```
busbar --validate     # BUSBAR_CONFIG=<config>, BUSBAR_PROVIDERS=<providers or baked-in>
```

Exit `0` = valid (prints a one-line summary of providers/models/pools). Exit `1` = errors (prints the first error), which fails the job.

## License

Apache-2.0 © Busbar, Inc.
