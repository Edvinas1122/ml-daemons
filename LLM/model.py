import time

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig


def load_engine(model_id, dtype="float16", load_in_4bit=True):
    """Load LLM model + tokenizer. Returns (model, tokenizer)."""
    print(f"Loading model: {model_id}", flush=True)
    t0 = time.time()

    torch_dtype = getattr(torch, dtype)

    if load_in_4bit:
        bnb = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch_dtype,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            quantization_config=bnb,
            device_map="auto",
            torch_dtype=torch_dtype,
        )
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            torch_dtype=torch_dtype,
        )

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    print(f"Loaded in {time.time() - t0:.1f}s", flush=True)
    return model, tokenizer
