# -*- coding: utf-8 -*-
# Heuristic Scanner for Potential Denso 2D & 3D Maps -> Export to CSV
# @category ECU_ReverseEngineering
# @runtime Jython

import java.io.File as File
import java.lang.Exception as JavaException
from ghidra.program.model.mem import MemoryAccessException

def is_valid_rom_ptr(ptr_val, memory):
    # Comprueba si el puntero apunta a un bloque de memoria inicializado (ROM válida)
    # y no a la nada o a la RAM (0xFFFFxxxx)
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
        print("Operacion cancelada por el usuario.")
        return

    out_f = open(filepath, "w")
    # Usamos la misma cabecera que en tus scripts originales para que encaje en tu DataManager
    out_f.write("Map_Type,Wrapper_Addr,Size_X,Size_Y,Axis_X_Addr,Axis_Y_Addr,Map_Z_Addr\n")

    print("Iniciando Escaner Heuristico de Mapas Denso...")
    print("-" * 60)
    
    hits_3d = 0
    hits_2d = 0
    
    # Iteramos de forma segura SOLO por los bloques de memoria definidos
    for block in memory.getBlocks():
        if not block.isInitialized():
            continue
            
        curr_addr = block.getStart()
        end_addr = block.getEnd()
        
        print("Escaneando bloque: {} a {}".format(curr_addr, end_addr))
        
        while curr_addr < end_addr:
            try:
                # Evitamos desbordamientos al final del bloque
                if curr_addr.addWrap(16) > end_addr:
                    break
                    
                size_x = memory.getShort(curr_addr) & 0xFFFF
                
                # --- HEURISTICA 3D ---
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
                            curr_addr = curr_addr.add(16) # Saltamos la estructura entera
                            continue
                            
                # --- HEURISTICA 2D ---
                # Si no encajó en 3D, comprobamos si encaja en el Wrapper 2D (12 bytes)
                # 0x00: Size_X, 0x02: Ignorado/Alineacion, 0x04: Ptr_X, 0x08: Ptr_Data
                if 1 < size_x <= 128:
                    ptr_x_2d = memory.getInt(curr_addr.add(4)) & 0xFFFFFFFF
                    ptr_z_2d = memory.getInt(curr_addr.add(8)) & 0xFFFFFFFF
                    
                    if is_valid_rom_ptr(ptr_x_2d, memory) and is_valid_rom_ptr(ptr_z_2d, memory):
                        if ptr_z_2d > ptr_x_2d:
                            # Como es 2D, seteamos Size_Y a 1 y Axis_Y_Addr a 0 (como hacias en tus scripts)
                            out_f.write("2d,{:08X},{},1,{:08X},0,{:08X}\n".format(
                                curr_addr.getOffset(), size_x, ptr_x_2d, ptr_z_2d
                            ))
                            hits_2d += 1
                            curr_addr = curr_addr.add(12)
                            continue
                            
            except MemoryAccessException:
                pass # Capturamos el error especifico de memoria de Java
            except JavaException:
                pass
            except Exception:
                pass
                
            # Si no es un mapa, avanzamos 4 bytes (los wrappers suelen estar alineados a 4 bytes)
            curr_addr = curr_addr.add(4)

    out_f.close()
    print("-" * 60)
    print("¡Escaner finalizado! Encontrados {} Mapas 3D y {} Curvas 2D potenciales.".format(hits_3d, hits_2d))
    print("Guardado en: {}".format(filepath))

run_heuristic_scanner()