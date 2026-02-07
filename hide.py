import wave
import os
import numpy as np
from typing import Tuple, Optional
from libs.lsb import AudioSteganography


def main():
    stego = AudioSteganography(lsb_position=5)  # Используем младший бит
    
    # Кодирование
    print("=== КОДИРОВАНИЕ ===")
    success, info = stego.encode(
        input_file="Beethoven_Diabelli_Variation_No._13.wav",
        output_file="encoded.wav",
        message="Привет как у тебя дела йоу"
    )
    print(info)

    success, info = stego.decode(
        input_file="encoded.wav"
    )
    print(info)


main()