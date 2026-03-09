from libs.abstract import StegoMethod
import numpy as np
from scipy.io import wavfile


class Dsss(StegoMethod):

    def _gen_noise(length, seed):
        rng = np.random.default_rng(seed)
        # Генерируем последовательность из -1 и 1
        return rng.choice([-1, 1], size=length).astype(np.float32)


    def _prng(key, L):
        out = np.ones(L, 'i4')
        password = np.frombuffer(key.encode(), 'B')
        max = 128 * password.size
        seed = 1-np.sum(password)/max

        # feed seed to logistic equation to get initial value
        x = 4 * seed * (1-seed)
        for i in range(L - 1):
            if x > 0.5:
                out[i] = 1
            else:
                out[i] = -1
            x = 4 * x * (1-x)
        
        return out
        

    def _mixer(L,bits,lower=-1,upper=1,K=0):

        N = bits.size
        m_sig = np.repeat(bits, L)
        m_sig = (m_sig * (upper - lower)) + lower

        return m_sig
    
    def _set_power(audio_data, N, L, r, alpha):
        powers = np.ones(N*L, 'f8')

        for x in range(N):
            power = (np.sum(audio_data[x*L : (x+1)*L] * r)) / (L*alpha)
            if abs(power) >= 0.9:
                powers[x*L : (x+1)*L] = abs(power) + 0.5
        return powers


    def encode(self, audio_path, output_path, message,L_min=1024):
        rate, audio = wavfile.read(audio_path)
    
        if audio.ndim > 1:
            audio = audio[:, 0]

        # convert to float
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0


        bit = np.ravel([[int(y) for y in format(ord(x), '08b')] for x in message])

        if len(bit) == 0:
            raise ValueError("Empty message")
        
        L2 = len(audio) // len(bit)
        L = max(L_min, L2)
        nframe = len(audio) // L
        N = nframe - (nframe%8)

        if len(bit) > N:
            print("Сообщение укорочено")
            bits = bit[:N]
        else:
            padding = np.zeros(N - len(bit), dtype=int)
            bits = np.concatenate([bit, padding])

        # r = Dsss._gen_noise(L, 228)
        r = Dsss._prng('password',L)
        pr = np.tile(r, N)
        alpha = 0.001

        mix= Dsss._mixer(L,bits)
        stego = np.copy(audio)
        apr = alpha * pr
        power = Dsss._set_power(audio, N, L, r, alpha)
        stego[:mix.size] += mix * power * apr
        # convert back
        output = np.clip(stego, -1, 1)
        output = (stego * 32767).astype(np.int16)
        wavfile.write(output_path, rate, output)
        # print(len(mix), len(pr), N*L)
        return True,f'{len(message)}'





    def decode(self, audio_path,len_mes,L_min=1024):

        rate, audio = wavfile.read(audio_path)

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0


        L2 = len(audio) // (len_mes*8)
        L = max(L_min, L2)
        nframe = len(audio) // L
        N = nframe - (nframe%8)
        
        x_sig = np.reshape(audio[:N*L], (N, L))

        
        r = Dsss._prng('password',L)

        bits = np.ones(N, dtype='int8')
    
        for i in range(N):
            c = np.sum(np.multiply(x_sig[i], r))
            if c < 0:
                bits[i] = 0
            else:
                bits[i] = 1
        chars = np.packbits(bits)
        return True,''.join(chr(i) if i>0 and i<127 else "*" for i in chars)





