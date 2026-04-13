# Script to extract unique data/map addresses referenced in ROM
# @author Varuna
# @category ECU_ReverseEngineering
# @runtime Jython

import csv
from ghidra.program.model.symbol import RefType

def extract_map_addresses():
    program = getCurrentProgram()
    listing = program.getListing()
    reference_manager = program.getReferenceManager()
    
    # ROM range (Adjusted to your .ori file size)
    rom_start = 0x00000000
    rom_end = 0x0017FFFF 
    
    # Use a set to prevent duplicate addresses
    unique_addresses = set()
    
    # Prompt user for save location
    output_file = askFile("Save Map Addresses CSV", "Save")
    
    print("Scanning code for map pointers...")
    
    # Get the very first address in the program to start the iterator
    min_address = program.getMinAddress()
    ref_iterator = reference_manager.getReferenceIterator(min_address)
    
    # Iterate through all references in the database
    while ref_iterator.hasNext():
        ref = ref_iterator.next()
        
        # We only care about memory reads (potential map data)
        if ref.isMemoryReference() and ref.getReferenceType().isRead():
            to_addr = ref.getToAddress()
            offset = to_addr.getOffset()
            
            # Filter: Only data read within the ROM area boundaries
            if rom_start <= offset <= rom_end:
                # Check that it is NOT an instruction (we want data, not code)
                if not listing.getInstructionAt(to_addr):
                    unique_addresses.add("0x{}".format(to_addr.toString()))
                    
    # Export results to CSV
    with open(output_file.getAbsolutePath(), 'wb') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Hex_Address_Possible_Map"])
        
        # Sort addresses to make them easier to follow in WinOLS
        for addr in sorted(unique_addresses):
            writer.writerow([addr])

    print("Done! Found {} unique addresses. CSV saved to: {}".format(len(unique_addresses), output_file.getAbsolutePath()))

extract_map_addresses()