#!/usr/bin/env python3
"""Pin a different Hugging Face checkpoint in Sources/.

TurboFieldfare hard-codes one MLX checkpoint: its repo ID, git revision, the
SHA-256 of model.safetensors.index.json and the download/install byte counts.
They live in three Swift files (see PATCHES). This script rewrites them so the
installer, the Mac app and the vision-pack writer point at another entry of
the MODELS table.

    cd /path/to/turbo-fieldfare               # the checkout that contains Sources/
    python3 patch_model.py 8bit               # pin the 8-bit checkpoint
    python3 patch_model.py 4bit               # back to the shipped default
    python3 patch_model.py --status           # what the checkout pins right now
    python3 patch_model.py 8bit --model-dir ~/Models/gemma4-8bit.gturbo
                                              # ...and make the Mac app use that directory
    python3 patch_model.py --probe mlx-community/gemma-4-26b-a4b-it-6bit
                                              # print a MODELS entry for any repo

The checkout is the current directory; --root DIR selects another one, so the
script can live anywhere:

    python3 ~/bin/patch_model.py --root ~/GIT/turbo-fieldfare 8bit

--model-dir DIR is optional. It makes the Mac app install into and load from
DIR (the .gturbo directory itself; settings, history and the image companion
go beside it). Without it the app keeps its own default location, so a run
without --model-dir also undoes an earlier one. The CLI and the server take
the directory on their command line (--output, --model) and are not affected.

Plugging in another Gemma 4 checkpoint: run --probe on its repo, paste the
printed block into MODELS, give it a name.

Scope: only the pinned identity moves. The Metal kernels decode 4-bit weights
(router and shared expert also have 8-bit paths) and the repacker and manifest
validators enforce that. After patching, the installer accepts the new
checkpoint, but the runtime will not load a 5/6/8-bit model until kernels
exist. The 4-bit assumptions live in:
  Sources/TurboFieldfareRepack/Core/Planning/RepackPlanner.swift
      logicalShape (32 / bits is wrong for 5 and 6), vision companion guards
  Sources/TurboFieldfare/Infrastructure/ModelIO/ManifestReader.swift
      validateQuant, allowed bits per slot
  Sources/TurboFieldfare/Runtime/Inference/Model.swift
      affineSizes, 4 or 8 only
  Sources/TurboFieldfareFormat/GTurboVisionFormatV1.swift
      vision weightBits == 4
  Sources/TurboFieldfare/Kernels/**/*Int4*.swift, Sources/TurboFieldfare/Metal/**/*.metal
Tests/TurboFieldfareApp/Core/Installation/AppModelInstallTests.swift pins the
4-bit constants and fails while another model is patched in.
"""

import argparse
import hashlib
import json
import os
import re
import struct
import sys
import urllib.request
from pathlib import Path

# ---------------------------------------------------------------------------
# Models. Every value comes from `--probe <repo>`; "4bit" is what the
# repository ships with. Add an entry here to plug in another checkpoint.
# ---------------------------------------------------------------------------

MODELS = {
    "4bit": {
        "display_name": "Gemma 4 26B-A4B IT 4-bit",
        "repo_id": "mlx-community/gemma-4-26b-a4b-it-4bit",
        "revision": "0d77464eeb233a2da68ebf9d7dc4edaac7db956d",
        "index_sha256": "bf198c9f5ea6462addca1966e5dd669c407537a876e82cf06db9084c5c850b13",
        "download_bytes": 14_620_479_420,
        "installed_bytes": 14_291_921_884,
        "vision_download_bytes": 1_539_478_890,
        "vision_weights_bytes": 1_144_373_248,
    },
    "5bit": {
        "display_name": "Gemma 4 26B-A4B IT 5-bit",
        "repo_id": "mlx-community/gemma-4-26b-a4b-it-5bit",
        "revision": "bc8c1a7fcc71ae85198570564917ad67cd2d1745",
        "index_sha256": "f1348e9043602e8c1382ff55f4fea85404a8b5121dff11c1c90bae68906b72e0",
        "download_bytes": 17_763_763_004,
        "installed_bytes": 17_421_032_412,
        "vision_download_bytes": 1_311_859_302,
        "vision_weights_bytes": 1_144_778_752,
    },
    "6bit": {
        "display_name": "Gemma 4 26B-A4B IT 6-bit",
        "repo_id": "mlx-community/gemma-4-26b-a4b-it-6bit",
        "revision": "968a9faa4b69230f3fc316b5755cb937a29c7ddc",
        "index_sha256": "144cf8350cb04bfe40692a183bdeba38df691478cc86e27e6242373171ce7d5f",
        "download_bytes": 20_892_749_980,
        "installed_bytes": 20_550_142_940,
        "vision_download_bytes": 1_468_984_170,
        "vision_weights_bytes": 1_145_184_256,
    },
    "8bit": {
        "display_name": "Gemma 4 26B-A4B IT 8-bit",
        "repo_id": "mlx-community/gemma-4-26b-a4b-it-8bit",
        "revision": "33c6d23798a0af159529890f79329206dbfbd73c",
        "index_sha256": "4b96ec862d7ae3f8d150b22b295cefcc9b5ef5e83f172f530dc1f2d2c11339cc",
        "download_bytes": 26_939_947_964,
        "installed_bytes": 26_871_278_556,
        "vision_download_bytes": 1_174_289_506,
        "vision_weights_bytes": 1_145_995_264,
    },
}

