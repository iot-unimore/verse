#!/usr/bin/env python3
"""
Generates new dynamic_onevoice_NNNNNN.yaml, dynamic_twovoice_NNNNNN.yaml and
dynamic_threevoice_NNNNNN.yaml scene files under resources/scenes/unimore/info/,
continuing the numbering already present there.

Rules:
  - dynamic_onevoice: 1 source. Its path is drawn from the "high" unimore
    path pool 120-150 + 160-170.
  - dynamic_twovoice: 2 sources. The first source's path is drawn from the
    "low" pool 010-060; the second source's path is drawn from the same
    "high" pool 120-150 + 160-170 used by dynamic_onevoice.
  - dynamic_threevoice: 3 sources. The first source's path is drawn from
    the "low" pool 010-060; the second and third sources' paths are drawn
    from the "high" pool 120-150 + 160-170 (two different paths).
  - Since the two pools are disjoint, paths used within one scene are
    always different from each other.
  - Voices are drawn from resources/voices/unimore/info (any voice); the
    voices used within one scene must differ.
  - Path/voice reuse across generated scenes is minimized as much as
    possible (shuffle-bag: cycle through every item once before any item
    repeats), falling back to reuse only once a pool is exhausted. The
    "high" path pool is shared (same bag) across dynamic_onevoice,
    dynamic_twovoice and dynamic_threevoice draws, for maximal spread.
  - Running the script with count N generates N onevoice files, plus N
    twovoice files if -t/--types >= 2, plus N threevoice files if
    -t/--types >= 3 (default -t 3, i.e. 3N files total), each numbered
    starting right after the highest existing number of its own kind in
    resources/scenes/unimore/info.
  - -s/--sounds optionally adds non-voice "sound" sources (e.g. urban
    noise) to each generated scene, and bumps the file's syntax version
    from 0.1.0 to 0.2.0 (the schema revision that introduced sounds; see
    resources/scenes/test/info/dynamic_twovoice_000001.yaml for a
    hand-written reference of that schema). If -s/--sounds is omitted
    entirely, or is explicitly 0, no sounds section is written and the
    syntax stays 0.1.0 -- both are equivalent to not having this option
    at all, which keeps the common "no sounds" case fully backward
    compatible with the legacy schema. If given a positive value:
      * a negative value is an error (the script exits without writing).
      * for dynamic_onevoice (1 voice), the sound count is capped to 1
        (a single-voice scene never gets more than one sound).
      * for dynamic_twovoice/dynamic_threevoice (2+ voices), each scene
        independently gets a random number of sounds between 1 and the
        given value (inclusive) -- so different scenes in the same run
        can end up with different sound counts.
      * sound ids are drawn from resources/sounds/urbansound8k/info, and
        their paths are drawn from a dedicated "sound" pool: unimore path
        ranges 010-040 + 130-140 + 160-170. Both are minimized for reuse
        the same way as voices/paths (shuffle-bag, shared across all scene
        kinds), and within one scene no two sounds repeat the same sound
        id or the same path.
      * scenes that end up with a sounds section get "_sound" inserted
        into their name/filename, e.g. dynamic_onevoice_000100.yaml (no
        sounds) vs dynamic_onevoice_sound_000100.yaml (has sounds). Each
        of the two variants has its own independent numbering sequence
        per scene kind (starting at 0 the first time that variant is
        generated), so e.g. dynamic_onevoice_000005.yaml and
        dynamic_onevoice_sound_000005.yaml can both exist at once.

Usage:
    python3 generate_dynamic_scenes.py COUNT [-o OUTPUT_DIR] [-t {1,2,3}] [-s SOUNDS] [--dry-run] [--seed SEED]

  COUNT is required and is the number of recipes per selected scene kind
  (see rules above for how many files that produces in total).

  -t/--types selects which scene kinds to generate:
    1 = dynamic_onevoice only
    2 = dynamic_onevoice + dynamic_twovoice
    3 = dynamic_onevoice + dynamic_twovoice + dynamic_threevoice (default)

  -s/--sounds optionally adds sound sources and bumps the syntax version
  to 0.2.0 (see rules above); omit it to keep the legacy 0.1.0 behavior.

  Examples:
    # preview what a run of 10 recipes (30 files, default -t 3) would
    # produce, without writing anything -- always do this first to
    # sanity-check the picks
    python3 generate_dynamic_scenes.py 10 --dry-run

    # actually generate 10 recipes (30 files) into
    # resources/scenes/unimore/info, the default output location
    python3 generate_dynamic_scenes.py 10

    # generate only dynamic_onevoice files (10 files)
    python3 generate_dynamic_scenes.py 10 -t 1

    # generate only dynamic_onevoice + dynamic_twovoice files (20 files)
    python3 generate_dynamic_scenes.py 10 -t 2

    # write to a scratch directory instead, e.g. to inspect the files
    # before copying them into the real info/ folder
    python3 generate_dynamic_scenes.py 10 -o /tmp/scene_preview

    # use a fixed --seed to get a reproducible (repeatable) set of picks,
    # e.g. useful when regenerating the same batch after tweaking the
    # rendering template
    python3 generate_dynamic_scenes.py 10 --seed 42

    # generate 10 recipes with sounds: syntax 0.2.0, 1 sound per
    # dynamic_onevoice scene, 1-3 random sounds per dynamic_twovoice/
    # dynamic_threevoice scene
    python3 generate_dynamic_scenes.py 10 -s 3

    # -s 0 is equivalent to omitting -s entirely: syntax stays 0.1.0 and
    # no sounds section is written
    python3 generate_dynamic_scenes.py 10 -s 0

  Re-running the script (e.g. to top up the dataset later) is safe: it
  re-scans resources/scenes/unimore/info for the highest existing number
  of each scene kind and continues from there, so it will not overwrite
  previously generated files.
"""

