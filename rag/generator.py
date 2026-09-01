import json
import logging
import urllib.request
import urllib.error
from config import LLM_MODEL, OLLAMA_BASE_URL, LLM_TIMEOUT

logger = logging.getLogger(__name__)

class OllamaGenerator:
    """
    Handles communication with the local Ollama backend.
    """
    
    def __init__(self, model_name: str = LLM_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.default_model_name = model_name
        self.base_url = base_url.rstrip("/")
        
    def check_health(self) -> bool:
        """
        Check if Ollama is running and accessible.
        """
        try:
            req = urllib.request.Request(self.base_url)
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
            
    def generate(self, system_prompt: str, user_prompt: str, model_name: str = None, return_usage: bool = False):
        """
        Generates a response from the LLM.
        """
        if not self.check_health():
            raise ConnectionError(
                f"Ollama is unavailable at {self.base_url}. Please ensure Ollama is running locally."
            )
            
        actual_model = model_name or self.default_model_name
        endpoint = f"{self.base_url}/api/generate"
        
        payload = {
            "model": actual_model,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": 0.0, # Strict deterministic answering
                "top_p": 0.9,
                "num_predict": 250 # Limit output length
            }
        }
        
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
        
        try:
            logger.info(f"Generating response using model {actual_model}...")
            with urllib.request.urlopen(req, timeout=LLM_TIMEOUT) as response:
                result = json.loads(response.read().decode("utf-8"))
                ans = result.get("response", "")
                if return_usage:
                    usage = {
                        "prompt_tokens": result.get("prompt_eval_count", 0),
                        "completion_tokens": result.get("eval_count", 0),
                        "total_tokens": result.get("prompt_eval_count", 0) + result.get("eval_count", 0)
                    }
                    return ans, usage
                return ans
        except urllib.error.URLError as e:
            logger.error(f"Error communicating with Ollama: {e}")
            raise ConnectionError(f"Failed to generate response: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Ollama response: {e}")
            raise ValueError(f"Invalid response from Ollama: {e}")
