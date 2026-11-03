"""Emit native Luno calls and scoped branches with named scalar arguments.

Encoding follows SSX 3 USA LunoVM_Execute and its retail world-object scripts.
The VM and native builtin table remain the game's; no new opcodes are added.
"""

import struct

# Compiler labels/branches; these become the VM's existing opcodes 0/2.
LABEL = -1
GATE = -2
JUMP = -3
JUMP_FALSE = -4


def calls_blob(calls):
    """Compile (builtin_id, [(parameter_index, bits, type), ...]) calls.

    Types 1/2 are integer/float. Luno literal instructions push the native
    16-byte named argument records; opcode 0x21 consumes them and stores the
    result in register two. Registers zero/one are reserved for the native
    receiver/default argument: LunoVM_Call always initializes both, even in
    a parameterless function. The descriptor allocates their maximum stack.
    Imported action/condition adapters occupy unused builtin slots 111..127.
    Original retail scripts never name these slots.
    """
    code = []
    branches = []
    labels = {}
    maximum = 0
    for builtin, arguments in calls:
        if builtin == LABEL:
            if arguments in labels:
                raise ValueError("duplicate Luno scope label")
            labels[arguments] = len(code)
            continue
        if builtin == JUMP:
            branches.append((len(code), arguments))
            code.append(0)  # native unconditional branch
            continue
        if builtin == JUMP_FALSE:
            branches.append((len(code), arguments))
            code.append(2 | (2 << 8))  # false result of the preceding call
            continue
        target = None
        conditional = builtin == GATE
        if conditional:
            arguments, target = arguments
            builtin = 120
        if not 0 <= builtin < 256 or len(arguments) > 255:
            raise ValueError("Luno builtin/argument count exceeds instruction fields")
        maximum = max(maximum, len(arguments))
        for index, bits, kind in arguments:
            if not 0 <= index < 256 or kind not in (1, 2):
                raise ValueError("unsupported Luno named scalar argument")
            code.extend(((0x26 if kind == 2 else 0x25) | (index << 8), bits))
        code.append(0x21 | (2 << 8) | (builtin << 16) | (len(arguments) << 24))
        if builtin == 116 or conditional:
            # Native opcode 2 branches on a false scalar. Its high word is
            # an absolute instruction index, not a byte offset.
            branches.append((len(code), target))
            code.append(2 | (2 << 8))
    if len(code) > 65535:
        raise ValueError("Luno guard target exceeds the native instruction field")
    for index, target in branches:
        if target is not None and target not in labels:
            raise ValueError("undefined Luno scope label")
        code[index] |= (len(code) if target is None else labels[target]) << 16
    code.append(0xff2a)  # return without a value, as in retail object scripts
    table = 16 + len(code) * 4
    end = table + 16
    return (struct.pack("<4I", 0x004e554c, table, end, end)
            + struct.pack("<" + "I" * len(code), *code)
            + struct.pack("<4I", (-table) & 0xffffffff, 0, 3, maximum))
