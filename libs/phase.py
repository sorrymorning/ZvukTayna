from libs.abstract import StegoMethod
import numpy as np
from scipy.io import wavfile


class PhaseCodingStego(StegoMethod):
    def __init__(self, seg_len=8192, delta=np.pi/8):
        """
        seg_len: длина FFT сегмента (должна быть степенью 2)
        delta: фазовый сдвиг
        """
        self.seg_len = seg_len
        self.delta = delta

    def _int_to_bits(self, value, nbits=32):
        return np.array([(value >> i) & 1 for i in range(nbits-1, -1, -1)], dtype=np.uint8)

    def _bits_to_int(self, bits):
        val = 0
        for b in bits:
            val = (val << 1) | int(b)
        return val

    def _bytes_to_bits(self, data: bytes):
        bits = []
        for byte in data:
            bits.extend([(byte >> i) & 1 for i in range(7, -1, -1)])
        return np.array(bits, dtype=np.uint8)

    def _bits_to_bytes(self, bits):
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for b in bits[i:i+8]:
                byte = (byte << 1) | int(b)
            out.append(byte)
        return bytes(out)

    
    def encode(self, input_file, output_file, message: str):

        rate, audio = wavfile.read(input_file)

        if len(audio.shape) > 1:
            audio = audio[:, 0]

        audio = audio.astype(np.int16)
        original_len = len(audio)

        msg_bytes = message.encode("utf-8")
        length_bits = self._int_to_bits(len(msg_bytes), 32)
        msg_bits = self._bytes_to_bits(msg_bytes)

        payload_bits = np.concatenate([length_bits, msg_bits])
        payload_len = len(payload_bits)

        max_bits = self.seg_len // 2 - 1
        if payload_len > max_bits:
            raise ValueError(f"Message too long. Max bits={max_bits}, needed={payload_len}")

        seg_num = int(np.ceil(len(audio) / self.seg_len))
        pad = seg_num * self.seg_len - len(audio)
        if pad > 0:
            audio = np.pad(audio, (0, pad), mode="constant")

        segs = audio.reshape((seg_num, self.seg_len)).astype(np.float64)

        fft_segs = np.fft.fft(segs, axis=1)

        M = np.abs(fft_segs)
        P = np.angle(fft_segs)

        phase_diff = P[1:] - P[:-1]

        new_phase = P[0].copy()

        for i in range(payload_len):
            k = i + 1  
            new_phase[k] = self.delta if payload_bits[i] == 1 else -self.delta
            new_phase[-k] = -new_phase[k]  

        P[0] = new_phase

        for i in range(1, seg_num):
            P[i] = P[i-1] + phase_diff[i-1]

        new_fft = M * np.exp(1j * P)
        new_segs = np.fft.ifft(new_fft, axis=1).real

        stego = new_segs.ravel()
        stego = np.clip(stego, -32768, 32767).astype(np.int16)

        stego = stego[:original_len]

        wavfile.write(output_file, rate, stego)

        return True, f"Phase coding embedded {len(msg_bytes)} bytes ({payload_len} bits)."

    def decode(self, input_file):
        rate, audio = wavfile.read(input_file)

        if len(audio.shape) > 1:
            audio = audio[:, 0]

        audio = audio.astype(np.int16)

        # pad audio
        seg_num = int(np.ceil(len(audio) / self.seg_len))
        pad = seg_num * self.seg_len - len(audio)
        if pad > 0:
            audio = np.pad(audio, (0, pad), mode="constant")

        segs = audio.reshape((seg_num, self.seg_len)).astype(np.float64)

        fft_segs = np.fft.fft(segs, axis=1)
        P = np.angle(fft_segs)

        ref_phase = P[0]

        extracted_bits = []

        for i in range(32):
            k = i + 1
            extracted_bits.append(1 if ref_phase[k] > 0 else 0)

        msg_len_bytes = self._bits_to_int(extracted_bits)

        msg_bits = []
        for i in range(msg_len_bytes * 8):
            k = 32 + i + 1
            msg_bits.append(1 if ref_phase[k] > 0 else 0)

        msg_bytes = self._bits_to_bytes(msg_bits)

        return True, msg_bytes.decode("utf-8", errors="ignore")

