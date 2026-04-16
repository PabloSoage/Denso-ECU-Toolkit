# -*- coding: utf-8 -*-
# Automated 3D Denso Map Extractor to CSV (Resilient Edition)
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
    
    try:
        save_file = askFile("Save Denso Mappack (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
    except:
        print("Operation cancelled by the user.")
        return

    f = open(filepath, "w")
    f.write("Wrapper_Addr,Size_X,Size_Y,Axis_X_Addr,Axis_Y_Addr,Map_Z_Addr\n")
    
    print("Starting Resilient Mass Extraction...")
    print("Saving to: " + filepath)
    print("----------------------------------------------------------------")
    
    map_count = 0
    seen_maps = set() # Avoid duplicate maps
    
    for ref in refs:
        if ref.getReferenceType().isCall():
            call_addr = ref.getFromAddress()
            instr = listing.getInstructionAt(call_addr)
            
            valid_map_found = False
            
            # Look back up to 20 instructions
            for _ in range(20):
                instr = instr.getPrevious()
                if not instr:
                    break
                    
                data_refs = instr.getReferencesFrom()
                for d_ref in data_refs:
                    if d_ref.isMemoryReference() and d_ref.getReferenceType().isData():
                        temp_ptr = d_ref.getToAddress()
                        
                        # Ignore RAM pointers immediately
                        if temp_ptr.getOffset() >= 0xFFFF0000:
                            continue
                            
                        try:
                            # Dereference the literal pool
                            real_config_offset = memory.getInt(temp_ptr) & 0xFFFFFFFF
                            
                            # Ensure the real struct is in ROM
                            if real_config_offset >= 0xFFFF0000 or real_config_offset == 0:
                                continue
                                
                            real_config_addr = toAddr(real_config_offset)
                            
                            # Duplicate filter
                            if real_config_addr in seen_maps:
                                valid_map_found = True
                                break
                            
                            # Read dimensions
                            size_x = memory.getShort(real_config_addr) & 0xFFFF
                            size_y = memory.getShort(real_config_addr.add(2)) & 0xFFFF
                            
                            # STRICT SANITY CHECK (This filters out garbage/noise)
                            if 0 < size_x <= 64 and 0 < size_y <= 64:
                                ptr_x = memory.getInt(real_config_addr.add(4)) & 0xFFFFFFFF
                                ptr_y = memory.getInt(real_config_addr.add(8)) & 0xFFFFFFFF
                                ptr_z = memory.getInt(real_config_addr.add(12)) & 0xFFFFFFFF
                                
                                # BOOM! We got a valid map
                                csv_line = "{:08X},{},{},{:08X},{:08X},{:08X}\n".format(
                                    call_addr.getOffset(), size_x, size_y, ptr_x, ptr_y, ptr_z
                                )
                                f.write(csv_line)
                                print("Map Extracted OK -> Wrapper: {:08X} | Map_Addr: {:08X} | Size: {}x{}".format(
                                    call_addr.getOffset(), ptr_z, size_y, size_x))
                                seen_maps.add(real_config_addr)
                                map_count += 1
                                valid_map_found = True
                                break # Break the reference loop
                                
                        except Exception as e:
                            pass
                        except JavaException as e:
                            pass
                            
                if valid_map_found:
                    break # Break the instruction backward loop

    f.close()
    print("----------------------------------------------------------------")
    print("SUCCESS! {} 3D maps exported.".format(map_count))

extract_3d_maps()