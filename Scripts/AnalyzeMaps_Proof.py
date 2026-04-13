# -*- coding: utf-8 -*-
# 3D Map Pointer Extractor Denso
# @category ECU_ReverseEngineering
# @runtime Jython

from ghidra.program.model.symbol import RefType

def test_map_extractor():
    program = getCurrentProgram()
    listing = program.getListing()
    
    # The address of your Master 3D Calculator
    target_addr = toAddr(0x000080e4)
    
    print("Starting 3D map hunt...")
    refs = getReferencesTo(target_addr)
    
    map_count = 0
    
    for ref in refs:
        if ref.getReferenceType().isCall():
            call_addr = ref.getFromAddress()
            
            # Go back up to 6 instructions before the call to look for who loads register r4
            instr = listing.getInstructionAt(call_addr)
            
            for _ in range(6):
                instr = instr.getPrevious()
                if not instr:
                    break
                
                # We check if this instruction references data (our LAB_xxxx)
                data_refs = instr.getReferencesFrom()
                for d_ref in data_refs:
                    if d_ref.isMemoryReference() and d_ref.getReferenceType().isData():
                        map_ptr = d_ref.getToAddress()
                        
                        # Print the finding
                        print("Call at: {} -> Points to map configuration at: {}".format(call_addr, map_ptr))
                        map_count += 1
                        break # Move to the next call
                else:
                    continue
                break
                
            if map_count >= 20: # Stop at 20 so as not to flood the console in this test
                break

    print("\nTest completed. The first {} structures were found.".format(map_count))

test_map_extractor()