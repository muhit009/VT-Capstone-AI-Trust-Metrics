# VT ARC HPC Setup Guide — GroundCheck Confidence Engine

**Document ID:** `hpc_setup_guide.md`
**Version:** 1.0
**Authors:** Confidence Engine (Xuhui & Muhit)
**Last Updated:** 2026-03-18
**Cluster:** VT ARC (Falcon + TinkerCliffs)
**Project:** GroundCheck — RAG Confidence Scoring for Boeing Engineering Documents

---

## Table of Contents

1. [Before You Start](#1-before-you-start)
2. [Step 1 — Connect to VT VPN](#2-step-1--connect-to-vt-vpn)
3. [Step 2 — Find Your Allocation Name](#3-step-2--find-your-allocation-name)
4. [Step 3 — SSH Into the Cluster](#4-step-3--ssh-into-the-cluster)
5. [Step 4 — Understand Storage](#5-step-4--understand-storage)
6. [Step 5 — Choose Your Cluster and GPU](#6-step-5--choose-your-cluster-and-gpu)
7. [Step 6 — Set Up Your Python Environment](#7-step-6--set-up-your-python-environment)
8. [Step 7 — Get the LLM Model](#8-step-7--get-the-llm-model)
9. [Step 8 — Transfer Your Code](#9-step-8--transfer-your-code)
10. [Step 9 — Run a Test Inference](#10-step-9--run-a-test-inference)
11. [Step 10 — Submit a Batch Job](#11-step-10--submit-a-batch-job)
12. [Quick Reference](#12-quick-reference)

---

## 1. Before You Start

You need three things before touching any cluster:

- [ ] VT PID and password (test at https://onecampus.vt.edu — if it fails, your password is expired)
- [ ] VT VPN connected (mandatory for all ARC access from off-campus)
- [ ] Your allocation name from ColdFront (https://coldfront.arc.vt.edu)

**Important warnings from ARC:**
- **Do NOT put Boeing data on ARC** — use the CUI cluster only for ITAR/export-controlled data
- **Do NOT run code on login nodes** — submit all jobs through Slurm or `interact`
- **Do NOT store models in your home directory** — use your project folder or scratch

---

## 2. Step 1 — Connect to VT VPN

You cannot access any ARC system without the VT VPN. Every time you want to use ARC, connect to VPN first.

1. Download the VT Cisco AnyConnect VPN client if you don't have it
2. Connect to `vpn.vt.edu`
3. Login with your VT PID and password + 2FA (Duo)

---

## 3. Step 2 — Find Your Allocation Name

1. Go to https://coldfront.arc.vt.edu
2. Login with your VT PID
3. Click **Allocations** in the left sidebar
4. You will see an allocation under **Professor Boker's PI account**
5. Note down the **Allocation Name** — you will need it for every Slurm command

It will look something like: `boker_lab` or `arc-boker` — the exact name is on ColdFront.

---

## 4. Step 3 — SSH Into the Cluster

**Option A — Web browser (easiest, no setup needed):**

Go to https://ood.arc.vt.edu → click **Clusters** → **Falcon Shell Access** or **TinkerCliffs Shell Access**

**Option B — Terminal SSH:**

```bash
# For Falcon (15B–30B models, L40S/A30 GPUs)
ssh <your-pid>@falcon1.arc.vt.edu

# For TinkerCliffs (70B models, A100/H200 GPUs)
ssh <your-pid>@tinkercliffs1.arc.vt.edu
```

Replace `<your-pid>` with your actual VT PID (e.g., `abdulm`).

You are now on the **login node**. Do not run any compute here.

---

## 5. Step 4 — Understand Storage

There are three storage locations. Know the difference before you put anything anywhere.

| Location | Path | Quota | Use For |
|---|---|---|---|
| Home | `/home/<your-pid>/` | 640 GB | Code, configs, small files |
| Project | `/projects/<allocation>/` | Large | Models, environments, datasets |
| Scratch | `/scratch/<your-pid>/` | Large, **NOT backed up** | Temporary output files |

**Check your project path:**
```bash
ls /projects/
# Look for a folder matching your allocation name
```

**Set up your working folders right now:**
```bash
mkdir -p /projects/<allocation>/groundcheck
mkdir -p /projects/<allocation>/groundcheck/models
mkdir -p /projects/<allocation>/groundcheck/envs
mkdir -p /projects/<allocation>/groundcheck/outputs
```

**Set HuggingFace cache to project folder** (add to `~/.bashrc` so it persists):
```bash
echo 'export HF_HOME=/projects/<allocation>/groundcheck/models/hf_cache' >> ~/.bashrc
echo 'export TRANSFORMERS_CACHE=/projects/<allocation>/groundcheck/models/hf_cache' >> ~/.bashrc
source ~/.bashrc
```

This prevents the DeBERTa NLI model from eating your home quota.

---

## 6. Step 5 — Choose Your Cluster and GPU

Pick based on which model you want to run:

| Model | Size | Min VRAM | Cluster | Partition | GPU |
|---|---|---|---|---|---|
| `mistral:7b-instruct` (current) | 7B | 8 GB (4-bit) | Falcon | `a30_normal_q` | A30 24 GB |
| `qwen2.5:32b` (recommended) | 32B | 18 GB (4-bit) | Falcon | `l40s_normal_q` | L40S 48 GB |
| `llama3.3:70b` (stretch goal) | 70B | 40 GB (4-bit) | TinkerCliffs | `a100_normal_q` | A100 80 GB |

**Recommendation for development and validation:** start on **Falcon L40S** with `qwen2.5:32b`.

> **NLI model note:** `cross-encoder/nli-deberta-v3-small` runs on CPU — no GPU needed for it. Request 1 CPU core alongside your GPU allocation.

**SU cost per hour** (so you don't burn through your monthly 1M SUs):

| GPU | SU/hour | Notes |
|---|---|---|
| A30 | 75 | Fine for 7B testing |
| L40S | 75 | Best value for 32B |
| A100 | 100 | Use for 70B |
| H200 | 150 | Only if A100 is unavailable |

---

## 7. Step 6 — Set Up Your Python Environment

You must do this **inside an interactive session on the correct node type** — not on the login node. Environments are not portable between node types.

**Get an interactive session first:**

```bash
# For Falcon L40S (recommended — for qwen2.5:32b)
interact -A <allocation> -t 1:00:00 -p l40s_normal_q -n 1 --gres=gpu:1

# For Falcon A30 (for mistral:7b testing)
interact -A <allocation> -t 1:00:00 -p a30_normal_q -n 1 --gres=gpu:1

# For TinkerCliffs A100 (for llama3.3:70b)
interact -A <allocation> -t 1:00:00 -p a100_normal_q -n 1 --gres=gpu:1
```

Wait for the prompt to change — you are now on a compute node.

**Load Miniconda and create the environment:**

```bash
module load Miniconda3

conda create -p /projects/<allocation>/groundcheck/envs/groundcheck python=3.11 pip -y
source activate /projects/<allocation>/groundcheck/envs/groundcheck
```

**Install GroundCheck dependencies:**

```bash
# Core ML dependencies
pip install torch --index-url https://download.pytorch.org/whl/cu121
pip install sentence-transformers
pip install nltk
pip install numpy
pip install httpx

# Download NLTK punkt tokenizer (needed by grounding scorer)
python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab')"

# Test the install
python -c "import torch; print('CUDA available:', torch.cuda.is_available())"
```

**Exit the interactive session when done:**
```bash
exit
```

---

## 8. Step 7 — Get the LLM Model

For this project the LLM runs through **Ollama**. Install it in your project folder.

**Step 7a — Check /common/data/models/ first**

ARC maintains pre-downloaded models. Always check here before downloading anything:

```bash
ls /common/data/models/
# Look for: mistral, qwen, llama, ollama
```

If your model is already there, you can point Ollama to it directly (saves time and quota).

**Step 7b — Install Ollama to project folder**

Ollama must be installed to your project folder (not home, to avoid quota issues):

```bash
# Start an interactive session first
interact -A <allocation> -t 1:00:00 -p l40s_normal_q -n 1 --gres=gpu:1

# Set Ollama home to project folder
export OLLAMA_HOME=/projects/<allocation>/groundcheck/models/ollama

# Download and install Ollama
curl -fsSL https://ollama.com/install.sh | OLLAMA_HOME=$OLLAMA_HOME sh

# Add to ~/.bashrc so it persists across sessions
echo 'export OLLAMA_HOME=/projects/<allocation>/groundcheck/models/ollama' >> ~/.bashrc
echo 'export PATH=$OLLAMA_HOME/bin:$PATH' >> ~/.bashrc
source ~/.bashrc
```

**Step 7c — Pull your model**

```bash
# Start Ollama server in background
ollama serve &
sleep 5

# Pull your chosen model (this will take a few minutes)
ollama pull qwen2.5:32b        # recommended — 18GB download
# OR
ollama pull mistral:7b-instruct  # current dev model — 4GB download
# OR (stretch goal, needs A100)
ollama pull llama3.3:70b        # 40GB download

# Verify it's there
ollama list
```

---

## 9. Step 8 — Transfer Your Code

From your **local machine** (not on HPC), transfer the confidence-develop repo to your project folder.

**Option A — rsync (recommended, resumes if interrupted):**

```bash
# Run this from your LOCAL machine
rsync -avz --exclude='venv/' --exclude='.git/' \
  "C:/Users/Abdul/OneDrive/Desktop/VT-Capstone/confidence-develop/" \
  <your-pid>@datatransfer.arc.vt.edu:/projects/<allocation>/groundcheck/confidence-develop/
```

**Option B — scp:**

```bash
# Run this from your LOCAL machine
scp -r "C:/Users/Abdul/OneDrive/Desktop/VT-Capstone/confidence-develop" \
  <your-pid>@datatransfer.arc.vt.edu:/projects/<allocation>/groundcheck/
```

**Option C — Git clone (if repo is on GitHub):**

```bash
# On the HPC login node
cd /projects/<allocation>/groundcheck/
git clone https://github.com/muhit009/VT-Capstone-AI-Trust-Metrics confidence-develop
cd confidence-develop
git checkout confidence-develop
```

---

## 10. Step 9 — Run a Test Inference

This is the validation run from `signal2_results_and_hpc.md` — confirms logprobs work and normalization constants are correct.

**Get an interactive GPU session:**

```bash
interact -A <allocation> -t 1:00:00 -p l40s_normal_q -n 1 --gres=gpu:1
```

**Activate environment and start Ollama:**

```bash
source activate /projects/<allocation>/groundcheck/envs/groundcheck
export OLLAMA_HOME=/projects/<allocation>/groundcheck/models/ollama
export PATH=$OLLAMA_HOME/bin:$PATH

ollama serve &
sleep 5
```

**Run the normalization validation script:**

```bash
cd /projects/<allocation>/groundcheck/confidence-develop
python dev/local_pipeline.py "What is the purpose of a Preliminary Design Review?"
```

**Run the full normalization validation (10 queries — records raw_mean_prob range):**

```bash
python - <<'EOF'
import sys, math
sys.path.insert(0, ".")
from confidence.generation_confidence import generation_confidence_scorer
from confidence.ollama_client import generate

TEST_QUERIES = [
    "What is the purpose of a Preliminary Design Review?",
    "What are the structural load requirements for launch vehicles?",
    "Define systems engineering according to NASA.",
    "What is specific impulse and why does it matter?",
    "What propellant types are used in rockets?",
    "When is range safety approval required?",
    "What is the allocated baseline established at PDR?",
    "How does liquid propellant compare to solid propellant?",
    "What is the systems engineering lifecycle?",
    "What constitutes a system according to the NASA handbook?",
]

raw_means = []
for query in TEST_QUERIES:
    result = generate(f"[INST] {query} [/INST]")
    gen = generation_confidence_scorer.from_ollama(result)
    raw_means.append(gen.raw_mean_prob)
    print(f"raw_mean={gen.raw_mean_prob:.4f}  level={gen.level}  tokens={gen.num_tokens}  filtered={gen.num_filtered}")
    print(f"  Q: {query[:60]}")

print(f"\nMin  : {min(raw_means):.4f}")
print(f"Max  : {max(raw_means):.4f}")
print(f"Mean : {sum(raw_means)/len(raw_means):.4f}")
print(f"\nCurrent config: GEN_CONF_RAW_MIN=0.3, GEN_CONF_RAW_MAX=0.9")
if min(raw_means) < 0.3:
    print(f"ACTION NEEDED: update GEN_CONF_RAW_MIN to {min(raw_means):.2f} in config.py")
if max(raw_means) > 0.9:
    print(f"ACTION NEEDED: update GEN_CONF_RAW_MAX to {max(raw_means):.2f} in config.py")
else:
    print("Normalization range [0.3, 0.9] validated — no config change needed")
EOF
```

**Exit when done:**
```bash
exit
```

---

## 11. Step 10 — Submit a Batch Job

For longer validation runs (more queries, different models), use `sbatch` instead of `interact`.

**Create a Slurm batch script** at `/projects/<allocation>/groundcheck/run_pipeline.sh`:

```bash
#!/bin/bash
#SBATCH --job-name=groundcheck
#SBATCH --account=<allocation>
#SBATCH --partition=l40s_normal_q
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=01:00:00
#SBATCH --output=/projects/<allocation>/groundcheck/outputs/%j.out
#SBATCH --error=/projects/<allocation>/groundcheck/outputs/%j.err

# Load environment
module load Miniconda3
source activate /projects/<allocation>/groundcheck/envs/groundcheck

# Set paths
export OLLAMA_HOME=/projects/<allocation>/groundcheck/models/ollama
export PATH=$OLLAMA_HOME/bin:$PATH
export HF_HOME=/projects/<allocation>/groundcheck/models/hf_cache
export TRANSFORMERS_CACHE=$HF_HOME

# Start Ollama
ollama serve &
sleep 10

# Run pipeline
cd /projects/<allocation>/groundcheck/confidence-develop
python dev/local_pipeline.py "What is the purpose of a Preliminary Design Review?"

# Monitor GPU usage (logged to separate file)
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used,memory.total \
  --format=csv -l 5 > /projects/<allocation>/groundcheck/outputs/$SLURM_JOBID.gpu.log &
```

**Submit the job:**
```bash
sbatch /projects/<allocation>/groundcheck/run_pipeline.sh
```

**Monitor it:**
```bash
squeue -u <your-pid>          # check status
tail -f outputs/<jobid>.out   # live output
jobload <jobid>               # CPU/memory usage
```

---

## 12. Quick Reference

**Interactive session commands:**

```bash
# Falcon L40S (32B model — recommended)
interact -A <allocation> -t 2:00:00 -p l40s_normal_q -n 1 --gres=gpu:1

# Falcon A30 (7B model — testing)
interact -A <allocation> -t 2:00:00 -p a30_normal_q -n 1 --gres=gpu:1

# TinkerCliffs A100 (70B stretch goal)
interact -A <allocation> -t 2:00:00 -p a100_normal_q -n 1 --gres=gpu:1
```

**Activate environment:**
```bash
module load Miniconda3
source activate /projects/<allocation>/groundcheck/envs/groundcheck
```

**Check your SU balance:**
```bash
sacct -X -o jobID,partition%20,AllocTRES%70 | tail -20
```

**Check disk quota:**
```bash
quota
```

**Check what models are pre-downloaded on ARC:**
```bash
ls /common/data/models/
```

**Kill an interactive session:**
```bash
exit    # always do this — don't leave idle sessions running
```

---

## Checklist Summary

- [ ] VT VPN connected
- [ ] Allocation name found on ColdFront
- [ ] SSH into cluster (OOD or terminal)
- [ ] Project folder structure created under `/projects/<allocation>/groundcheck/`
- [ ] HF_HOME and TRANSFORMERS_CACHE set in `~/.bashrc`
- [ ] Interactive session started on correct GPU node type
- [ ] Conda environment created at `/projects/<allocation>/groundcheck/envs/groundcheck`
- [ ] All dependencies installed (torch, sentence-transformers, nltk, numpy, httpx)
- [ ] Ollama installed to project folder
- [ ] Model pulled (`qwen2.5:32b` or `mistral:7b-instruct`)
- [ ] Code transferred (rsync / scp / git clone)
- [ ] `dev/local_pipeline.py` runs end-to-end
- [ ] Normalization validation script run — `raw_mean_prob` range recorded
- [ ] `config.py` updated if range falls outside [0.3, 0.9]

---

*End of Document — hpc_setup_guide.md v1.0*
