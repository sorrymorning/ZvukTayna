from typing import Tuple
import wave
import numpy as np

from libs.abstract import StegoMethod


class LSBCodingStego(StegoMethod):
    """
    Класс для стеганографии в WAV-файлах с использованием LSB-метода
    """
    
    def __init__(self, lsb_position: int = 0):
        """
        Инициализация параметров стеганографии
        
        Args:
            lsb_position: Позиция LSB (0 - младший бит, 1 - следующий и т.д.)
                         Чем выше значение, тем меньше искажений, но ниже вместимость
        """
        self.lsb_position = lsb_position
        self.end_marker = "*^*^*"  # Маркер конца сообщения

    def _int_to_bits(self, value: int, bits: int = 32):
        return [(value >> i) & 1 for i in range(bits-1, -1, -1)]


    def _bits_to_int(self, bits):
        value = 0
        for b in bits:
            value = (value << 1) | b
        return value


    def _bytes_to_bits(self, data: bytes):
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits


    def _bits_to_bytes(self, bits):
        out = bytearray()
        for i in range(0, len(bits), 8):
            byte = 0
            for b in bits[i:i+8]:
                byte = (byte << 1) | b
            out.append(byte)
        return bytes(out)
    
    def _message_to_bits(self, message: str) -> list:
        """
        Преобразование сообщения в список битов
        """
        bits = []
        # Добавляем маркер конца сообщения
        full_message = message + self.end_marker
        
        for char in full_message:
            # Преобразуем символ в бинарную строку (8 бит)
            binary = format(ord(char), '08b')
            # Добавляем каждый бит в список как целое число
            bits.extend([int(bit) for bit in binary])
        
        return bits
    
    def _bits_to_message(self, bits: list) -> str:
        """
        Преобразование списка битов обратно в сообщение
        """
        message = ""
        
        # Обрабатываем биты группами по 8
        for i in range(0, len(bits), 8):
            if i + 8 > len(bits):
                break
                
            # Собираем 8 битов
            byte_bits = bits[i:i+8]
            # Преобразуем в строку битов
            byte_str = ''.join(str(bit) for bit in byte_bits)
            # Конвертируем в символ
            char_code = int(byte_str, 2)
            char = chr(char_code)
            
            # Проверяем маркер конца
            if message.endswith(self.end_marker[:-1]) and char == self.end_marker[-1]:
                message = message[:-len(self.end_marker)+1]
                break
                
            message += char
        
        return message


    def _embed_bit_min_error(self, sample, bit, k):
        original = int(sample)

        u = original & 0xFFFF

        base = (u & ~(1 << k)) | ((bit & 1) << k)

        best = base
        min_error = abs(np.int32(self._uint16_to_int16(base)) - np.int32(original))

        for low_bits in range(1 << k):
            candidate = (base & ~((1 << k) - 1)) | low_bits
            error = abs(np.int32(self._uint16_to_int16(candidate)) - np.int32(original))
            if error < min_error:
                min_error = error
                best = candidate

        return np.int16(self._uint16_to_int16(best))

    def _uint16_to_int16(self,x):
        return x - 0x10000 if x >= 0x8000 else x




    def encode(self, input_file: str, output_file: str, message: str) -> Tuple[bool, str]:
        """
        Кодирование сообщения в аудиофайл
        
        Args:
            input_file: Путь к исходному аудиофайлу
            output_file: Путь для сохранения файла со скрытым сообщением
            message: Сообщение для сокрытия
            
        Returns:
            Tuple[bool, str]: (успех, сообщение об ошибке/успехе)
        """
        try:
            with wave.open(input_file, 'rb') as song:
                params = song.getparams()
                n_frames = song.getnframes()
                frames = song.readframes(n_frames)
                
            samples = np.frombuffer(frames, dtype=np.int16).copy()
        
            # 2. Проверяем вместимость
            message_bytes = message.encode("utf-8")
            length_bits = self._int_to_bits(len(message_bytes), 32)
            message_bits = length_bits + self._bytes_to_bits(message_bytes)
            
            SILENCE_THRESHOLD = 500
            bit_index = 0

            usable_samples = np.sum(np.abs(samples.astype(np.int32)) >= SILENCE_THRESHOLD)  

            if usable_samples < len(message_bits):
                raise ValueError("Сообщение слишком большое")

            for i in range(len(samples)):
                if bit_index >= len(message_bits):
                    break

                if np.abs(samples[i].astype(np.int32)) < SILENCE_THRESHOLD:
                    continue

                samples[i] = self._embed_bit_min_error(
                    samples[i],
                    message_bits[bit_index],
                    self.lsb_position
                )

                bit_index += 1

            if bit_index < len(message_bits):
                raise ValueError("Не удалось встроить все биты сообщения")
            
            new_frames = samples.tobytes()

            with wave.open(output_file, 'wb') as out:
                out.setparams(params)
                out.writeframes(new_frames)
            
            # 5. Рассчитываем статистику
            capacity = usable_samples // 8  # Максимальное количество символов
            used = len(message)
            usage_percent = (used / capacity) * 100
            
            return True, (
                f"Сообщение успешно скрыто!\n"
                f"Файл сохранен: {output_file}\n"
                f"Размер сообщения: {used} символов\n"
                f"Использовано емкости: {usage_percent:.2f}%\n"
                f"Позиция LSB: {self.lsb_position}"
            )
            
        except Exception as e:
            return False, f"Ошибка при кодировании: {str(e)}"
    
    def decode(self, input_file: str) -> Tuple[bool, str]:
        try:
            with wave.open(input_file, 'rb') as song:
                n_frames = song.getnframes()
                frames = song.readframes(n_frames)

            samples = np.frombuffer(frames, dtype=np.int16)

            SILENCE_THRESHOLD = 500
            extracted_bits = []

            # 1) Сначала извлекаем 32 бита длины
            for i in range(len(samples)):
                if abs(int(samples[i])) < SILENCE_THRESHOLD:
                    continue

                bit = (int(samples[i]) >> self.lsb_position) & 1
                extracted_bits.append(bit)

                if len(extracted_bits) == 32:
                    break

            if len(extracted_bits) < 32:
                return False, "Не удалось извлечь длину сообщения"

            msg_length = self._bits_to_int(extracted_bits)  # длина в байтах
            total_bits_needed = msg_length * 8

            # 2) Теперь извлекаем сообщение
            message_bits = []
            count = 0

            for j in range(i + 1, len(samples)):
                if abs(int(samples[j])) < SILENCE_THRESHOLD:
                    continue

                bit = (int(samples[j]) >> self.lsb_position) & 1
                message_bits.append(bit)
                count += 1

                if count == total_bits_needed:
                    break

            if len(message_bits) < total_bits_needed:
                return False, "Не удалось извлечь все биты сообщения"

            message_bytes = self._bits_to_bytes(message_bits)

            try:
                message = message_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return False, "Сообщение извлечено, но не удалось декодировать UTF-8"

            return True, message

        except Exception as e:
            return False, f"Ошибка при декодировании: {str(e)}"
