#!/bin/bash
#SBATCH --job-name=vllm-server
#SBATCH --account=muataz
#SBATCH --partition=l40s_normal_q
#SBATCH --nodes=1
#SBATCH --gres=gpu:1
#SBATCH --mem=64G
#SBATCH --time=72:00:00
#SBATCH --output=/projects/meng/group23/logs/vllm_server_%j.log

source /projects/meng/group23/envs/venv/bin/activate
export HF_HOME=/projects/meng/group23/models/hf_cache

vllm serve /common/data/models/mistralai--Mistral-Small-3.1-24B-Instruct-2503 --port 8000 --max-model-len 8192 --served-model-name mistral-small-24b --quantization fp8