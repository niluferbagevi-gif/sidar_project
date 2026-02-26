"""
Sidar Project - LLM İstemcisi
Ollama ve Google Gemini API entegrasyonu.
"""

import json
import logging
import requests
from typing import List, Dict, Optional, Iterator, Union

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama veya Gemini üzerinden LLM çağrıları yapar."""

    def __init__(self, provider: str, config) -> None:
        """
        provider: "ollama" | "gemini"
        config  : Config nesnesi
        """
        self.provider = provider.lower()
        self.config = config

    # ─────────────────────────────────────────────
    #  ANA ÇAĞRI NOKTASI
    # ─────────────────────────────────────────────

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        stream: bool = False,
    ) -> Union[str, Iterator[str]]:
        """
        Sohbet tamamlama isteği gönder.

        Args:
            stream: True ise yanıt parça parça (Iterator) döner.
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + list(messages)

        if self.provider == "ollama":
            return self._ollama_chat(messages, model or self.config.CODING_MODEL, temperature, stream)
        elif self.provider == "gemini":
            return self._gemini_chat(messages, temperature, stream)
        else:
            raise ValueError(f"Bilinmeyen AI sağlayıcısı: {self.provider}")

    # ─────────────────────────────────────────────
    #  OLLAMA
    # ─────────────────────────────────────────────

    def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        stream: bool
    ) -> Union[str, Iterator[str]]:
        url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/chat"
        
        # JSON Modunu Zorla
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "format": "json",
            "options": {"temperature": temperature},
        }
        
        try:
            # STREAM MODU
            if stream:
                return self._stream_ollama_response(url, payload)
            
            # NORMAL MOD
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

        except requests.exceptions.ConnectionError:
            logger.error("Ollama bağlantı hatası.")
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] Ollama'ya bağlanılamadı. 'ollama serve' açık mı?", "thought": "Hata oluştu."})
            return iter([msg]) if stream else msg
        except Exception as exc:
            logger.error("Ollama hata: %s", exc)
            msg = json.dumps({"tool": "final_answer", "argument": f"[HATA] Ollama: {exc}", "thought": "Hata oluştu."})
            return iter([msg]) if stream else msg

    def _stream_ollama_response(self, url: str, payload: dict) -> Iterator[str]:
        """Ollama stream yanıtını parçalar halinde yield eder."""
        try:
            with requests.post(url, json=payload, stream=True, timeout=120) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if line:
                        try:
                            body = json.loads(line)
                            chunk = body.get("message", {}).get("content", "")
                            if chunk:
                                yield chunk
                        except json.JSONDecodeError:
                            continue
        except Exception as exc:
            yield json.dumps({"tool": "final_answer", "argument": f"\n[HATA] Akış kesildi: {exc}", "thought": "Hata"})

    # ─────────────────────────────────────────────
    #  GEMINI
    # ─────────────────────────────────────────────

    def _gemini_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        stream: bool
    ) -> Union[str, Iterator[str]]:
        try:
            import google.generativeai as genai
        except ImportError:
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] 'google-generativeai' kurulu değil.", "thought": "Paket eksik"})
            return iter([msg]) if stream else msg

        if not self.config.GEMINI_API_KEY:
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] GEMINI_API_KEY ayarlanmamış.", "thought": "Key eksik"})
            return iter([msg]) if stream else msg

        genai.configure(api_key=self.config.GEMINI_API_KEY)

        # Sistem mesajını ayır
        system_text = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                chat_messages.append(m)

        # JSON Modunu Zorla
        model = genai.GenerativeModel(
            model_name=self.config.GEMINI_MODEL,
            system_instruction=system_text or None,
            generation_config={
                "temperature": temperature,
                "response_mime_type": "application/json"
            },
        )

        # Gemini history formatı
        history = []
        last_user = None
        for m in chat_messages:
            role = "user" if m["role"] == "user" else "model"
            if role == "user":
                last_user = m["content"]
                if history or last_user:
                    history.append({"role": role, "parts": [m["content"]]})
            else:
                history.append({"role": role, "parts": [m["content"]]})

        if not last_user and chat_messages:
            last_user = chat_messages[-1]["content"]
        
        prompt = last_user or "Merhaba"

        try:
            chat_session = model.start_chat(history=history[:-1] if history else [])
            
            if stream:
                response_stream = chat_session.send_message(prompt, stream=True)
                return self._stream_gemini_generator(response_stream)
            else:
                response = chat_session.send_message(prompt)
                return response.text

        except Exception as exc:
            logger.error("Gemini hata: %s", exc)
            msg = json.dumps({"tool": "final_answer", "argument": f"[HATA] Gemini: {exc}", "thought": "Hata"})
            return iter([msg]) if stream else msg

    def _stream_gemini_generator(self, response_stream) -> Iterator[str]:
        """Gemini stream yanıtını dönüştürür."""
        try:
            for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            yield json.dumps({"tool": "final_answer", "argument": f"\n[HATA] Gemini akış hatası: {exc}", "thought": "Hata"})

    # ─────────────────────────────────────────────
    #  YARDIMCILAR
    # ─────────────────────────────────────────────

    def list_ollama_models(self) -> List[str]:
        url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/tags"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            models = resp.json().get("models", [])
            return [m["name"] for m in models]
        except Exception:
            return []

    def is_ollama_available(self) -> bool:
        try:
            url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/tags"
            requests.get(url, timeout=5)
            return True
        except Exception:
            return False