from typing import Tuple
import wave
import numpy as np

from libs.abstract import StegoMethod


class AudioSteganography(StegoMethod):
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

    def _check_capacity(self, audio_size: int, message_size: int) -> bool:
        """
        Проверка, помещается ли сообщение в аудиофайл
        """
        # Каждый байт сообщения требует 8 байт аудио (по 1 биту на каждый)
        required_bytes = message_size * 8
        return audio_size >= required_bytes

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


    def _embed_bit_min_error(sample, bit, k):
        """
        sample: оригинальный int16 сэмпл
        bit: 0 или 1
        k: позиция бита (например 5 для 6-го)
        """
        original = sample

        # Устанавливаем целевой бит
        base = (sample & ~(1 << k)) | (bit << k)

        best = base
        min_error = abs(base - original)

        # Перебираем варианты младших битов
        for low_bits in range(1 << k):
            candidate = (base & ~((1 << k) - 1)) | low_bits
            error = abs(candidate - original)

            if error < min_error:
                min_error = error
                best = candidate

        return best


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
            message_bits = self._message_to_bits(message)
            
            SILENCE_THRESHOLD = 500
            bit_index = 0

            usable_samples = np.sum(np.abs(samples.astype(np.int32)) >= SILENCE_THRESHOLD)  

            if usable_samples < len(message_bits):
                raise ValueError("Сообщение слишком большое")

            for i in range(len(samples)):
                if bit_index >= len(message_bits):
                    break

                if abs(samples[i]) < SILENCE_THRESHOLD:
                    continue

                samples[i] = self._embed_bit_min_error(
                    samples[i],
                    message_bits[bit_index],
                    self.lsb_position
                )

                bit_index += 1


            
            new_frames = samples.tobytes()

            with wave.open(output_file, 'wb') as out:
                out.setparams(params)
                out.writeframes(new_frames)
            
            # 5. Рассчитываем статистику
            capacity = len(samples) // 8  # Максимальное количество символов
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
    
    def decode(self, input_file: str) -> Tuple[bool, str, str]:
        """
        Декодирование сообщения из аудиофайла
        
        Args:
            input_file: Путь к аудиофайлу со скрытым сообщением
            
        Returns:
            Tuple[bool, str, str]: (успех, извлеченное сообщение, информация)
        """
        try:
            # 1. Открываем аудиофайл
            with wave.open(input_file, 'rb') as song:
                n_frames = song.getnframes()
                frames = song.readframes(n_frames)
                audio_data = bytearray(frames)
            
            # 2. Извлекаем биты сообщения
            extracted_bits = []
            
            for i in range(len(audio_data)):
                # Извлекаем целевой бит
                bit = (audio_data[i] >> self.lsb_position) & 1
                extracted_bits.append(bit)
                
                # Проверяем, не нашли ли мы маркер конца
                if len(extracted_bits) >= 8 * 5:  # Минимальная длина для маркера
                    temp_message = self._bits_to_message(extracted_bits)
                    if self.end_marker in temp_message:
                        break
            
            # 3. Преобразуем биты в сообщение
            message = self._bits_to_message(extracted_bits)
            
            if not message:
                return False, "", "Сообщение не найдено или файл поврежден"
            
            # 4. Рассчитываем статистику
            extracted_bits_count = len(message) * 8
            total_bits_read = len(extracted_bits)
            
            return True, message, (
                f"Сообщение успешно извлечено!\n"
                f"Длина сообщения: {len(message)} символов\n"
                f"Извлечено бит: {extracted_bits_count}\n"
                f"Проанализировано байт аудио: {total_bits_read // 8}"
            )
            
        except Exception as e:
            return False, "", f"Ошибка при декодировании: {str(e)}"