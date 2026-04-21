# -*- coding: utf-8 -*-
# Automated Map to DTC Mapper (Forward Taint Analysis)
# @category ECU_ReverseEngineering
# @runtime Jython

import java.io.File as File
import java.lang.Exception as JavaException

def run_auto_mapper():
    program = getCurrentProgram()
    listing = program.getListing()
    memory = program.getMemory()
    
    try:
        # Prompt user to select their 2D maps CSV
        csv_file = askFile("Select your 2D Maps CSV", "Open")
        csv_path = csv_file.getAbsolutePath()
        
        # Output file
        save_file = askFile("Save 2D Curves DTC Mapped (CSV)", "Save")
        filepath = save_file.getAbsolutePath()
        if not filepath.endswith(".csv"):
            filepath += ".csv"
        out_path = filepath
        # out_path = csv_path.replace(".csv", "_DTC_Mapped.csv")
    except:
        print("Operation cancelled.")
        return

    print("----------------------------------------------------------------")
    print("Starting Automated Forward Taint Analysis...")
    print("Reading from: {}".format(csv_path))
    
    # Read the input CSV
    try:
        with open(csv_path, 'r') as f:
            lines = f.readlines()
    except Exception as e:
        print("Failed to read CSV: {}".format(e))
        return

    # Prepare output
    out_f = open(out_path, "w")
    out_f.write("Wrapper_Addr,Curve_Data_Addr,Target_RAM_Var,Potential_DTC_Func\n")
    
    hit_count = 0
    
    # Skip header
    for line in lines[1:]:
        if not line.strip(): continue
        
        parts = line.split(',')
        wrapper_addr_str = parts[0].strip()
        curve_addr_str = parts[3].strip()
        
        try:
            wrapper_addr = toAddr(int(wrapper_addr_str, 16))
        except:
            continue
            
        func = program.getFunctionManager().getFunctionContaining(wrapper_addr)
        if not func:
            continue
            
        # Step 1: Find RAM variables modified inside this map's wrapper function
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
            
        # Step 2: Cross-reference forward. Who reads this RAM variable?
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
                    
        # Step 3: Log the discovery
        if target_ram and dtc_func:
            out_line = "{},{},{:08X},{}\n".format(
                wrapper_addr_str, curve_addr_str, target_ram.getOffset(), dtc_func.getName()
            )
            out_f.write(out_line)
            print("Map at {} -> Writes to RAM {:08X} -> Read by Diagnostics Func: {}".format(
                curve_addr_str, target_ram.getOffset(), dtc_func.getName()))
            hit_count += 1

    out_f.close()
    print("----------------------------------------------------------------")
    print("Analysis Complete. {} Maps successfully linked to Diagnostic functions.".format(hit_count))
    print("Results saved to: {}".format(out_path))

run_auto_mapper()