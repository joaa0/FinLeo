from __future__ import annotations

from pathlib import Path

from mistralai import Mistral

from chamaleon.config import Settings


class AudioTranscriptionError(RuntimeError):
    pass


class AudioTranscriptionClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def transcribe_file(self, file_path: str | Path) -> str:
        if not self.settings.openai_api_key:
            raise AudioTranscriptionError("MISTRAL_API_KEY nao configurada para transcricao de audio")

        client = Mistral(api_key=self.settings.openai_api_key)
        file_name = Path(file_path).name
        with open(file_path, "rb") as f:
            response = client.audio.transcriptions.complete(
                model=self.settings.mistral_transcription_model,
                file={"content": f, "file_name": file_name},
                language=self.settings.mistral_transcription_language,
            )

        text = getattr(response, "text", "") or getattr(response, "transcription", "")
        if not text:
            raise AudioTranscriptionError("A transcricao voltou vazia")
        return str(text).strip()
