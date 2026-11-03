"""Emit straight-line native Luno calls with named scalar arguments.

Encoding follows SSX 3 USA LunoVM_Execute and its retail world-object scripts.
The VM and native builtin table remain the game's; no new opcodes are added.
"""

import struct


def calls_blob(calls):
    """Compile (builtin_id, [(parameter_index, bits, type), ...]) calls.

    Types 1/2 are integer/float. Luno literal instructions push the native
    16-byte named argument records; opcode 0x21 consumes them and stores the
    result in register two. Registers zero/one are reserved for the native
    receiver/default argument: LunoVM_Call always initializes both, even in
    a parameterless function. The descriptor allocates their maximum stack.
    Imported reset/teleport adapters occupy unused builtin slots 111..114.
    Original retail scripts never name these slots.
    """
    code = []
    guards = []
    maximum = 0
    for builtin, arguments in calls:
        if not 0 <= builtin < 256 or len(arguments) > 255:
            raise ValueError("Luno builtin/argument count exceeds instruction fields")
        maximum = max(maximum, len(arguments))
        for index, bits, kind in arguments:
            if not 0 <= index < 256 or kind not in (1, 2):
                raise ValueError("unsupported Luno named scalar argument")
            code.extend(((0x26 if kind == 2 else 0x25) | (index << 8), bits))
        code.append(0x21 | (2 << 8) | (builtin << 16) | (len(arguments) << 24))
        if builtin == 116:
            # Native opcode 2 branches on a false scalar. Its high word is
            # an absolute instruction index, not a byte offset.
            guards.append(len(code))
            code.append(2 | (2 << 8))
    if len(code) > 65535:
        raise ValueError("Luno guard target exceeds the native instruction field")
    for index in guards:
        code[index] |= len(code) << 16
    code.append(0xff2a)  # return without a value, as in retail object scripts
    table = 16 + len(code) * 4
    end = table + 16
    return (struct.pack("<4I", 0x004e554c, table, end, end)
            + struct.pack("<" + "I" * len(code), *code)
            + struct.pack("<4I", (-table) & 0xffffffff, 0, 3, maximum))
