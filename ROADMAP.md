# Roadmap

Notes on planned ideas and improvements. Not commitments — just
things worth doing.

## Ideas

### Explicit project root in the config

`[ignore]` globs are matched relative to pytest's `rootdir`, so they can break
when pytest resolves a different rootdir. Let `boundaries.toml` set `root` to keep matching stable.