import argparse
import itertools
import random
import re
import sys
from pathlib import Path

_ROOT_DIR = Path(__file__).resolve().parent
_SCENES_INFO_DIR = _ROOT_DIR / "info"
_PATHS_INFO_DIR = _ROOT_DIR.parent.parent / "paths" / "unimore" / "info"
_VOICES_INFO_DIR = _ROOT_DIR.parent.parent / "voices" / "unimore" / "info"
_SOUNDS_INFO_DIR = _ROOT_DIR.parent.parent / "sounds" / "urbansound8k" / "info"

_PATH_POOL_HIGH_RANGES = [(120, 150), (160, 170)]  # onevoice source; twovoice/threevoice source 1(+2)
_PATH_POOL_LOW_RANGES = [(10, 60)]  # twovoice/threevoice source 0
_SOUND_PATH_POOL_RANGES = [(10, 40), (130, 140), (160, 170)]  # sound sources


class ShuffleBag:
    """Draws items with minimal repetition: items are handed out in random
    order, every item is used once before any item repeats, and the bag
    reshuffles only once exhausted."""

    def __init__(self, items):
        """Store the full pool of candidate items (any hashable/comparable
        type) to draw from; the bag starts empty and is filled lazily on
        the first draw."""
        self.all_items = list(items)
        self.queue = []

    def _refill(self):
        """Reshuffle a fresh copy of the full pool into the draw queue,
        called automatically once the current queue runs out."""
        self.queue = self.all_items[:]
        random.shuffle(self.queue)

    def draw_distinct(self, k):
        """Draw k distinct items (requires len(all_items) >= k)."""
        drawn = []
        while len(drawn) < k:
            if not self.queue:
                self._refill()
            item = self.queue.pop(0)
            if item in drawn:
                self.queue.append(item)
                continue
            drawn.append(item)
        return drawn


def list_path_ids(ranges):
    """List existing unimore path ids (e.g. 'path_120') whose number falls
    within any of the given inclusive (lo, hi) ranges."""
    ids = []
    for lo, hi in ranges:
        for n in range(lo, hi + 1):
            if (_PATHS_INFO_DIR / f"path_{n:03d}.yaml").exists():
                ids.append(f"path_{n:03d}")
    return ids


def list_voice_ids():
    """List all voice ids (yaml basenames) under resources/voices/unimore/info."""
    return sorted(p.stem for p in _VOICES_INFO_DIR.glob("*.yaml"))


