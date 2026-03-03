from libs.abstract import StegoMethod
import numpy as np
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
import base64
import os
from cryptography.fernet import Fernet
from scipy.io import wavfile
import hashlib

SYNC_MARKER = np.array([1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 1, 0, 1, 0, 0, 0])  # 16 бит
END_MARKER = np.array([0, 0, 0, 0, 1, 1, 1, 1])  # 8 бит конца


class Dsss(StegoMethod):


    def _derive_key(password: str, salt: bytes) -> bytes:
        # Превращаем пароль в 32-байтный ключ через 100,000 итераций хеширования.
        # Это делает перебор паролей (Brute-force) мучительно долгим.
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000, 
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode()))

    @staticmethod
    def encrypt(data: bytes, password: str) -> bytes:
        # Генерируем уникальную соль (16 байт)
        salt = os.urandom(16)
        key = Dsss._derive_key(password, salt)
        f = Fernet(key)
        # На выходе: [SALT] + [ЗАШИФРОВАННЫЕ ДАННЫЕ]
        return salt + f.encrypt(data)


    def _gen_noise(length, seed):
        rng = np.random.default_rng(seed)
        # Генерируем последовательность из -1 и 1
        return rng.choice([-1, 1], size=length).astype(np.float32)


    def _mixer(L,bits,lower,upper,K):

        from scipy.signal import windows

        if 2*K > L:
            temp = L // 4
            K = temp - (temp % 4)
        else:
            K -= K % 4


        N = len(bits)
        m_sig = np.repeat(bits,L)
        hann_window = windows.hann(K)
        c = np.convolve(m_sig,hann_window,mode='full')
        start = K//2
        end = len(c) - K//2 + 1
        wnorm = c[start:end] / np.max(np.abs(c))
        w_sig = wnorm * (upper - lower) + lower
        m_sig = m_sig * (upper - lower) + lower
        return w_sig,m_sig


    def encode(self, audio_path, output_path, message,L_min=8*1024):
        rate, audio = wavfile.read(audio_path)

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0

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

        r = Dsss._gen_noise(L, 228)
        pr = np.tile(r, N)
        alpha = 0.005

        mix,datasig = Dsss._mixer(L,bits,-1,1,256)
        

        if audio.ndim == 1:
            stego = audio[:N*L] + alpha * mix * pr
            out = audio.copy()
            out[:N*L] = stego
        else:
            stego = audio[:N*L, 0] + alpha * mix * pr
            out = audio.copy()
            out[:N*L, 0] = stego

        output_int16 = (out * 32767).astype(np.int16)
        wavfile.write(output_path, rate, output_int16)
        # print(len(mix), len(pr), N*L)
        return True,f'{len(message)}'





    def decode(self, audio_path,len_mes,L_min=8*1024):
        rate, audio = wavfile.read(audio_path)

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype == np.uint8:
            audio = (audio.astype(np.float32) - 128.0) / 128.0

        L2 = len(audio) // (len_mes*8)
        L = max(L_min, L2)
        nframe = len(audio) // L
        N = nframe - (nframe%8)

        if audio.ndim == 1:
            xsig = audio[:N*L].reshape((L, N), order='F')
        else:
            xsig = audio[:N*L, 0].reshape((L, N), order='F')
        
        r = Dsss._gen_noise(L, 228)

        c = np.sum(xsig * r[:, None], axis=0) / L

        # Биты
        data_bits = np.where(c < 0, '0', '1')

        # Группировка по 8 бит
        bin_matrix = np.array(data_bits).reshape((8, N//8), order='F').T

        # В символы
        chars = [
            chr(int(''.join(byte), 2))
            for byte in bin_matrix
        ]

        return True,''.join(chars)[:len_mes]





