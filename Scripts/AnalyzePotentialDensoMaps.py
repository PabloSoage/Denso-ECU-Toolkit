# -*- coding: utf-8 -*-
# Heuristic Scanner for Potential Denso 2D & 3D Maps -> Export to CSV
# @category ECU_ReverseEngineering
# @runtime Jython

import java.io.File as File
import java.lang.Exception as JavaException
from ghidra.program.model.mem import MemoryAccessException

def is_valid_rom_ptr(ptr_val, memory):
    # Checks if the pointer points to an initialized memory block (valid ROM)
    # and not to null or RAM space (0xFFFFxxxx)
    if ptr_val >= 0xFFFF0000 or ptr_val == 0:
        return False
    try:
        addr = toAddr(ptr_val)
        block = memory.getBlock(addr)
        return block is not None and block.isInitialized()
    except:
        return False

def run_heuristic_scanner():
    program = getCurrentProgram()
    memory = program.getMemory()
    
    try:
        save_file = askFile("Save Potential Maps (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
    except:
        print("Operation cancelled by user.")
        return

    out_f = open(filepath, "w")

    out_f.write("Map_Type,Wrapper_Addr,Size_X,Size_Y,Axis_X_Addr,Axis_Y_Addr,Map_Z_Addr\n")

    print("Starting Denso Heuristic Map Scanner...")
    print("-" * 60)
    
    hits_3d = 0
    hits_2d = 0
    
    # Iterate ONLY through defined memory blocks
    for block in memory.getBlocks():
        if not block.isInitialized():
            continue
            
        curr_addr = block.getStart()
        end_addr = block.getEnd()
        
        print("Scanning block: {} to {}".format(curr_addr, end_addr))
        
        while curr_addr < end_addr:
            try:
                # Avoid overflows at the end of the block
                if curr_addr.addWrap(16) > end_addr:
                    break
                    
                size_x = memory.getShort(curr_addr) & 0xFFFF
                
                # --- 3D HEURISTIC ---
                size_y = memory.getShort(curr_addr.add(2)) & 0xFFFF
                if 1 < size_x <= 64 and 1 < size_y <= 64:
                    ptr_x = memory.getInt(curr_addr.add(4)) & 0xFFFFFFFF
                    ptr_y = memory.getInt(curr_addr.add(8)) & 0xFFFFFFFF
                    ptr_z = memory.getInt(curr_addr.add(12)) & 0xFFFFFFFF
                    
                    if is_valid_rom_ptr(ptr_x, memory) and is_valid_rom_ptr(ptr_y, memory) and is_valid_rom_ptr(ptr_z, memory):
                        if ptr_z > ptr_x and ptr_z > ptr_y:
                            out_f.write("3d,{:08X},{},{},{:08X},{:08X},{:08X}\n".format(
                                curr_addr.getOffset(), size_x, size_y, ptr_x, ptr_y, ptr_z
                            ))
                            hits_3d += 1
                            curr_addr = curr_addr.add(16) # Skip the entire structure
                            continue
                            
                # --- 2D HEURISTIC ---
                # If it didn't fit 3D, check if it fits the 2D Wrapper (12 bytes)
                # 0x00: Size_X, 0x02: Ignored/Alignment, 0x04: Ptr_X, 0x08: Ptr_Data
                if 1 < size_x <= 128:
                    ptr_x_2d = memory.getInt(curr_addr.add(4)) & 0xFFFFFFFF
                    ptr_z_2d = memory.getInt(curr_addr.add(8)) & 0xFFFFFFFF
                    
                    if is_valid_rom_ptr(ptr_x_2d, memory) and is_valid_rom_ptr(ptr_z_2d, memory):
                        if ptr_z_2d > ptr_x_2d:
                            # As it is 2D, we set Size_Y to 1 and Axis_Y_Addr to 0
                            out_f.write("2d,{:08X},{},1,{:08X},0,{:08X}\n".format(
                                curr_addr.getOffset(), size_x, ptr_x_2d, ptr_z_2d
                            ))
                            hits_2d += 1
                            curr_addr = curr_addr.add(12)
                            continue
                            
            except MemoryAccessException:
                pass # Catch specific Java memory errors
            except JavaException:
                pass
            except Exception:
                pass
                
            # If no map found, advance 4 bytes (wrappers are usually 4-byte aligned)
            curr_addr = curr_addr.add(4)

    out_f.close()
    print("-" * 60)
    print("Scan finished! Found {} potential 3D Maps and {} 2D Curves.".format(hits_3d, hits_2d))
    print("Saved to: {}".format(filepath))

run_heuristic_scanner()
