"""
EROganizer - layanan inferensi chatbot (Qwen2.5-0.5B-Instruct + adapter LoRA hasil training).

Layanan ini HANYA dipanggil oleh Laravel (bind ke 127.0.0.1), bukan oleh browser.
Laravel yang menangani login, CSRF, pembatasan permintaan, menyusun system prompt, dan MENJALANKAN tool call
ke database (model hanya mengusulkan tool call; hasilnya dikirim balik sebagai pesan role "tool").

Jalankan:  run_server.bat   (atau: venv\\Scripts\\python.exe -m uvicorn server:app --host 127.0.0.1 --port 8001)

Variabel lingkungan:
  CHATBOT_ADAPTER_DIR  folder adapter LoRA (default: adapter hasil training terbaru di training/output/*/adapter; run_server.bat memakai RUN_NAME dari config.bat). Isi "none" untuk model dasar tanpa adapter.
  CHATBOT_MODEL_DIR    folder model dasar
  CHATBOT_DEVICE       "cpu" atau "cuda"
"""

import os
import sys
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Literal

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent / "training" / "scripts"))
from modelutil import eos_ids  # noqa: E402  (token berhenti diturunkan dari model/template, bukan ditulis untuk Qwen)

BASE_DIR = Path(__file__).resolve().parent
MODEL_DIR = Path(os.environ.get("CHATBOT_MODEL_DIR", BASE_DIR / "models" / "Qwen2.5-0.5B-Instruct"))
def _default_adapter() -> str:
    """Tanpa CHATBOT_ADAPTER_DIR: pakai adapter hasil training yang paling baru (training/output/*/adapter)."""
    found = sorted((BASE_DIR / "training" / "output").glob("*/adapter/adapter_config.json"), key=lambda p: p.stat().st_mtime)
    return str(found[-1].parent) if found else str(BASE_DIR / "training" / "output" / "(belum-ada)" / "adapter")


ADAPTER_ENV = os.environ.get("CHATBOT_ADAPTER_DIR", _default_adapter())
ADAPTER_DIR = None if ADAPTER_ENV.strip().lower() in ("", "none") else Path(ADAPTER_ENV)


def pick_device() -> str:
    """Pakai GPU bila benar-benar bisa dipakai; kalau tidak, jatuh ke CPU."""
    forced = os.environ.get("CHATBOT_DEVICE")  # opsional: "cpu" atau "cuda"
    if forced:
        return forced
    if torch.cuda.is_available():
        try:
            torch.zeros(1, device="cuda")
            return "cuda"
        except Exception as exc:  # GPU terdeteksi tetapi tidak bisa dialokasikan
            print(f"[chatbot] GPU tidak bisa dipakai ({str(exc).splitlines()[0]}); memakai CPU")
    return "cpu"


DEVICE = pick_device()
DTYPE = torch.bfloat16 if DEVICE == "cuda" else torch.float32

MAX_INPUT_TOKENS = 4096  # batas konteks yang dikirim ke model (riwayat lama dibuang bila lebih)

state = {}
generate_lock = threading.Lock()  # satu model, satu generasi pada satu waktu


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not MODEL_DIR.exists():
        raise RuntimeError(f"Folder model tidak ditemukan: {MODEL_DIR}\nJalankan download_model.bat dulu (atau set CHATBOT_MODEL_DIR).")
    started = time.time()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
    model = AutoModelForCausalLM.from_pretrained(MODEL_DIR, dtype=DTYPE)
    model.to(DEVICE)
    if ADAPTER_DIR is not None:
        # Gagal keras (bukan diam-diam kembali ke model dasar): model dasar tanpa adapter tidak mengenal protokol tool call.
        if not ADAPTER_DIR.exists():
            raise RuntimeError(f"Adapter belum ada: {ADAPTER_DIR}\nLatih dulu dengan train.bat, atau set RUN_NAME di config.local.bat ke nama training yang sudah ada.\n(CHATBOT_ADAPTER_DIR=none menjalankan model dasar tanpa adapter, TANPA kemampuan tool call.)")
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, str(ADAPTER_DIR)).merge_and_unload()
    model.eval()
    state["tokenizer"] = tokenizer
    state["model"] = model
    state["eos"] = eos_ids(tokenizer, model)
    state["loaded_in"] = round(time.time() - started, 1)
    print(f"[chatbot] model dimuat dari {MODEL_DIR} + adapter={ADAPTER_DIR} ke {DEVICE} dalam {state['loaded_in']} detik")
    yield
    state.clear()


app = FastAPI(title="EROganizer Chatbot", lifespan=lifespan)


class Message(BaseModel):
    # "tool" = hasil eksekusi tool call dari Laravel (dirender oleh chat template Qwen sebagai <tool_response>)
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    messages: List[Message] = Field(min_length=1, max_length=30)
    max_new_tokens: int = Field(default=400, ge=16, le=512)
    # 0 = greedy (sama seperti saat evaluasi). Sampling bisa merusak JSON tool call.
    temperature: float = Field(default=0.0, ge=0.0, le=1.5)


class ChatResponse(BaseModel):
    reply: str
    new_tokens: int
    elapsed_ms: int
    device: str


@app.get("/health")
def health():
    return {
        "status": "ok" if "model" in state else "loading",
        "model": MODEL_DIR.name,
        "adapter": ADAPTER_DIR.parent.name if ADAPTER_DIR is not None else None,
        "device": DEVICE,
        "loaded_in_s": state.get("loaded_in"),
    }


def build_inputs(messages: List[Message]):
    tokenizer = state["tokenizer"]
    items = [{"role": m.role, "content": m.content} for m in messages]

    while True:
        text = tokenizer.apply_chat_template(items, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt")
        if inputs["input_ids"].shape[1] <= MAX_INPUT_TOKENS:
            return inputs
        # buang pesan non-system paling lama sampai muat (sisakan pesan terakhir)
        drop = next((i for i, m in enumerate(items[:-1]) if m["role"] != "system"), None)
        if drop is None:
            raise HTTPException(status_code=413, detail="Pesan terlalu panjang.")
        items.pop(drop)


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if "model" not in state:
        raise HTTPException(status_code=503, detail="Model belum siap.")

    model = state["model"]
    tokenizer = state["tokenizer"]
    inputs = build_inputs(req.messages).to(DEVICE)

    gen_kwargs = dict(
        max_new_tokens=req.max_new_tokens,
        repetition_penalty=1.0,  # >1 menghukum token yang berulang (angka jam, tanda kutip) dan merusak JSON
        eos_token_id=state["eos"],
        pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
    )
    if req.temperature > 0:
        gen_kwargs.update(do_sample=True, temperature=req.temperature, top_p=0.9, top_k=40)
    else:
        gen_kwargs.update(do_sample=False)

    started = time.time()
    with generate_lock, torch.inference_mode():
        output = model.generate(**inputs, **gen_kwargs)

    new_ids = output[0][inputs["input_ids"].shape[1]:]
    reply = tokenizer.decode(new_ids, skip_special_tokens=True).strip()
    return ChatResponse(
        reply=reply,
        new_tokens=int(new_ids.shape[0]),
        elapsed_ms=int((time.time() - started) * 1000),
        device=DEVICE,
    )
