from libs.abstract import StegoMethod
import numpy as np
from scipy.io import wavfile
from math import *
from math import atan2, floor
import wave
import cmath

class PhaseCodingStego(StegoMethod):
    def __init__(self, seg_len=8192, delta=np.pi/8):
        """
        seg_len: длина FFT сегмента (должна быть степенью 2)
        delta: фазовый сдвиг
        """
        self.seg_len = seg_len
        self.delta = delta

    def calculate_max_message_length(input_filename):
        rate, audio = wavfile.read(input_filename)
        if len(audio.shape) > 1:
            audio = audio[:, 0] 
        audio_len = len(audio)

        seg_len = int(2 * 2**np.ceil(np.log2(2*audio_len)))

        seg_num = int(np.ceil(audio_len / seg_len))

        max_bits_per_seg = (seg_len // 2 - 1) // 2
        max_bits = seg_num * max_bits_per_seg

        max_bytes = max_bits // 8

        return max_bytes

    def encode(self,input_filename, output_filename, message):

        rate, audio = wavfile.read(input_filename)
        if len(audio.shape) > 1:
            audio = audio[:, 0]  
        audio = audio.copy()

        msg_len = 8 * len(message)
        seg_len = int(2 * 2**np.ceil(np.log2(2*msg_len)))
        seg_num = int(np.ceil(len(audio) / seg_len))

        audio.resize(seg_num * seg_len, refcheck=False)

        msg_bin = np.ravel([[int(y) for y in format(ord(x), '08b')] for x in message])
        msg_pi = msg_bin.copy()
        msg_pi[msg_pi == 0] = -1
        msg_pi = msg_pi * -np.pi / 2

        segs = audio.reshape((seg_num, seg_len))
        segs = np.fft.fft(segs)
        M = np.abs(segs)  # Magnitude
        P = np.angle(segs)  # Phase

        seg_mid = seg_len // 2

        for i in range(seg_num):
            start = i * len(msg_pi) // seg_num
            end = (i + 1) * len(msg_pi) // seg_num
            P[i, seg_mid - (end - start):seg_mid] = msg_pi[start:end]
            P[i, seg_mid + 1:seg_mid + 1 + (end - start)] = -msg_pi[start:end][::-1]

        segs = M * np.exp(1j * P)
        audio = np.fft.ifft(segs).real.ravel().astype(np.int16)

        wavfile.write(output_filename, rate, audio)
        return True,str(len(message))



    def decode(self,input_filename, msg_len):
        # Read the input WAV file
        msg_len *= 8
        rate, audio = wavfile.read(input_filename)
        seg_len = int(2 * 2**np.ceil(np.log2(2*msg_len)))
        seg_num = int(np.ceil(len(audio) / seg_len))
        seg_mid = seg_len // 2

        extracted_bits = []

        # Extract the embedded message from the phase of the middle frequencies
        for i in range(seg_num):
            x = np.fft.fft(audio[i * seg_len:(i + 1) * seg_len])
            extracted_phase = np.angle(x)
            start = i * msg_len // seg_num
            end = (i + 1) * msg_len // seg_num
            extracted_bits.extend((extracted_phase[seg_mid - (end - start):seg_mid] < 0).astype(np.int8))

        extracted_bits = np.array(extracted_bits[:msg_len])
        # Convert binary bits back to characters
        chars = extracted_bits.reshape((-1, 8)).dot(1 << np.arange(8 - 1, -1, -1)).astype(np.uint8)
        message = ''.join(chr(c) for c in chars)
        return True,message