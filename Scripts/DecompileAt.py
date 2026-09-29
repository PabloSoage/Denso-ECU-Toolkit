# Decompile the functions containing the given addresses and write their C to
# <outdir>/<entry>.c. Run headless after analysis (-process ... -noanalysis).
# Args: <outdir> ADDR ...
# @category ECU_ReverseEngineering
# @runtime Jython
import os

from ghidra.app.decompiler import DecompInterface

args = list(getScriptArgs())
out = args.pop(0)
fm = currentProgram.getFunctionManager()
di = DecompInterface()
di.openProgram(currentProgram)
done = set()
for a in args:
    t = int(a, 16)
    f = fm.getFunctionContaining(toAddr(t))
    if f is None:
        print("no function at %08X" % t)
        continue
    e = f.getEntryPoint().getOffset()
    if e in done:
        continue
    done.add(e)
    res = di.decompileFunction(f, 120, monitor)
    if res.decompileCompleted():
        c = res.getDecompiledFunction().getC()
    else:
        c = "// failed: " + res.getErrorMessage()
    with open(os.path.join(out, "%08X.c" % e), "w") as h:
        h.write("// function %s at %08X (asked for %08X)\n" % (f.getName(), e, t))
        h.write(c)
    print("decompiled %08X (%d chars)" % (e, len(c)))
