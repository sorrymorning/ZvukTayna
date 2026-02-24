from libs.abstract import StegoMethod
from scipy.io import wavfile
import numpy as np


class EchoCodingStego(StegoMethod):



    def _size(audio_data):
        if audio_data.ndim == 1:
            # Моно сигнал
            s_len = len(audio_data)
            s_ch = 1
            # Преобразуем в 2D для единообразия
            audio_data = audio_data.reshape(-1, 1)
        else:
            # Стерео или многоканальный
            s_len, s_ch = audio_data.shape
        
        print(f"Размер сигнала: {s_len} сэмплов, {s_ch} канал(ов)")
        return s_len,s_ch


    def _prng_from_password(password, length, alpha=0.04):
        
        # 1. Конвертируем пароль в число (как в MATLAB)
        # MATLAB: sum(double(key).*(1:length(key)))
        seed = sum(ord(char) * (i+1) for i, char in enumerate(password))
        
        # 2. Создаем генератор с этим seed
        rng = np.random.default_rng(seed)
        
        # 3. Генерируем последовательность -1 и 1
        bipolar = rng.choice([-1, 1], size=length).astype(np.float32)
        
        # 4. Масштабируем на alpha (как в MATLAB: pr = alpha * prng(...))
        pr_sequence = alpha * bipolar
        
        return pr_sequence


    def encode(self, audio_path, output_path, data,d0=150, d1=200, alpha=0.04, L=8*1024):
        
        sample_rate, audio_data = wavfile.read(audio_path) # Частота дискретизации
        s_len,s_ch = EchoCodingStego._size(audio_data)
        bit = np.ravel([[int(y) for y in format(ord(x), '08b')] for x in data])
        nframe = s_len // L
        N = nframe - (nframe % 8)
        if len(bit) > N:
            print("WARNING: Сообщение слишком длинное, обрезается!")
            bits = bit[:N]
        else:
            print("WARNING: Сообщение дополняется нулями...")
            # Дополнение нулями справа
            padding = np.zeros(N - len(bit), dtype=int)
            bits = np.concatenate([bit, padding])

        password = 'mypassword123';       
        Lp = 512;                         
        pr = EchoCodingStego._prng_from_password(password, Lp, alpha)
        print(pr)


        return True,"SOrry"
        
        

    def decode(self, audio_path):
        pass