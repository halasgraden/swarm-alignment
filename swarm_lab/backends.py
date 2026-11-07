"""Backend construction shared by single-run and batch entry points."""
def make_policy(inference):
    backend=inference.get('backend','ollama')
    if backend=='openrouter':
        from .openrouter import OpenRouterPolicy
        return OpenRouterPolicy(inference['model'],temperature=inference.get('temperature',0.6),
            timeout=inference.get('timeout',600),num_predict=inference.get('num_predict') or 8192,
            provider=inference.get('provider'),reasoning=inference.get('think',True))
    if backend=='ollama':
        from .ollama import OllamaPolicy
        return OllamaPolicy(inference['model'],url=inference.get('url','http://127.0.0.1:11434'),
            temperature=inference.get('temperature',0.6),timeout=inference.get('timeout',600),
            think=inference.get('think'),num_predict=inference.get('num_predict'),num_ctx=inference.get('context_length'))
    raise ValueError(f'Unknown backend: {backend}')