# ---------------------------------------------------------------------------
# Where the values are hard-coded. Each rule is (regex, template): group(1) of
# the regex is kept, the rest of the match becomes the template rendered from
# the MODELS entry. Rules apply inside the block that starts at `anchor` and
# ends at the next blank line (None = whole file); each must match once.
# ---------------------------------------------------------------------------

PATCHES = [
    ("Sources/TurboFieldfareRepack/Core/Remote/SupportedModelSource.swift", None, [
        (r'(let displayName = )"[^"]*"', '"{display_name}"'),
        (r'(let repoID = )"[^"]*"', '"{repo_id}"'),
        (r'(let revision = )"[^"]*"', '"{revision}"'),
        (r'(let sourceIndexSHA256 =\s+)"[^"]*"', '"{index_sha256}"'),
        (r'(let approximateDownloadBytes: UInt64 = )[\d_]+', '{download_bytes}'),
        (r'(let installedBytes: UInt64 = )[\d_]+', '{installed_bytes}'),
    ]),
    ("Sources/TurboFieldfareApp/Core/Installation/AppModelInstallDescriptor.swift",
     "static let `default` = AppModelInstallDescriptor(", [
        (r'(displayName: )"[^"]*"', '"{display_name}"'),
        (r'(repoID: )"[^"]*"', '"{repo_id}"'),
        (r'(revision: )"[^"]*"', '"{revision}"'),
        (r'(sourceIndexSHA256: )"[^"]*"', '"{index_sha256}"'),
        (r'(approximateDownloadBytes: )[\d_]+', '{download_bytes}'),
        (r'(installedBytes: )[\d_]+', '{installed_bytes}'),
    ]),
    # The image companion streams from the same checkpoint. Its installed size
    # is the weights file plus GTurboVisionFormatV1.metadataMaxBytes.
    ("Sources/TurboFieldfareApp/Core/Installation/AppModelInstallDescriptor.swift",
     "static let visionCompanion = AppModelInstallDescriptor(", [
        (r'(repoID: )"[^"]*"', '"{repo_id}"'),
        (r'(revision: )"[^"]*"', '"{revision}"'),
        (r'(sourceIndexSHA256: )"[^"]*"', '"{index_sha256}"'),
        (r'(approximateDownloadBytes: )[\d_]+', '{vision_download_bytes}'),
        (r'(installedBytes: )[\d_]+( \+ [\d_]+)?', '{vision_weights_bytes} + 4_194_304'),
    ]),
    ("Sources/TurboFieldfareRepack/Core/Writing/VisionPackWriter.swift", None, [
        (r'(modelID == )"[^"]*"', '"{repo_id}"'),
    ]),
    # --model-dir. `nil` keeps the app's own default: scratch/gemma4.gturbo
    # inside a checkout, else ~/Library/Application Support/TurboFieldfare/gemma4.gturbo.
    ("Sources/TurboFieldfareApp/Core/Installation/AppModelLocation.swift",
     "static func defaultURL()", [
        (r'(explicitURL: )(?:nil|URL\(fileURLWithPath: "[^"]*", isDirectory: true\))',
         '{model_dir}'),
    ]),
]


