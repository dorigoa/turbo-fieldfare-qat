# Purpose


Build the [TurboFieldfare](https://github.com/drumih/turbo-fieldfare) Mac app
from upstream, pinned to a Gemma 4 26B-A4B checkpoint of your choice instead of
the one hard-coded upstream, and install the bundle into `/Applications`.

Two checkpoints are available:

| Key       | Hugging Face repo                            | Notes                                                        |
|-----------|----------------------------------------------|--------------------------------------------------------------|
| `4bit`    | `mlx-community/gemma-4-26b-a4b-it-4bit`      | upstream default                                             |
| `qat4bit` | `mlx-community/gemma-4-26B-A4B-it-qat-4bit`  | quantization-aware trained; router and shared expert at 8-bit |

QAT (quantization-aware training) is supposed to be a little more accurate
than plain post-training 4-bit quantization at the same size.

# Requirements

- macOS 26 or later and a Swift 6.2 toolchain (Xcode), as upstream requires.
- SSH access to GitHub: `makeall.sh` clones with `git@github.com:`.
- Python 3 (standard library only) for `patch_model.py`.
- About 15 GB of download on first app launch, plus roughly the same on disk
  for the installed model.

# Instructions

```
git clone git@github.com:dorigoa/turbo-fieldfare-qat.git
cd turbo-fieldfare-qat
./makeall.sh qat4bit        # or: ./makeall.sh 4bit
```

The argument is mandatory and must be one of the keys above. `makeall.sh`
then:

1. Deletes any existing `turbo-fieldfare/` directory and clones upstream
   fresh into it.
2. Runs `./patch_model.py --root turbo-fieldfare <key>`, which rewrites the
   pinned checkpoint (repo ID, revision, SHA-256 of
   `model.safetensors.index.json`, download and install byte counts) in three
   Swift files under `turbo-fieldfare/Sources/`:
   `SupportedModelSource.swift`, `AppModelInstallDescriptor.swift` and
   `VisionPackWriter.swift`.
3. Copies `build-app.sh` into `turbo-fieldfare/Scratch/` and runs it with
   `--install`: release build of `TurboFieldfareMac` and
   `TurboFieldfareDecodeService`, bundle assembled in
   `turbo-fieldfare/build/TurboFieldfare.app`, then copied to
   `/Applications/TurboFieldfare.app`, replacing any previous one.

On first launch the app downloads and installs the pinned checkpoint into
`~/Library/Application Support/TurboFieldfare/gemma4.gturbo`. When you switch
to a build pinned to another checkpoint, delete that directory first: the app
does not reuse an install made from a different checkpoint.

# Working on the checkout by hand

`makeall.sh` always re-clones and rebuilds from scratch. To re-pin or rebuild
an existing `turbo-fieldfare/` checkout without re-cloning:

```
./patch_model.py --root turbo-fieldfare --status      # what the checkout pins now
./patch_model.py --root turbo-fieldfare qat4bit       # re-pin (or 4bit)
turbo-fieldfare/Scratch/build-app.sh --install        # rebuild and reinstall
```

`patch_model.py <key> --model-dir DIR` additionally makes the app install into
and load from `DIR` instead of its default location. See the docstring at the
top of `patch_model.py` for all options.

# Adding another checkpoint

`./patch_model.py --probe <repo>` prints a ready-made `MODELS` entry for any
Hugging Face repo, reading only the index, `config.json` and the safetensors
headers. Paste it into the `MODELS` table of `patch_model.py`, give it a key,
and add the key to the `case` list in `makeall.sh`.

Only 4-bit checkpoints work: MLX affine, group size 64, base 4-bit, with an
8-bit router; the shared expert may be 4- or 8-bit. The runtime's Metal
kernels decode 4-bit weights for embeddings, attention, routed experts and the
LM head, and the manifest validator enforces exactly that mix when the model is
loaded. A 5-, 6- or 8-bit checkpoint downloads and installs fine, then the app
stops with `configuration invalid: completed install did not pass metadata
validation`. Supporting those would mean writing new kernels, not patching
constants, which is why they are not offered here.

# Files

- `makeall.sh`: clone, patch, build, install (see above).
- `patch_model.py`: pins a checkpoint in a checkout; `--status`, `--probe`,
  `--model-dir`.
- `build-app.sh`: assembles `TurboFieldfare.app` from the release build; run
  from `turbo-fieldfare/Scratch/`.
- `patch.sh`: legacy sed-based patcher, superseded by `patch_model.py` and no
  longer called by `makeall.sh`.
- `model_pins.json`: values recorded for the QAT pin; not read by any script.
- `test.sh`, `check_markdown_links.rb`: copies of upstream helpers.
