# Pre-analysis setup for a raw Denso SH705x flash image loaded with the Raw Binary
# loader: names the block ROM and makes it executable, adds the RAM block the other
# scripts expect (0xFFFF0000-0xFFFFFFFF, volatile), and seeds functions from the
# SH exception vector table (256 longwords; 1 and 3 are stack pointers).
# Use as -preScript; in the GUI, run it before Auto Analyze.
# @category ECU_ReverseEngineering
# @runtime Jython
from ghidra.program.model.data import PointerDataType

mem = currentProgram.getMemory()
ROM_END = mem.getMaxAddress().getOffset() + 1

for block in mem.getBlocks():
    if block.getStart().getOffset() == 0:
        block.setName("ROM")
        block.setExecute(True)

if mem.getBlock(toAddr(0xFFFF0000)) is None:
    ram = mem.createUninitializedBlock("RAM", toAddr(0xFFFF0000), 0x10000, False)
    ram.setRead(True)
    ram.setWrite(True)
    ram.setVolatile(True)

# SH vector table: 256 longwords; 1 and 3 are stack pointers, the rest handlers.
entries = set()
for i in range(256):
    target = mem.getInt(toAddr(i * 4)) & 0xFFFFFFFF
    if i in (1, 3):
        continue
    if 0 < target < ROM_END and target % 2 == 0:
        entries.add(target)
for i in range(256):
    try:  # noqa: SIM105 -- Jython 2.7 has no contextlib.suppress
        createData(toAddr(i * 4), PointerDataType.dataType)
    except Exception:
        pass
for target in sorted(entries):
    disassemble(toAddr(target))
    createFunction(toAddr(target), None)
print("SetupDenso: ROM end 0x%X, %d vector entry points" % (ROM_END, len(entries)))
