#!/bin/bash
# Uso: ./script.sh /ruta/al/directorio > salida.txt

for archivo in $(find "$1" -type f); do
    echo "========================================"
    echo "ARCHIVO: $archivo"
    echo "========================================"
    cat "$archivo"
    echo -e "\n"
done
