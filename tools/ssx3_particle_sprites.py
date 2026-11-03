"""Import authored Tricky particle images through native world texture slots.

Effect numbers index the executable's FX catalogue, not SSH directory order.
Marked descriptor values select an ordinary world texture/GS blend preset in
the existing native Emitter_Render; no global SSX 3 FX entry is replaced.
"""

from functools import lru_cache
from pathlib import Path
import struct

from tricky_assets import FormatError, read_iso_file
from tricky_ssh import to_world_ssh

TEXTURE_TAG = 0x54580000
BLEND_TAG = 0x42500000

# Native GsPkt_AddAlpha presets, also decoded by ssx3-render/frame.rs.
NATIVE_ALPHA_PRESET = {0x48: 7, 0x44: 5, 0x89: 4, 0x6a: 3,
                       0x46: 6, 0x2a: 1, 0x81: 8, 0x42: 9}


@lru_cache(maxsize=2)
def catalogue(iso: Path):
    elf = read_iso_file(iso, "SLUS_203.26")
    ssh = read_iso_file(iso, "DATA/TEXTURES/PARTICLE.SSH")
    if ssh[:4] != b"SHPS" or len(ssh) < 16:
        raise FormatError("invalid Tricky particle SSH")
    size, count = struct.unpack_from("<2I", ssh, 4)
    if size != len(ssh) or count > 1000 or 16 + count * 8 > size:
        raise FormatError("invalid Tricky particle image directory")
    entries = [struct.unpack_from("<4sI", ssh, 16 + i * 8) for i in range(count)]
    images = {}
    for i, (name, start) in enumerate(entries):
        end = entries[i + 1][1] if i + 1 < count else len(ssh)
        if name in images or start < 16 + count * 8 or end <= start or end > size:
            raise FormatError("invalid Tricky particle image extent")
        images[name] = ssh[start:end]
    # USA ELF: data table38*{name[8],mip} at33edf0. Emitter_Render1d8bc8
    # uses this effect order through the app's texture table at app+30.
    base = 0x33edf0 - 0xff000
    effects = []
    for index in range(38):
        name, mip = struct.unpack_from("<8sI", elf, base + index * 12)
        name = name.split(b"\0", 1)[0]
        if name not in images:
            raise FormatError("Tricky FX catalogue references a missing particle image")
        effects.append((name, mip))
    if [name for name, _ in effects[:5]] != [b"part", b"snfl", b"clod", b"spry", b"halo"]:
        raise FormatError("unexpected Tricky USA FX catalogue")
    # Source Emitter_Render selects style through392cf8; GsPkt_AddAlpha's
    # jump table390860 resolves that style to its actual GS ALPHA value.
    styles = struct.unpack_from("<8I", elf, 0x392cf8 - 0xff000)
    jumps = struct.unpack_from("<11I", elf, 0x390860 - 0xff000)
    blends = []
    for style in styles:
        if style >= len(jumps):
            raise FormatError("Tricky particle blend style is outside its table")
        at = jumps[style] - 0xff000
        code = struct.unpack_from("<3I", elf, at)
        immediate = next((word & 0xffff for word in code if word >> 16 == 0x2403), None)
        if immediate not in NATIVE_ALPHA_PRESET:
            raise FormatError("unrecovered Tricky particle alpha preset")
        blends.append(NATIVE_ALPHA_PRESET[immediate])
    return effects, images, blends


class ParticleSprites:
    def __init__(self, iso: Path, first_id: int):
        self.effects, self.images, self.blends = catalogue(iso)
        self.first_id = first_id
        self.ids = {}
        self.used = {}

    def sprite(self, source: int) -> int:
        if not 0 <= source < len(self.effects):
            raise FormatError("Tricky emitter sprite is outside its FX catalogue")
        name, mip = self.effects[source]
        if mip:
            raise FormatError("Tricky particle mip selection needs an explicit native mapping")
        if name not in self.ids:
            rid = self.first_id + len(self.ids)
            if rid > 32767:
                raise FormatError("Tricky particle textures exceed native signed texture IDs")
            self.ids[name] = rid
        rid = self.ids[name]
        self.used[source] = {"source_effect": source, "name": name.decode("ascii"),
                             "native_texture": rid}
        return TEXTURE_TAG | rid

    def blend(self, source: int) -> int:
        if not 0 <= source < len(self.blends):
            raise FormatError("Tricky particle blend is outside its recovered table")
        return BLEND_TAG | self.blends[source]

    def records(self):
        for name, rid in self.ids.items():
            yield rid, to_world_ssh(self.images[name], lightmap=False)

    def summary(self):
        return {"native_particle_textures": len(self.ids),
                "source_particle_sprites": [self.used[i] for i in sorted(self.used)],
                "source_particle_blend_presets": self.blends}
