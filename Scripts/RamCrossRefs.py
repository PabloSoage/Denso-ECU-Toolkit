# For each RAM address, find the literal-pool entries that hold it and list the
# functions that reference those entries (that is how SH code reaches a global).
# Each function is decompiled into <outdir>/<entry>.c, and the list is appended to
# <outdir>/ramxref.txt. It does not tell reads from writes: read the C for that.
# Args: <outdir> RAMADDR ...
# @category ECU_ReverseEngineering
# @runtime Jython
import os

from ghidra.app.decompiler import DecompInterface

args = list(getScriptArgs())
out = args.pop(0)
mem = currentProgram.getMemory()
fm = currentProgram.getFunctionManager()
di = DecompInterface()
di.openProgram(currentProgram)
decompiled = set()

rom = mem.getBlock("ROM")
start, end = rom.getStart().getOffset(), rom.getEnd().getOffset()


def pool_entries(target):
    found = []
    addr = start
    while addr + 4 <= end:
        if (mem.getInt(toAddr(addr)) & 0xFFFFFFFF) == target:
            found.append(addr)
        addr += 2
    return found


def users_of(pools):
    users = {}
    for p in pools:
        for r in getReferencesTo(toAddr(p)):
            f = fm.getFunctionContaining(r.getFromAddress())
            if f is not None:
                users.setdefault(f.getEntryPoint().getOffset(), f)
    return users


def decompile_to_file(entry, function):
    res = di.decompileFunction(function, 120, monitor)
    c = res.getDecompiledFunction().getC() if res.decompileCompleted() else "// failed"
    with open(os.path.join(out, "%08X.c" % entry), "w") as h:
        h.write("// function %s at %08X\n" % (function.getName(), entry))
        h.write(c)


with open(os.path.join(out, "ramxref.txt"), "a") as report:
    for a in args:
        pools = pool_entries(int(a, 16))
        users = users_of(pools)
        line = "%s: %d pool entries, used by %s" % (
            a, len(pools), ", ".join("%08X" % e for e in sorted(users)))
        print(line)
        report.write(line + "\n")
        for e, f in sorted(users.items()):
            if e not in decompiled:
                decompiled.add(e)
                decompile_to_file(e, f)
