from libs.abstract import StegoMethod

import numpy as np
import scipy.io.wavfile as wavfile

class PhaseCoding(StegoMethod):

    def encode(self,input_filename, output_filename, message):
        rate, audio = wavfile.read(input_filename)
        if len(audio.shape) > 1:
            audio = audio[:, 0]  # Convert to mono by selecting the first channel
        audio = audio.copy()
        # Calculate message length in bits
        msg_len = 8 * len(message)
        # Calculate segment length, ensuring it's a power of 2
        seg_len = int(2 * 2**np.ceil(np.log2(2*msg_len)))
        # Calculate the number of segments needed
        seg_num = int(np.ceil(len(audio) / seg_len))

        # Resize the audio array to fit the number of segments
        audio.resize(seg_num * seg_len, refcheck=False)

        # Convert message to binary representation
        msg_bin = np.ravel([[int(y) for y in format(ord(x), '08b')] for x in message])
        # Convert binary to phase shifts (-pi/8 for 1, pi/8 for 0)
        msg_pi = msg_bin.copy()
        msg_pi[msg_pi == 0] = -1
        msg_pi = msg_pi * -np.pi / 2 # Use smaller phase to improve audio quality 1/8 may cause low BER, so change back to 1/2

        # Reshape audio into segments and perform FFT
        segs = audio.reshape((seg_num, seg_len))
        segs = np.fft.fft(segs)
        M = np.abs(segs)  # Magnitude
        P = np.angle(segs)  # Phase

        seg_mid = seg_len // 2

        # Embed message into the phase of the middle frequencies
        for i in range(seg_num):
            start = i * len(msg_pi) // seg_num
            end = (i + 1) * len(msg_pi) // seg_num
            P[i, seg_mid - (end - start):seg_mid] = msg_pi[start:end]
            P[i, seg_mid + 1:seg_mid + 1 + (end - start)] = -msg_pi[start:end][::-1]

        # Reconstruct the audio with modified phase
        segs = M * np.exp(1j * P)
        audio = np.fft.ifft(segs).real.ravel().astype(np.int16)

        # Write the modified audio to the output file
        wavfile.write(output_filename, rate, audio)

    def decode():
        pass

