"""
Sidar Project - LLM İstemcisi
Ollama ve Google Gemini API entegrasyonu (Asenkron).
"""

import json
import logging
from typing import List, Dict, Optional, AsyncIterator, Union

import httpx

logger = logging.getLogger(__name__)


class LLMClient:
    """Ollama veya Gemini üzerinden asenkron LLM çağrıları yapar."""

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

    async def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        stream: bool = False,
        json_mode: bool = True,
    ) -> Union[str, AsyncIterator[str]]:
        """
        Sohbet tamamlama isteği gönder (Asenkron).

        Args:
            stream   : True ise yanıt parça parça (AsyncIterator) döner.
            json_mode: True ise modeli JSON çıktıya zorlar (ReAct döngüsü için).
                       Özetleme gibi düz metin gereken çağrılarda False geçin.
        """
        if system_prompt:
            messages = [{"role": "system", "content": system_prompt}] + list(messages)

        if self.provider == "ollama":
            return await self._ollama_chat(messages, model or self.config.CODING_MODEL, temperature, stream, json_mode)
        elif self.provider == "gemini":
            return await self._gemini_chat(messages, temperature, stream, json_mode)
        else:
            raise ValueError(f"Bilinmeyen AI sağlayıcısı: {self.provider}")

    # ─────────────────────────────────────────────
    #  OLLAMA (ASYNC)
    # ─────────────────────────────────────────────

    async def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        stream: bool,
        json_mode: bool = True,
    ) -> Union[str, AsyncIterator[str]]:
        url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/chat"

        # Ollama options: GPU katman sayısını ilet (USE_GPU=true ise)
        options: dict = {"temperature": temperature}
        use_gpu = getattr(self.config, "USE_GPU", False)
        if use_gpu:
            # num_gpu=-1 → Ollama tüm model katmanlarını GPU'ya atar (0 = CPU-only).
            # GPU_DEVICE, hangi cihazın kullanılacağını belirtir; katman sayısını değil.
            options["num_gpu"] = -1

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": options,
        }
        # JSON modu yalnızca ReAct döngüsü için zorunlu; özetleme gibi
        # düz metin gereken çağrılarda atlanır.
        if json_mode:
            payload["format"] = "json"
        
        timeout = getattr(self.config, "OLLAMA_TIMEOUT", 60)
        
        try:
            # STREAM MODU
            if stream:
                return self._stream_ollama_response(url, payload, timeout=timeout)

            # NORMAL MOD
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data.get("message", {}).get("content", "")

        except httpx.ConnectError:
            logger.error("Ollama bağlantı hatası.")
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] Ollama'ya bağlanılamadı. 'ollama serve' açık mı?", "thought": "Hata oluştu."})
            return self._fallback_stream(msg) if stream else msg
        except Exception as exc:
            logger.error("Ollama hata: %s", exc)
            msg = json.dumps({"tool": "final_answer", "argument": f"[HATA] Ollama: {exc}", "thought": "Hata oluştu."})
            return self._fallback_stream(msg) if stream else msg

    async def _stream_ollama_response(self, url: str, payload: dict, timeout: int = 120) -> AsyncIterator[str]:
        """Ollama stream yanıtını parçalar halinde asenkron yield eder."""
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
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
    #  GEMINI (ASYNC)
    # ─────────────────────────────────────────────

    async def _gemini_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        stream: bool,
        json_mode: bool = True,
    ) -> Union[str, AsyncIterator[str]]:
        try:
            import google.generativeai as genai
        except ImportError:
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] 'google-generativeai' kurulu değil.", "thought": "Paket eksik"})
            return self._fallback_stream(msg) if stream else msg

        if not self.config.GEMINI_API_KEY:
            msg = json.dumps({"tool": "final_answer", "argument": "[HATA] GEMINI_API_KEY ayarlanmamış.", "thought": "Key eksik"})
            return self._fallback_stream(msg) if stream else msg

        genai.configure(api_key=self.config.GEMINI_API_KEY)

        # Sistem mesajını ayır
        system_text = ""
        chat_messages = []
        for m in messages:
            if m["role"] == "system":
                system_text = m["content"]
            else:
                chat_messages.append(m)

        gen_config = {"temperature": temperature}
        if json_mode:
            gen_config["response_mime_type"] = "application/json"

        model = genai.GenerativeModel(
            model_name=self.config.GEMINI_MODEL,
            system_instruction=system_text or None,
            generation_config=gen_config,
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
                # Gemini asenkron çağrısı: send_message_async
                response_stream = await chat_session.send_message_async(prompt, stream=True)
                return self._stream_gemini_generator(response_stream)
            else:
                response = await chat_session.send_message_async(prompt)
                return response.text

        except Exception as exc:
            logger.error("Gemini hata: %s", exc)
            msg = json.dumps({"tool": "final_answer", "argument": f"[HATA] Gemini: {exc}", "thought": "Hata"})
            return self._fallback_stream(msg) if stream else msg

    async def _stream_gemini_generator(self, response_stream) -> AsyncIterator[str]:
        """Gemini stream yanıtını asenkron dönüştürür."""
        try:
            async for chunk in response_stream:
                if chunk.text:
                    yield chunk.text
        except Exception as exc:
            yield json.dumps({"tool": "final_answer", "argument": f"\n[HATA] Gemini akış hatası: {exc}", "thought": "Hata"})

    async def _fallback_stream(self, msg: str) -> AsyncIterator[str]:
        """Senkron hata durumlarında asenkron itere edilebilir bir nesne döndürmek için yardımcı."""
        yield msg

    # ─────────────────────────────────────────────
    #  YARDIMCILAR (ASYNC)
    # ─────────────────────────────────────────────

    async def list_ollama_models(self) -> List[str]:
        url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                models = resp.json().get("models", [])
                return [m["name"] for m in models]
        except Exception:
            return []

    async def is_ollama_available(self) -> bool:
        url = f"{self.config.OLLAMA_URL.removesuffix('/api')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.get(url)
                return True
        except Exception:
            return False