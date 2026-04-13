# -*- coding: utf-8 -*-
# Automated 3D Denso Map Extractor to CSV
# @category ECU_ReverseEngineering
# @runtime Jython

from ghidra.program.model.symbol import RefType
import java.io.File as File
import java.lang.Exception as JavaException

def extract_3d_maps():
    program = getCurrentProgram()
    listing = program.getListing()
    memory = program.getMemory()
    
    # Address of the 3D Master Function
    target_addr = toAddr(0x000080e4)
    refs = getReferencesTo(target_addr)
    
    # 1. Ask the user where to physically save the CSV
    try:
        save_file = askFile("Save Denso Mappack (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
    except:
        print("Operation cancelled by the user.")
        return

    # Open file in write mode
    f = open(filepath, "w")
    f.write("Wrapper_Addr,Size_Y,Size_X,Axis_Y_Addr,Axis_X_Addr,Map_Z_Addr\n")
    
    print("Starting Mass Extraction and saving to: " + filepath)
    print("----------------------------------------------------------------")
    
    map_count = 0
    
    for ref in refs:
        if ref.getReferenceType().isCall():
            call_addr = ref.getFromAddress()
            
            instr = listing.getInstructionAt(call_addr)
            literal_ptr = None
            
            # Search for the literal pool (the "box" containing the pointer)
            for _ in range(6):
                instr = instr.getPrevious()
                if not instr:
                    break
                data_refs = instr.getReferencesFrom()
                for d_ref in data_refs:
                    if d_ref.isMemoryReference() and d_ref.getReferenceType().isData():
                        literal_ptr = d_ref.getToAddress()
                        break
                if literal_ptr:
                    break
            
            if literal_ptr:
                # PREVENT MemoryAccessException: Skip reading if the literal pointer itself is in RAM
                if literal_ptr.getOffset() >= 0xFFFF0000:
                    continue
                    
                try:
                    # THE MAGIC TRICK! Read the address INSIDE the literal pool
                    real_config_offset = memory.getInt(literal_ptr) & 0xFFFFFFFF
                    real_config_addr = toAddr(real_config_offset)
                    
                    # Skip if the actual configuration structure is in RAM or is null
                    if real_config_offset >= 0xFFFF0000 or real_config_offset == 0:
                        continue
                        
                    # READ THE REAL STRUCTURE
                    # offset 0x00: short Size Y
                    # offset 0x02: short Size X
                    # offset 0x04: int Pointer Axis Y
                    # offset 0x08: int Pointer Axis X
                    # offset 0x0C: int Pointer Map Z
                    
                    size_y = memory.getShort(real_config_addr) & 0xFFFF
                    size_x = memory.getShort(real_config_addr.add(2)) & 0xFFFF
                    
                    ptr_y = memory.getInt(real_config_addr.add(4)) & 0xFFFFFFFF
                    ptr_x = memory.getInt(real_config_addr.add(8)) & 0xFFFFFFFF
                    ptr_z = memory.getInt(real_config_addr.add(12)) & 0xFFFFFFFF
                    
                    # Sanity filter: Discard "garbage" with invalid dimensions (must be between 1 and 64)
                    if 0 < size_x <= 64 and 0 < size_y <= 64:
                        linea_csv = "{:08X},{},{},{:08X},{:08X},{:08X}\n".format(
                            call_addr.getOffset(), size_y, size_x, ptr_y, ptr_x, ptr_z
                        )
                        f.write(linea_csv)
                        print("Map Extracted OK -> Map_Addr: {:08X} | Size: {}x{}".format(ptr_z, size_y, size_x))
                        map_count += 1
                        
                except Exception as e:
                    # Python exceptions
                    pass
                except JavaException as e:
                    # Catch deep Ghidra Java memory exceptions to prevent crashes
                    pass

    f.close()
    print("----------------------------------------------------------------")
    print("SUCCESS! {} 3D maps exported to file: {}".format(map_count, filepath))

extract_3d_maps()