# ---------------------------------------------------------------------------
# Patching
# ---------------------------------------------------------------------------

def swift_literal(value):
    """Ints become Swift literals with digit groups; strings pass through."""
    return format(value, "_") if isinstance(value, int) else value


def block_span(text, anchor, file):
    """Character range of the region a patch applies to."""
    if anchor is None:
        return 0, len(text)
    start = text.find(anchor)
    if start < 0:
        sys.exit(f"{file}: anchor not found: {anchor}")
    end = text.find("\n\n", start)
    return start, len(text) if end < 0 else end


def model_dir_literal(model_dir):
    """Swift expression for AppModelLocation.defaultURL's explicitURL."""
    if model_dir is None:
        return "nil"
    if '"' in model_dir or "\\" in model_dir:
        sys.exit(f"--model-dir: quotes and backslashes are not supported: {model_dir}")
    return f'URL(fileURLWithPath: "{model_dir}", isDirectory: true)'


def patch(model, root, model_dir):
    values = {key: swift_literal(value) for key, value in model.items()}
    values["model_dir"] = model_dir_literal(model_dir)
    for file, anchor, rules in PATCHES:
        path = root / file
        text = path.read_text(encoding="utf-8")
        start, end = block_span(text, anchor, file)
        block = text[start:end]
        for regex, template in rules:
            matches = list(re.finditer(regex, block))
            if len(matches) != 1:
                sys.exit(f"{file}: expected one match for {regex!r}, found {len(matches)}")
            m = matches[0]
            block = block[:m.start()] + m.group(1) + template.format(**values) + block[m.end():]
        patched = text[:start] + block + text[end:]
        if patched != text:
            path.write_text(patched, encoding="utf-8")
            print(f"patched   {file}")
        else:
            print(f"unchanged {file}")
    print(f"{root} now pins {model['display_name']} "
          f"({model['repo_id']} @ {model['revision'][:12]}); "
          f"app model dir: {model_dir or 'app default'}")


def status(root):
    """Read the pinned values back and say which MODELS entry they are."""
    print(f"{'checkout':22} {root}")
    seen = {}  # key -> {value: [files]}
    for file, anchor, rules in PATCHES:
        text = (root / file).read_text(encoding="utf-8")
        start, end = block_span(text, anchor, file)
        for regex, template in rules:
            key = re.search(r"\{(\w+)\}", template).group(1)
            m = re.search(regex, text[start:end])
            if m is None:
                sys.exit(f"{file}: no match for {regex!r}")
            raw = m.group(0)[len(m.group(1)):]
            if key == "model_dir":
                quoted = re.search(r'"([^"]*)"', raw)
                value = quoted.group(1) if quoted else "app default"
            elif raw.startswith('"'):
                value = raw.strip('"')
            else:
                value = int(re.match(r"[\d_]+", raw).group(0).replace("_", ""))
            seen.setdefault(key, {}).setdefault(value, []).append(file)

    pinned = {}
    for key, values in seen.items():
        if len(values) == 1:
            pinned[key] = next(iter(values))
            print(f"{key:22} {swift_literal(pinned[key])}")
        else:
            print(f"{key:22} INCONSISTENT")
            for value, files in values.items():
                print(f"{'':22}   {swift_literal(value)}  <- {', '.join(sorted(set(files)))}")
    names = [name for name, model in MODELS.items()
             if all(model[key] == value for key, value in pinned.items() if key in model)]
    print(f"{'MODELS entry':22} {names[0] if names else 'none (run --probe and add one)'}")


# ---------------------------------------------------------------------------
# --probe: derive a MODELS entry from Hugging Face. Reads only the index,
# config.json and the safetensors headers, then repeats the installer's own
# arithmetic (RepackPlanner, RangeCopyPlanner, VisionPackPlan). On the 4-bit
# repo it reproduces the shipped constants exactly.
# ---------------------------------------------------------------------------

HF = "https://huggingface.co"
PAGE_BYTES = 16_384                      # GTurboFormatV1.alignmentBytes
RANGE_CHUNK_BYTES = 64 * 1024 * 1024     # RemoteChunkPolicy.defaultBytes
RESIDENT_HEADER_BYTES = 24               # GTurboFormatV1.residentHeaderBytes
RESIDENT_ENTRY_BYTES = 72                # GTurboFormatV1.residentEntryBytes
MULTIMODAL = ("vision_tower.", "embed_vision.", "audio_tower.")
SIDECARS = ("config.json", "tokenizer.json", "tokenizer_config.json",
            "special_tokens_map.json", "chat_template.jinja", "chat_template.json")
