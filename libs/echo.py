from libs.abstract import StegoMethod
import numpy as np
from scipy.io import wavfile
from scipy.signal import lfilter
import struct
import os

class EchoStego(StegoMethod):
    def __init__(self):
        self.delay_0 = 120#100  # Delay for bit 0 (in samples)
        self.delay_1 = 200  # Delay for bit 1 (in samples)
        self.segment_len = 4096 # Length of each segment to encode a bit
        self.transition_len = 256 # Cross-fade length

    def _text_to_bits(self, data_bytes):
        bits = []
        for byte in data_bytes:
            for i in range(8):
                bits.append((byte >> (7 - i)) & 1)
        return bits

    def _bits_to_bytes(self, bits):
        bytes_list = []
        for i in range(0, len(bits), 8):
            byte_val = 0
            chunk = bits[i:i+8]
            if len(chunk) < 8:
                break # Incomplete byte
            for bit in chunk:
                byte_val = (byte_val << 1) | bit
            bytes_list.append(byte_val)
        return bytes(bytes_list)

    def encode(self, cover_path, output_path,data_bytes, echo_amplitude=0.4):
        data_bytes = data_bytes.encode('utf-8')
        rate, audio = wavfile.read(cover_path)

        # Convert to float32 for processing
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0

        # Handle stereo by processing only the first channel or mixing (simplification: use mono or first channel)
        if len(audio.shape) > 1:
            audio = audio[:, 0]

        bits = self._text_to_bits(data_bytes)
        # Add length header (32 bits) to know how much to decode
        length_bits = self._text_to_bits(struct.pack('>I', len(bits)))
        all_bits = length_bits + bits

        required_len = len(all_bits) * self.segment_len
        if required_len > len(audio):
            raise ValueError(f"Audio file too short. Need {required_len} samples, have {len(audio)}.")

        output_audio = np.zeros_like(audio)
        
        fade_in = np.linspace(0, 1, self.transition_len)
        fade_out = 1 - fade_in

        for i, bit in enumerate(all_bits):
            start = i * self.segment_len
            end = start + self.segment_len

            segment = audio[start:end]

            delay = self.delay_1 if bit == 1 else self.delay_0


            padded_segment = np.concatenate([np.zeros(delay), segment])
            echo_segment = padded_segment[:len(segment)]

            mixed_segment = segment + echo_amplitude * echo_segment

            # For this implementation, we'll just place them (might have clicks)
            # To fix clicks: We should really process the whole signal with two filters and then mix

            output_audio[start:end] = mixed_segment

        # Copy the rest of the audio
        output_audio[len(all_bits)*self.segment_len:] = audio[len(all_bits)*self.segment_len:]

        # Normalize output to prevent clipping
        max_val = np.max(np.abs(output_audio))
        if max_val > 1.0:
            output_audio /= max_val

        # Convert back to int16
        output_int16 = (output_audio * 32767).astype(np.int16)
        wavfile.write(output_path, rate, output_int16)
        return True, output_path

    def decode(self, stego_path):
        rate, audio = wavfile.read(stego_path)

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0

        if len(audio.shape) > 1:
            audio = audio[:, 0]

        # Decode length first
        length_bits_count = 32
        length_bits = []

        for i in range(length_bits_count):
            start = i * self.segment_len
            end = start + self.segment_len
            segment = audio[start:end]

            bit = self._decode_bit(segment)
            length_bits.append(bit)

        data_len_bits = self._bits_to_bytes(length_bits)
        try:
            total_bits_to_read = struct.unpack('>I', data_len_bits)[0]
        except:
            raise ValueError("Failed to decode length header")

        # Decode data
        data_bits = []
        for i in range(length_bits_count, length_bits_count + total_bits_to_read):
            start = i * self.segment_len
            end = start + self.segment_len
            if end > len(audio):
                break
            segment = audio[start:end]
            bit = self._decode_bit(segment)
            data_bits.append(bit)
        bytes = self._bits_to_bytes(data_bits) 
        return True,bytes.decode('utf-8')

    def _decode_bit(self, segment):
        # Cepstrum analysis
        # C = real(ifft(log(abs(fft(x)))))

        # Windowing
        windowed = segment * np.hamming(len(segment))

        spectrum = np.fft.fft(windowed)
        log_spectrum = np.log(np.abs(spectrum) + 1e-10) # Add small epsilon
        cepstrum = np.fft.ifft(log_spectrum).real

        # Check peaks at delay_0 and delay_1
        # We look at the range around the expected delays

        # Check peaks at delay_0 and delay_1 with a small window
        # to account for potential jitter or broad peaks
        window = 2

        val0 = np.max(cepstrum[self.delay_0 - window : self.delay_0 + window + 1])
        val1 = np.max(cepstrum[self.delay_1 - window : self.delay_1 + window + 1])

        return 1 if val1 > val0 else 0