def list_sound_ids():
    """List all sound ids (yaml basenames) under resources/sounds/urbansound8k/info."""
    return sorted(p.stem for p in _SOUNDS_INFO_DIR.glob("*.yaml"))


def next_start_number(prefix):
    """Find the highest NNNNNN already used by '{prefix}_NNNNNN.yaml' files
    in resources/scenes/unimore/info, and return the next free number (0 if
    none exist yet). Called with a plain prefix (e.g. 'dynamic_onevoice')
    and separately with its '_sound' variant (e.g. 'dynamic_onevoice_sound')
    to give each its own independent numbering sequence."""
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)\.yaml$")
    max_n = -1
    for p in _SCENES_INFO_DIR.glob(f"{prefix}_*.yaml"):
        m = pattern.match(p.name)
        if m:
            max_n = max(max_n, int(m.group(1)))
    return max_n + 1


_LISTENERS_BLOCK = """\
  #
  # listener heads (MUST be count=1)
  #
  listeners_count: 1
  listeners:
    0:
       type: heads
       subtype: unimore
       info: head_003

       # positioning: listener is static
       position:
         type: static
         coord:
           value: [0, 0, 0]
           type: spherical
           units: ['degree','degree','metre']
         view_vect:
           value: [1, 0, 0]
           type: cartesian
           units: ['metre']
         up_vect:
           value: [0, 0, 1]
"""

_ROOMS_BLOCK = """\
  #
  # rooms (MUST be count=1 or count=0 for no reverberation)
  #
  rooms_count: 0
  rooms:
   0:
      type: rooms
      subtype:
      info:

#EOF
...
"""


def _source_block(index, voice_id, path_id):
    """Render one 'sources.N' YAML block (a single dynamic voice source
    positioned by a path), for use inside a scene's sources list.
    `index` is the source's 0-based slot number, `voice_id` is a voice
    basename from resources/voices/unimore/info and `path_id` is a path
    basename (e.g. 'path_120') from resources/paths/unimore/info."""
    return f"""\
    {index}:
      # source type and info file
      type: voices
      subtype: unimore
      info: {voice_id}

      # positioning using spherical coord
      position:
        type: dynamic
        value:
          type: paths
          subtype: unimore
          info: {path_id}
"""


def _sound_block(index, sound_id, path_id):
    """Render one 'sounds.N' YAML block (a single dynamic sound source
    positioned by a path), for use inside a scene's sounds list.
    `index` is the sound's 0-based slot number, `sound_id` is a sound
    basename from resources/sounds/urbansound8k/info and `path_id` is a
    path basename (e.g. 'path_130') from resources/paths/unimore/info."""
    return f"""\
    {index}:
      # source type and info file
      type: sounds
      subtype: urbansound8k
      info: {sound_id}

      # positioning using spherical coord
      position:
        type: dynamic
        value:
          type: paths
          subtype: unimore
          info: {path_id}
"""


def build_sounds_section(sound_ids, path_ids):
    """Render the full 'sounds_count'/'sounds:' section for a scene, given
    parallel `sound_ids`/`path_ids` sequences (one entry per sound, at
    least one -- the "no sounds" case is represented by omitting the
    section entirely, see _sounds_text_for_scene())."""
    entries = "\n".join(_sound_block(i, s, p) for i, (s, p) in enumerate(zip(sound_ids, path_ids)))
    header = """\
  #
  # sounds sources (any NON human voice)
  #
  sounds_count: {count}
  sounds:
""".format(count=len(sound_ids))
    return header + entries


def _compose_tail(sounds_text):
    """Join the listeners section, an optional sounds section, and the
    rooms section into the tail shared by every scene kind, following the
    blank-line-between-sections convention used throughout this schema.
    `sounds_text` is the return value of build_sounds_section(), or None
    to omit the sounds section entirely (the legacy, syntax-0.1.0
    layout)."""
    if sounds_text:
        return f"{_LISTENERS_BLOCK}\n{sounds_text}\n{_ROOMS_BLOCK}"
    return f"{_LISTENERS_BLOCK}\n{_ROOMS_BLOCK}"


