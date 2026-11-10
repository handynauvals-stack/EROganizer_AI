"""
Pembantu lintas-model: penanda giliran asisten (untuk loss masking) dan token berhenti (EOS),
DITURUNKAN dari chat template model, bukan ditulis tangan untuk Qwen/ChatML.

  detect_markers(tok) -> (START, END)   Qwen/ChatML: ("<|im_start|>assistant\\n", "<|im_end|>")
                                         Llama-3:     ("<|start_header_id|>assistant<|end_header_id|>\\n\\n", "<|eot_id|>")
                                         Gemma:       ("<start_of_turn>model\\n", "<end_of_turn>")
  eos_ids(tok, model)   -> daftar id token berhenti untuk generate()

Template tanpa "generation prompt" (mis. Mistral lama) tidak bisa dideteksi otomatis: beri --assistant-start/--assistant-end pada train.py.
"""


def detect_markers(tok):
    user = [{"role": "user", "content": "U"}]
    base = tok.apply_chat_template(user, tokenize=False)
    gen = tok.apply_chat_template(user, tokenize=False, add_generation_prompt=True)
    full = tok.apply_chat_template(user + [{"role": "assistant", "content": "AAAA"}], tokenize=False)
    start = gen[len(base):] if gen.startswith(base) else ""
    end = full[full.index("AAAA") + 4:].strip() if "AAAA" in full else ""
    return start, end


def eos_ids(tok, model=None):
    ids = []
    e = getattr(getattr(model, "generation_config", None), "eos_token_id", None)
    for x in ([e] if isinstance(e, int) else (e or [])):
        ids.append(int(x))
    if tok.eos_token_id is not None:
        ids.append(int(tok.eos_token_id))
    _, end = detect_markers(tok)  # penutup giliran asisten: <|im_end|>, <|eot_id|>, <end_of_turn>, ...
    tid = tok.convert_tokens_to_ids(end) if end else None
    if isinstance(tid, int) and tid >= 0 and tid != tok.unk_token_id:
        ids.append(tid)
    return sorted(set(ids))
