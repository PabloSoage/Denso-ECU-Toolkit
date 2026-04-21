# -*- coding: utf-8 -*-
# Automated Map to DTC Mapper (Forward Taint Analysis for 2D & 3D)
# @category ECU_ReverseEngineering
# @runtime Jython

import java.io.File as File
import java.lang.Exception as JavaException

def process_csv(filepath, map_type, data_addr_col_idx, out_f, program, listing):
    hit_count = 0
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print("Failed to read {}: {}".format(filepath, e))
        return 0

    for line in lines[1:]:
        if not line.strip(): continue
        parts = line.split(',')
        wrapper_addr_str = parts[0].strip()
        data_addr_str = parts[data_addr_col_idx].strip()
        
        try:
            wrapper_addr = toAddr(int(wrapper_addr_str, 16))
        except:
            continue
            
        func = program.getFunctionManager().getFunctionContaining(wrapper_addr)
        if not func: continue
            
        # Step 1: Find RAM writes
        instructions = listing.getInstructions(func.getBody(), True)
        target_ram = None
        
        for instr in instructions:
            # We look for instructions writing to RAM (FFFFxxxx range)
            refs = instr.getReferencesFrom()
            for ref in refs:
                if ref.getReferenceType().isWrite() or ref.getReferenceType().isData():
                    dest = ref.getToAddress()
                    if dest.getOffset() >= 0xFFFF0000:
                        target_ram = dest
                        break # Grab the first relevant RAM write
            if target_ram:
                break
                
        if not target_ram:
            continue # No RAM flag found for this map
            
        # Step 2: Cross-reference forward to Diagnostics Function. Who reads this RAM variable?
        ram_refs = getReferencesTo(target_ram)
        dtc_func = None
        
        for r_ref in ram_refs:
            if r_ref.getReferenceType().isRead():
                reader_addr = r_ref.getFromAddress()
                r_func = program.getFunctionManager().getFunctionContaining(reader_addr)
                
                # If the function reading the RAM is NOT the same function that wrote it
                if r_func and r_func != func:
                    dtc_func = r_func
                    break # We found the diagnostic/fault manager function
                    
        # Step 3: Log discovery
        if target_ram and dtc_func:
            out_line = "{},{},{},{:08X},{}\n".format(
                map_type, wrapper_addr_str, data_addr_str, target_ram.getOffset(), dtc_func.getName()
            )
            out_f.write(out_line)
            print("{} Map at {} -> Writes to RAM {:08X} -> Read by Diagnostics Func: {}".format(
                map_type, data_addr_str, target_ram.getOffset(), dtc_func.getName()))
            hit_count += 1
            
    return hit_count

def run_auto_mapper():
    program = getCurrentProgram()
    listing = program.getListing()
    
    try:
        # Prompt for 2D Maps CSV
        csv_2d_file = askFile("Select your 2D Maps CSV", "Open")
        csv_2d_path = csv_2d_file.getAbsolutePath()
        
        # Prompt for 3D Maps CSV
        csv_3d_file = askFile("Select your 3D Maps CSV", "Open")
        csv_3d_path = csv_3d_file.getAbsolutePath()
        
        save_file = askFile("Save 2D/3D DTC Mapped (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
        out_path = filepath
        # out_path = csv_2d_path.replace(".csv", "_and_3D_DTC_Mapped.csv")
    except:
        print("Operation cancelled.")
        return

    print("----------------------------------------------------------------")
    print("Starting Unified Forward Taint Analysis...")
    
    out_f = open(out_path, "w")
    out_f.write("Map_Type,Wrapper_Addr,Map_Data_Addr,Target_RAM_Var,Potential_DTC_Func\n")
    
    total_hits = 0
    
    # Process 2D CSV (Data Addr is in column 3)
    print("Processing 2D Maps...")
    total_hits += process_csv(csv_2d_path, "2D", 3, out_f, program, listing)
    
    # Process 3D CSV (Data Addr is in column 5)
    print("Processing 3D Maps...")
    total_hits += process_csv(csv_3d_path, "3D", 5, out_f, program, listing)

    out_f.close()
    print("----------------------------------------------------------------")
    print("Analysis Complete. {} Maps (2D & 3D) linked to Diagnostic functions.".format(total_hits))
    print("Results saved to: {}".format(out_path))

run_auto_mapper()