def render_onevoice(name, voice_id, path_id, version_minor=1, sounds_text=None):
    """Render a full dynamic_onevoice scene YAML (1 dynamic voice source)
    with the given scene `name`, `voice_id` and `path_id`. `version_minor`
    is the syntax.version.minor value (1 for the legacy schema, 2 once
    sounds are in use). `sounds_text`, if given, is inserted between the
    listeners and rooms sections (see build_sounds_section())."""
    sources = _source_block(0, voice_id, path_id)
    return f"""\
---
# audio rendering scene configuration file
syntax:
  name: audio_rendering_scene
  version:
    major: 0
    minor: {version_minor}
    revision: 0

#
# details
#
scene:
  name: {name}
  description: scene with a dynamic single voice in the room

#
# audio setup
#
setup:
  #
  # scene audio format for final rendering
  #
  format:
    type: wav
    subtype: pcm_s16le
    samplerate: 48000

  #
  # audio sources (voices)
  #
  sources_count: 1
  sources:
{sources}
{_compose_tail(sounds_text)}"""


def render_twovoice(name, voice_ids, path_ids, version_minor=1, sounds_text=None):
    """Render a full dynamic_twovoice scene YAML (2 dynamic voice sources)
    with the given scene `name` and per-source `voice_ids`/`path_ids`
    (each a 2-item sequence, one entry per source). `version_minor` is the
    syntax.version.minor value (1 for the legacy schema, 2 once sounds are
    in use). `sounds_text`, if given, is inserted between the listeners
    and rooms sections (see build_sounds_section())."""
    sources = "\n".join(_source_block(i, v, p) for i, (v, p) in enumerate(zip(voice_ids, path_ids)))
    return f"""\
---
# audio rendering scene configuration file
syntax:
  name: audio_rendering_scene
  version:
    major: 0
    minor: {version_minor}
    revision: 0

#
# details
#
scene:
  name: {name}
  description: scene with two voices moving in the room

#
# audio setup
#
setup:
  #
  # scene audio format for final rendering
  #
  format:
    type: wav
    subtype: pcm_s16le
    samplerate: 48000

  #
  # audio sources (voices)
  #
  sources_count: 2
  sources:
{sources}
{_compose_tail(sounds_text)}"""


def render_threevoice(name, voice_ids, path_ids, version_minor=1, sounds_text=None):
    """Render a full dynamic_threevoice scene YAML (3 dynamic voice
    sources) with the given scene `name` and per-source `voice_ids`/
    `path_ids` (each a 3-item sequence, one entry per source).
    `version_minor` is the syntax.version.minor value (1 for the legacy
    schema, 2 once sounds are in use). `sounds_text`, if given, is
    inserted between the listeners and rooms sections (see
    build_sounds_section())."""
    sources = "\n".join(_source_block(i, v, p) for i, (v, p) in enumerate(zip(voice_ids, path_ids)))
    return f"""\
---
# audio rendering scene configuration file
syntax:
  name: audio_rendering_scene
  version:
    major: 0
    minor: {version_minor}
    revision: 0

#
# details
#
scene:
  name: {name}
  description: scene with three voices moving in the room

#
# audio setup
#
setup:
  #
  # scene audio format for final rendering
  #
  format:
    type: wav
    subtype: pcm_s16le
    samplerate: 48000

  #
  # audio sources (voices)
  #
  sources_count: 3
  sources:
{sources}
{_compose_tail(sounds_text)}"""


def _scene_name(prefix, num, has_sounds):
    """Build a scene's name/filename stem: '{prefix}_NNNNNN', or
    '{prefix}_sound_NNNNNN' when `has_sounds` is True, so that files with
    a sounds section are distinguishable by filename (e.g.
    dynamic_onevoice_000100.yaml vs dynamic_onevoice_sound_000100.yaml)."""
    suffix = "_sound" if has_sounds else ""
    return f"{prefix}{suffix}_{num:06d}"


