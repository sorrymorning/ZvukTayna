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

    def encode(self,input_wav, output_wav, message, password=123, chip_rate=1024, alpha=0.05):
        sample_rate, audio = wavfile.read(input_wav)
        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            # audio = audio.mean(axis=1)
            audio = audio[:,0]
        print(audio[:20])
        # key = hash(password) % (2**32)
        key = int.from_bytes(
            hashlib.sha256(str(password).encode()).digest()[:4],
            'big'
        )
        total_chips = (len(SYNC_MARKER) + len(message)*8 + len(END_MARKER)) * chip_rate
        

        # ✅ ЕДИНЫЙ поток: маркер + сообщение + конец
        all_bits = np.concatenate([
            SYNC_MARKER,                                    # Синхронизация
            np.array([1 if b=='1' else 0 for b in ''.join(format(ord(c), '08b') for c in message)]),  # Данные
            END_MARKER                                      # Конец
        ])
        
        carrier = Dsss._gen_noise(total_chips, key)
        
        # Внедрение всего потока разом 
        for i, bit in enumerate(all_bits):
            start = i * chip_rate
            end = start + chip_rate
            if end < len(audio):
                audio[start:end] += (2*bit - 1) * carrier[i*chip_rate:(i+1)*chip_rate] * alpha
        
        audio = np.clip(audio, -32768, 32767).astype(np.int16)
        wavfile.write(output_wav, sample_rate, audio)
        print(audio[:20])
        return True,"Получилось"


    def decode(self, input_wav, password=123, chip_rate=1024, threshold=0.5):
        """
        Декодирование сообщения из WAV файла
        """
        # Читаем аудиофайл
        sample_rate, audio = wavfile.read(input_wav)
        
        # Конвертируем в float32 без нормализации (как при кодировании)
        audio = audio.astype(np.float32)
        if audio.ndim > 1:
            audio = audio[:, 0]  # Берем первый канал
        
        print(f"Аудио длина: {len(audio)} сэмплов")
        
        # Генерируем ключ из пароля
        # key = hash(password) % (2**32)
        key = int.from_bytes(
            hashlib.sha256(str(password).encode()).digest()[:4],
            'big'
        )
        # 1. ПОИСК СИНХРОМАРКЕРА
        sync_len = len(SYNC_MARKER) * chip_rate
        reference_sync = Dsss._gen_noise(sync_len, key)
        
        # Модулируем reference_sync маркером
        for i, bit in enumerate(SYNC_MARKER):
            start = i * chip_rate
            end = start + chip_rate
            reference_sync[start:end] *= (2*bit - 1)
        
        # Ищем синхромаркер в аудио
        search_window_size = min(60000, len(audio) - sync_len)
        search_window = audio[:search_window_size]
        
        # Корреляция для поиска паттерна
        corr = np.correlate(search_window, reference_sync, mode='valid')
        
        # Нормализуем корреляцию
        norm_factor = np.sqrt(np.sum(reference_sync**2))
        if norm_factor > 0:
            corr = corr / norm_factor
        
        # Находим пик корреляции
        best_offset = np.argmax(corr)
        max_score = corr[best_offset]
        
        # Автоматический порог, если не задан
        if threshold is None:
            threshold = np.std(corr) * 5
        
        print(f"Макс. корреляция: {max_score:.2f}, порог: {threshold:.2f}")
        
        if max_score < threshold:
            return False, "Синхромаркер не найден"
        
        print(f"Синхромаркер найден на смещении: {best_offset}")

        # 2. ИЗВЛЕЧЕНИЕ ДАННЫХ
        # Начинаем с позиции после синхромаркера
        data_start = best_offset + sync_len
        
        # Оцениваем максимальное количество бит, которое можно извлечь
        max_bits = (len(audio) - data_start) // chip_rate
        print(f"Максимум бит для извлечения: {max_bits}")
        
        extracted_bits = []
        bit_idx = 0
        
        while True:
            # Позиция текущего бита
            pos = data_start + bit_idx * chip_rate
            
            # Проверяем, не вышли ли за границы
            if pos + chip_rate > len(audio):
                print("Достигнут конец аудио")
                break
            
            # Извлекаем сегмент аудио для этого бита
            segment = audio[pos:pos + chip_rate]
            
            # Генерируем шум для этого бита (без модуляции)
            # noise_segment = Dsss._gen_noise(chip_rate, key + bit_idx)
            
            full_noise = Dsss._gen_noise((len(SYNC_MARKER) + max_bits + len(END_MARKER)) * chip_rate, key)
            noise_segment = full_noise[
                (len(SYNC_MARKER) + bit_idx)*chip_rate :
                (len(SYNC_MARKER) + bit_idx + 1)*chip_rate
            ]

            # Корреляция сегмента с шумом
            correlation = np.correlate(segment, noise_segment, mode='valid')[0]
            
            # Определяем бит по знаку корреляции
            bit = 1 if correlation > 0 else 0
            extracted_bits.append(bit)
            
            bit_idx += 1
            
            # Проверяем, не нашли ли маркер конца
            if len(extracted_bits) >= len(END_MARKER):
                # Проверяем последние N бит на совпадение с END_MARKER
                last_bits = extracted_bits[-len(END_MARKER):]
                if np.array_equal(last_bits, END_MARKER):
                    print(f"Найден маркер конца на бите {bit_idx}")
                    # Убираем маркер конца из результатов
                    extracted_bits = extracted_bits[:-len(END_MARKER)]
                    break
        
        # 3. ПРЕОБРАЗОВАНИЕ БИТ В ТЕКСТ
        if len(extracted_bits) < 8:
            return False, "Недостаточно бит для формирования сообщения"
        
        # Группируем биты в байты
        bytes_list = []
        for i in range(0, len(extracted_bits) - 7, 8):
            byte_bits = extracted_bits[i:i+8]
            byte_value = 0
            for bit in byte_bits:
                byte_value = (byte_value << 1) | bit
            bytes_list.append(byte_value)
        
        # Преобразуем байты в строку
        try:
            message = bytes(bytes_list).decode('utf-8', errors='ignore')
            # Очищаем от возможных нулевых символов
            message = message.split('\x00')[0]
        except:
            return False, "Ошибка декодирования сообщения"
        
        return True, message





