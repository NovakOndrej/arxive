import os, time, re, requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")

# Strip any leaked "thinking" blocks and keep the final answer
REASONING = re.compile(r"<think>.*?</think>", re.I | re.S)
def clean(text: str) -> str:
    if not text: return ""
    # keep only the tail after the last </think>, then remove any leftover blocks
    tail = text.split("</think>")[-1]
    return REASONING.sub("", tail).strip() or text.strip()

BASE_OPTIONS = {"temperature": 0.2, "top_p": 0.9, "num_predict": 100, "num_ctx": 1024, "seed": 42}

SYSTEM_LIST = (
  "You are a scientific assistant. Extract only the novel contributions of a research abstract. "
  "Output MUST be a single line starting with 'Novelty:' followed by a comma-separated list of short noun phrases (3–8 words). "
  "Third-person; no background/applications/future work; preserve numerics; no <think>."
)

def summarize_novelty_list(abstract: str, model: str = "gemma3:1b") -> str:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_LIST},
            {"role": "user", "content": f"Abstract:\n{abstract}\n"},
        ],
        "options": BASE_OPTIONS,
        "stream": False,
        "keep_alive": "1h",  # keep model hot
    }
    r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
    if r.status_code == 404:  # fallback for servers without /api/chat
        r = requests.post(f"{OLLAMA_URL}/api/generate",
                          json={"model": model, "prompt": SYSTEM_LIST + "\n\nAbstract:\n" + abstract,
                                "options": BASE_OPTIONS, "stream": False, "keep_alive": "1h"}, timeout=600)
    r.raise_for_status()
    data = r.json()
    text = (data.get("message", {}) or {}).get("content") or data.get("response", "")
    return clean(text)

if __name__ == "__main__":
    t = time.time()
    print(summarize_novelty_list(" Topological photonics offers a robust platform for controlling light, with applications such as backscattering-immune edge transport and slow-light propagation. In this work, we present a comprehensive and automated framework for the design and characterization of symmetry-protected interface modes in two-dimensional photonic crystals. The main tool in our approach is an iterative band connection algorithm that ensures symmetry consistency across the Brillouin zone, enabling reliable reconstruc- tion of photonic bands even near degeneracies. Complementing this, we introduce a data-driven symmetry classification method that constructs comparator functions directly from eigenmode data, removing the need for predefined symmetry operations or irreducible representations. These tools are particularly suited for generative or parametrized geometries where symmetries may vary. Using this framework, we identify example structures exhibiting obstructed atomic limits, characterized by Wannier center displacements and mode inversions. We analyze the trade-offs between interface mode dispersion and bulk bandgap size and show how the number of photonic crystal periods at the interface governs the emergence and robustness of topological modes. Finally, we demonstrate the scalability of our approach across material platforms and operating wavelengths, including the telecommu- nication range. These contributions enable physically grounded and fully automated design of topological photonic interfaces, paving the way for large-scale exploration and optimization of complex photonic structures."))
    print(f"[timing] wall={time.time() - t:.3f}s")