def _sounds_text_for_scene(sounds_option, allow_multiple, sound_id_bag, sound_path_bag):
    """Compute the sounds_text to embed in one scene, given the global
    -s/--sounds option (`sounds_option`, already validated to be None or
    >= 0). `allow_multiple` is False for dynamic_onevoice (capped to at
    most 1 sound) and True for dynamic_twovoice/dynamic_threevoice (a
    random count between 1 and `sounds_option`, drawn independently per
    scene). Returns a (sounds_text, log_suffix) pair: `sounds_text` is
    None if `sounds_option` is None or 0 (both are the legacy "no sounds
    section at all" case) or the rendered section text otherwise (see
    build_sounds_section()); `log_suffix` is a human-readable string to
    append to the per-scene [INFO] log line."""
    if not sounds_option:
        return None, ""
    n = random.randint(1, sounds_option) if allow_multiple else 1
    sound_ids = sound_id_bag.draw_distinct(n)
    sound_path_ids = sound_path_bag.draw_distinct(n)
    return build_sounds_section(sound_ids, sound_path_ids), f", sounds={sound_ids}, sound_paths={sound_path_ids}"


def generate(count, output_dir, dry_run, seed, types, sounds):
    """Generate `count` dynamic_onevoice scene files, plus `count`
    dynamic_twovoice files if `types` >= 2, plus `count` dynamic_threevoice
    files if `types` >= 3 (types*count total) into `output_dir`, drawing
    voices/paths per the pooling rules described in the module docstring.
    Numbering for each scene kind continues from the highest existing file
    of that kind already present in resources/scenes/unimore/info
    (regardless of `output_dir`), so re-runs never collide with previously
    generated files. If `seed` is given, the random draws are reproducible
    across runs. If `dry_run` is True, the picks are computed and logged
    but no files are written.

    `sounds` controls the -s/--sounds behavior: None or 0 means no sounds
    section is written and the syntax stays 0.1.0 (both are equivalent to
    omitting -s/--sounds entirely -- legacy, backward-compatible
    behavior); a negative value is an error (exits without writing
    anything); a positive value bumps the syntax to 0.2.0 and adds a
    sounds section per the rules in the module docstring."""
    if sounds is not None and sounds < 0:
        print(f"[ERROR] -s/--sounds must be >= 0, got: {sounds}")
        sys.exit(1)

    if seed is not None:
        random.seed(seed)

    path_pool_high_ids = list_path_ids(_PATH_POOL_HIGH_RANGES)
    path_pool_low_ids = list_path_ids(_PATH_POOL_LOW_RANGES)
    voice_ids = list_voice_ids()

    print(
        f"[INFO] pools: high(120-150,160-170)={len(path_pool_high_ids)} paths, "
        f"low(010-060)={len(path_pool_low_ids)} paths, voices={len(voice_ids)}"
    )

    # shared "high" bag: draws for dynamic_onevoice's source and for
    # dynamic_twovoice's second source come from the same pool/bag.
    path_pool_high_bag = ShuffleBag(path_pool_high_ids)
    path_pool_low_bag = ShuffleBag(path_pool_low_ids)
    voice_bag = ShuffleBag(voice_ids)

    version_minor = 1
    sound_id_bag = None
    sound_path_bag = None
    if sounds:
        version_minor = 2
        sound_ids = list_sound_ids()
        sound_path_ids = list_path_ids(_SOUND_PATH_POOL_RANGES)
        print(f"[INFO] sound pools: sounds={len(sound_ids)}, paths(010-040,130-140,160-170)={len(sound_path_ids)}")
        sound_id_bag = ShuffleBag(sound_ids)
        sound_path_bag = ShuffleBag(sound_path_ids)

    # each scene kind has two independent numbering sequences: one for
    # plain files and one for their "_sound" counterpart, since a scene
    # may or may not end up with a sounds section (see _scene_name()).
    onevoice_plain_nums = itertools.count(next_start_number("dynamic_onevoice"))
    onevoice_sound_nums = itertools.count(next_start_number("dynamic_onevoice_sound"))
    twovoice_plain_nums = itertools.count(next_start_number("dynamic_twovoice"))
    twovoice_sound_nums = itertools.count(next_start_number("dynamic_twovoice_sound"))
    threevoice_plain_nums = itertools.count(next_start_number("dynamic_threevoice"))
    threevoice_sound_nums = itertools.count(next_start_number("dynamic_threevoice_sound"))

    output_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        (voice_id,) = voice_bag.draw_distinct(1)
        (path_id,) = path_pool_high_bag.draw_distinct(1)
        sounds_text, sounds_log = _sounds_text_for_scene(sounds, False, sound_id_bag, sound_path_bag)
        has_sounds = sounds_text is not None
        num = next(onevoice_sound_nums if has_sounds else onevoice_plain_nums)
        name = _scene_name("dynamic_onevoice", num, has_sounds)
        content = render_onevoice(name, voice_id, path_id, version_minor, sounds_text)
        out_path = output_dir / f"{name}.yaml"
        print(f"[INFO] {name}: voice={voice_id}, path={path_id}{sounds_log}")
        if not dry_run:
            out_path.write_text(content)

    if types >= 2:
        for i in range(count):
            voice_ids_pick = voice_bag.draw_distinct(2)
            (path_id_low,) = path_pool_low_bag.draw_distinct(1)
            (path_id_high,) = path_pool_high_bag.draw_distinct(1)
            path_ids_pick = [path_id_low, path_id_high]
            sounds_text, sounds_log = _sounds_text_for_scene(sounds, True, sound_id_bag, sound_path_bag)
            has_sounds = sounds_text is not None
            num = next(twovoice_sound_nums if has_sounds else twovoice_plain_nums)
            name = _scene_name("dynamic_twovoice", num, has_sounds)
            content = render_twovoice(name, voice_ids_pick, path_ids_pick, version_minor, sounds_text)
            out_path = output_dir / f"{name}.yaml"
            print(f"[INFO] {name}: voices={voice_ids_pick}, paths={path_ids_pick}{sounds_log}")
            if not dry_run:
                out_path.write_text(content)

    if types >= 3:
        for i in range(count):
            voice_ids_pick = voice_bag.draw_distinct(3)
            (path_id_low,) = path_pool_low_bag.draw_distinct(1)
            path_ids_high = path_pool_high_bag.draw_distinct(2)
            path_ids_pick = [path_id_low, *path_ids_high]
            sounds_text, sounds_log = _sounds_text_for_scene(sounds, True, sound_id_bag, sound_path_bag)
            has_sounds = sounds_text is not None
            num = next(threevoice_sound_nums if has_sounds else threevoice_plain_nums)
            name = _scene_name("dynamic_threevoice", num, has_sounds)
            content = render_threevoice(name, voice_ids_pick, path_ids_pick, version_minor, sounds_text)
            out_path = output_dir / f"{name}.yaml"
            print(f"[INFO] {name}: voices={voice_ids_pick}, paths={path_ids_pick}{sounds_log}")
            if not dry_run:
                out_path.write_text(content)

    total_files = types * count
    if dry_run:
        print(f"[INFO] dry-run: {total_files} file(s) would be written to {output_dir}")
    else:
        print(f"[INFO] wrote {total_files} file(s) to {output_dir}")


