# -*- coding: utf-8 -*-
# Automated 2D Curve Extractor for Denso to CSV
# @category ECU_ReverseEngineering
# @runtime Jython

from ghidra.program.model.symbol import RefType
import java.io.File as File
import java.lang.Exception as JavaException

def extract_2d_maps():
    program = getCurrentProgram()
    listing = program.getListing()
    memory = program.getMemory()
    
    # Address of the master 2D function
    target_addr = toAddr(0x00008070)
    refs = getReferencesTo(target_addr)
    
    try:
        save_file = askFile("Save 2D Curves (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
    except:
        print("Operation cancelled by the user.")
        return

    f = open(filepath, "w")
    f.write("Wrapper_Addr,Size_X,Axis_X_Addr,Curve_Data_Addr\n")
    
    print("Starting Mass Extraction of 2D Curves...")
    print("----------------------------------------------------------------")
    
    map_count = 0
    seen_maps = set() # Avoid duplicate maps
    
    for ref in refs:
        if ref.getReferenceType().isCall():
            call_addr = ref.getFromAddress()
            instr = listing.getInstructionAt(call_addr)
            
            valid_map_found = False
            
            # Search up to 20 instructions back
            for _ in range(20):
                instr = instr.getPrevious()
                if not instr:
                    break
                    
                data_refs = instr.getReferencesFrom()
                for d_ref in data_refs:
                    if d_ref.isMemoryReference() and d_ref.getReferenceType().isData():
                        temp_ptr = d_ref.getToAddress()
                        
                        if temp_ptr.getOffset() >= 0xFFFF0000:
                            continue
                            
                        try:
                            # Read the real pointer
                            real_config_offset = memory.getInt(temp_ptr) & 0xFFFFFFFF
                            
                            if real_config_offset >= 0xFFFF0000 or real_config_offset == 0:
                                continue
                                
                            real_config_addr = toAddr(real_config_offset)
                            
                            # Duplicate filter
                            if real_config_addr in seen_maps:
                                valid_map_found = True
                                break
                            
                            # Denso 2D Structure:
                            # 0x00: short Size X
                            # 0x04: int Pointer Axis X
                            # 0x08: int Pointer Curve Data
                            size_x = memory.getShort(real_config_addr) & 0xFFFF
                            
                            # Sanity Filter (2D curves can have up to 128 points)
                            if 0 < size_x <= 128:
                                ptr_x = memory.getInt(real_config_addr.add(4)) & 0xFFFFFFFF
                                ptr_data = memory.getInt(real_config_addr.add(8)) & 0xFFFFFFFF
                                
                                csv_line = "{:08X},{},{:08X},{:08X}\n".format(
                                    call_addr.getOffset(), size_x, ptr_x, ptr_data
                                )
                                f.write(csv_line)
                                print("2D Curve Extracted OK -> Wrapper: {:08X} | Data Addr: {:08X} | Points: {}".format(
                                    call_addr.getOffset(), ptr_data, size_x))
                                
                                seen_maps.add(real_config_addr)
                                map_count += 1
                                valid_map_found = True
                                break
                                
                        except Exception as e:
                            pass
                        except JavaException as e:
                            pass
                            
                if valid_map_found:
                    break

    f.close()
    print("----------------------------------------------------------------")
    print("SUCCESS! {} unique 2D curves were exported.".format(map_count))

extract_2d_maps()