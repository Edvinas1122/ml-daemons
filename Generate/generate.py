#!/usr/bin/env python3
"""SDXL image generation — one-shot. Loads model, generates, unloads."""

import argparse
import os
import sys
import time
from datetime import datetime

import torch
from diffusers import StableDiffusionXLPipeline


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", nargs="+")
    parser.add_argument("--output", default="output")
    parser.add_argument("--steps", type=int, default=25)
    parser.add_argument("--negative", default="blurry, low quality, ugly")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    os.makedirs(args.output, exist_ok=True)

    t0 = time.time()

    pipe = StableDiffusionXLPipeline.from_pretrained(
        "stabilityai/stable-diffusion-xl-base-1.0",
        torch_dtype=torch.float16,
        use_safetensors=True,
        variant="fp16",
    )
    pipe.enable_model_cpu_offload()
    pipe.enable_vae_slicing()
    pipe.enable_vae_tiling()

    print(f"Model loaded in {time.time() - t0:.1f}s", flush=True)

    t1 = time.time()
    image = pipe(
        prompt=prompt,
        negative_prompt=args.negative,
        num_inference_steps=args.steps,
    ).images[0]
    print(f"Inference in {time.time() - t1:.1f}s", flush=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe = "".join(c if c.isalnum() or c in " _-" else "_" for c in prompt)[:60]
    filename = f"{ts}_{safe}.png"
    path = os.path.join(args.output, filename)
    image.save(path)

    total = time.time() - t0
    print(f"Saved: {path}  ({total:.1f}s total)", flush=True)


if __name__ == "__main__":
    main()