def main():
    """CLI entry point: parse `count` (positional, required), -o/--output-dir
    (optional, defaults to resources/scenes/unimore/info), -t/--types,
    -s/--sounds, --dry-run and --seed, then generate the scene files via
    generate()."""
    parser = argparse.ArgumentParser(description="Generate dynamic_onevoice/twovoice/threevoice unimore scene files")
    parser.add_argument(
        "count", type=int, help="number of recipes to generate per selected type (see -t/--types)"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=_SCENES_INFO_DIR,
        help="output directory (default: resources/scenes/unimore/info)",
    )
    parser.add_argument(
        "-t",
        "--types",
        type=int,
        choices=[1, 2, 3],
        default=3,
        help="which scene kinds to generate: 1=onevoice only, 2=onevoice+twovoice, "
        "3=onevoice+twovoice+threevoice (default: %(default)s, i.e. count*3 files total)",
    )
    parser.add_argument(
        "-s",
        "--sounds",
        type=int,
        default=None,
        help="add sound sources and bump syntax to 0.2.0; N>=1=up to N random sounds per "
        "scene (capped to 1 for dynamic_onevoice), negative is an error. Omitted or 0 means "
        "no sounds section is written and syntax stays 0.1.0 (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", default=False, help="report without writing files")
    parser.add_argument("--seed", type=int, default=None, help="random seed for reproducible generation")

    args = parser.parse_args()

    generate(args.count, args.output_dir, args.dry_run, args.seed, args.types, args.sounds)


if __name__ == "__main__":
    main()
