# Улучшения на будущее

- Использования шифрование сообщения в *DSSS*

```python
def encode(self, input_wav, output_wav, message, password="123", chip_rate=1024, alpha=0.05):
    sample_rate, audio = wavfile.read(input_wav)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    
    # ШАГ 1: ШИФРУЕМ СООБЩЕНИЕ
    # Превращаем строку в байты
    message_bytes = message.encode('utf-8')
    # Шифруем с использованием пароля
    encrypted_data = self.encrypt(message_bytes, str(password))
    
    print(f"Исходное сообщение: {len(message_bytes)} байт")
    print(f"Зашифрованное: {len(encrypted_data)} байт (включая соль)")
    
    # ШАГ 2: ПРЕВРАЩАЕМ ЗАШИФРОВАННЫЕ ДАННЫЕ В БИТЫ
    # Каждый байт превращаем в 8 бит
    message_bits = []
    for byte in encrypted_data:
        # format(byte, '08b') дает строку из 8 символов '0' и '1'
        bits = [1 if b == '1' else 0 for b in format(byte, '08b')]
        message_bits.extend(bits)
    
    # ШАГ 3: СОЗДАЕМ ПОЛНЫЙ ПОТОК БИТОВ
    all_bits = np.concatenate([
        SYNC_MARKER,                    # Синхронизация
        np.array(message_bits),          # Зашифрованные данные
        END_MARKER                       # Конец
    ])
    
    # ШАГ 4: СОЗДАЕМ ШУМ ИЗ ПАРОЛЯ
    # Используем пароль для генерации seed
    key = int.from_bytes(hashlib.sha256(str(password).encode()).digest()[:4], 'little')
    
    total_chips = len(all_bits) * chip_rate
    
    if total_chips > len(audio):
        raise ValueError(f"Аудио слишком короткое! Нужно {total_chips} отсчетов, есть {len(audio)}")
    
    carrier = self._gen_noise(total_chips, key)
    
    # ШАГ 5: ВСТРАИВАЕМ
    audio_float = audio.astype(np.float32)
    
    for i, bit in enumerate(all_bits):
        start = i * chip_rate
        end = start + chip_rate
        # Адаптивная мощность
        segment_power = np.abs(audio_float[start:end]).mean() + 0.001
        adaptive_alpha = alpha * segment_power
        audio_float[start:end] += (2*bit - 1) * carrier[i*chip_rate:(i+1)*chip_rate] * adaptive_alpha
    
    audio_float = np.clip(audio_float, -32768, 32767).astype(np.int16)
    wavfile.write(output_wav, sample_rate, audio_float)
    
    print(f"Встроено {len(message_bits)} бит зашифрованных данных")
    return True, "Сообщение зашифровано и встроено"
```