# manifest.json + packed_experts/layout.json + verified-install.json, measured
# on the 4-bit install. Other variants differ by a few KB, and the descriptor
# adds a 1 GiB reserve on top anyway.
JSON_ALLOWANCE_BYTES = 8_464_004


def hf_get(url, byte_range=None):
    headers = {"User-Agent": "turbo-fieldfare-patch-model"}
    if os.environ.get("HF_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["HF_TOKEN"]
    if byte_range:
        headers["Range"] = "bytes=%d-%d" % byte_range
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def load_snapshot(repo):
    """Revision, index bytes, config, file sizes, and every tensor's location."""
    api = json.loads(hf_get(f"{HF}/api/models/{repo}?blobs=true"))
    revision = api["sha"]
    sizes = {s["rfilename"]: s.get("size") or 0 for s in api["siblings"]}
    base = f"{HF}/{repo}/resolve/{revision}"
    index = hf_get(f"{base}/model.safetensors.index.json")
    config = json.loads(hf_get(f"{base}/config.json"))
    tensors = {}
    for shard in sorted(set(json.loads(index)["weight_map"].values())):
        print(f"  reading header of {shard}", file=sys.stderr)
        header_len = struct.unpack("<Q", hf_get(f"{base}/{shard}", (0, 7)))[0]
        header = json.loads(hf_get(f"{base}/{shard}", (8, 7 + header_len)))
        for name, t in header.items():
            if name == "__metadata__":
                continue
            begin, end = t["data_offsets"]
            tensors[name] = {"shard": shard, "offset": 8 + header_len + begin,
                             "size": end - begin, "dtype": t["dtype"], "shape": t["shape"]}
    return revision, index, config, sizes, tensors


def round_up(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def coalesced_download_bytes(copies):
    """Bytes the installer fetches for a list of (shard, offset, size) source
    ranges: RangeCopyPlanner.coalesce merges neighbours per shard as long as
    the merged span stays within one range chunk, gaps included."""
    pieces = []
    for shard, offset, size in copies:
        while size > 0:
            n = min(size, RANGE_CHUNK_BYTES)
            pieces.append((shard, offset, n))
            offset, size = offset + n, size - n
    total = 0
    current = None  # [shard, start, end]
    for shard, offset, n in sorted(pieces):
        end = offset + n
        if current and current[0] == shard and max(current[2], end) - current[1] <= RANGE_CHUNK_BYTES:
            current[2] = max(current[2], end)
        else:
            if current:
                total += current[2] - current[1]
            current = [shard, offset, end]
    if current:
        total += current[2] - current[1]
    return total


def layer_index(name):
    """N in '...layers.N....', or None."""
    match = re.search(r"\.layers\.(\d+)\.", name)
    return int(match.group(1)) if match else None


def text_plan(tensors):
    """(bytes of model_weights.bin + packed_experts/*.bin, bytes downloaded)."""
    copies, resident_bytes, name_bytes, resident_count = [], 0, 0, 0
    routed = {}  # layer -> weight tensor names of the routed experts
    for name, t in tensors.items():
        if not name.startswith("language_model.") or name.endswith((".scales", ".biases")):
            continue
        if ".experts.switch_glu." in name:
            routed.setdefault(layer_index(name), []).append(name)
            continue
        resident_count += 1
        name_bytes += len(name.encode())
        parts = [t]
        if t["dtype"] == "U32" and name.endswith(".weight"):
            base = name[:-len(".weight")]
            parts += [tensors[base + ".scales"], tensors[base + ".biases"]]
        for part in parts:
            resident_bytes += part["size"]
            copies.append((part["shard"], part["offset"], part["size"]))
    index_bytes = round_up(RESIDENT_HEADER_BYTES + RESIDENT_ENTRY_BYTES * resident_count
                           + name_bytes, PAGE_BYTES)

    layers_bytes = 0
    for names in routed.values():
        experts = tensors[names[0]]["shape"][0]
        blob = 0  # one expert's gate/up/down weights, scales and biases
        for name in sorted(names):
            base = name[:-len(".weight")]
            for suffix in (".weight", ".scales", ".biases"):
                part = tensors[base + suffix]
                per_expert = part["size"] // experts
                blob += per_expert
                copies += [(part["shard"], part["offset"] + e * per_expert, per_expert)
                           for e in range(experts)]
        layers_bytes += experts * round_up(blob, PAGE_BYTES)
    return index_bytes + resident_bytes + layers_bytes, coalesced_download_bytes(copies)


def vision_order(name):
    """RepackPlanner.visionExecutionKey: the order tensors take in the pack."""
    if name.startswith("vision_tower.patch_embedder."):
        return f"0000/{name}"
    if name.startswith("vision_tower.encoder.layers.") and layer_index(name) is not None:
        return f"1000/{layer_index(name):03d}/{name}"
    if name in ("vision_tower.std_bias", "vision_tower.std_scale"):
        return f"2000/{name}"
    if name.startswith("embed_vision."):
        return f"3000/{name}"
    return f"9999/{name}"


def vision_plan(tensors):
    """(bytes of the vision weights file, bytes downloaded for it)."""
    offset, copies = 0, []
    for name in sorted((n for n in tensors if n.startswith(MULTIMODAL)), key=vision_order):
        t = tensors[name]
        offset = round_up(offset, PAGE_BYTES) + t["size"]
        copies.append((t["shard"], t["offset"], t["size"]))
    return offset, coalesced_download_bytes(copies)


def probe(repo):
    revision, index, config, sizes, tensors = load_snapshot(repo)
    outputs_bytes, download_bytes = text_plan(tensors)
    vision_weights_bytes, vision_download_bytes = vision_plan(tensors)
    installed_bytes = (outputs_bytes + sum(sizes.get(f, 0) for f in SIDECARS)
                       + JSON_ALLOWANCE_BYTES)
    quant = config.get("quantization", {})
    short = repo.rsplit("/", 1)[-1]
    name = short.rsplit("-", 1)[-1] if short.endswith("bit") else short
    print(f'    "{name}": {{  # {quant.get("bits")}-bit, group {quant.get("group_size")}, {quant.get("mode")}')
    print(f'        "display_name": "{short}",  # free text, shown by the app')
    print(f'        "repo_id": "{repo}",')
    print(f'        "revision": "{revision}",')
    print(f'        "index_sha256": "{hashlib.sha256(index).hexdigest()}",')
    print(f'        "download_bytes": {download_bytes:_},')
    print(f'        "installed_bytes": {installed_bytes:_},')
    print(f'        "vision_download_bytes": {vision_download_bytes:_},')
    print(f'        "vision_weights_bytes": {vision_weights_bytes:_},')
    print('    },')


def main():
    parser = argparse.ArgumentParser(
        description="Pin a different Hugging Face checkpoint in a TurboFieldfare checkout.")
    parser.add_argument("model", nargs="?", choices=sorted(MODELS), metavar="MODEL",
                        help="MODELS entry to pin: %(choices)s")
    parser.add_argument("--status", action="store_true",
                        help="show what the checkout pins right now")
    parser.add_argument("--probe", metavar="REPO",
                        help="print a MODELS entry for a Hugging Face repo")
    parser.add_argument("--root", metavar="DIR", default=".",
                        help="checkout to work on, the directory that contains Sources/ "
                             "(default: current directory)")
    parser.add_argument("--model-dir", metavar="DIR",
                        help="with MODEL: make the Mac app install into and load from DIR, "
                             "the .gturbo directory itself (default: the app's own location)")
    args = parser.parse_args()
    if [args.model is not None, args.status, args.probe is not None].count(True) != 1:
        parser.error("pass exactly one of MODEL, --status, --probe REPO")
    if args.model_dir is not None and args.model is None:
        parser.error("--model-dir goes together with MODEL")

    if args.probe:
        probe(args.probe)  # needs no checkout
        return
    root = Path(args.root).expanduser().resolve()
    if not (root / "Sources").is_dir():
        sys.exit(f"{root}: no Sources/ directory here; "
                 "--root must point at the checkout that contains it")
    if args.status:
        status(root)
    else:
        model_dir = args.model_dir and os.path.abspath(os.path.expanduser(args.model_dir))
        patch(MODELS[args.model], root, model_dir)


if __name__ == "__main__":
    main()
