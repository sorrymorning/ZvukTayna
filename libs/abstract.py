from abc import ABC, abstractmethod


class StegoMethod(ABC):

    @abstractmethod
    def encode(self, audio_path, output_path, data):
        pass

    @abstractmethod
    def decode(self, audio_path):
        pass
