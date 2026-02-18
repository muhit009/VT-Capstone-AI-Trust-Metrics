import torch
import numpy as np
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer
from models.schemas import InferenceRequest, InferenceResponse, ConfidenceMetrics

class ModelService:
    def __init__(self, model_id: str):
        self.model_id = model_id
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)
        
        # Load model with bitsandbytes 4-bit quantization
        # This replaces the need for the AWQ library
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            load_in_4bit=True, # bitsandbytes integration
            torch_dtype=torch.float16,
            trust_remote_code=True
        )

        # Initialize pipeline
        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer
        )

    def generate(self, payload: InferenceRequest) -> InferenceResponse:
        # We use generate_kwargs to extract probabilities for confidence
        generate_kwargs = {
            "max_new_tokens": payload.max_new_tokens,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "return_dict_in_generate": True,
            "output_scores": True,
            "do_sample": True if payload.temperature > 0 else False
        }

        # Run inference
        outputs = self.model.generate(
            **self.tokenizer(payload.prompt, return_tensors="pt").to(self.model.device),
            **generate_kwargs
        )

        # Extract generated tokens (excluding the prompt)
        prompt_length = self.tokenizer(payload.prompt, return_tensors="pt").input_ids.shape[1]
        generated_tokens = outputs.sequences[0][prompt_length:]
        generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

        # --- CALCULATE ACTUAL CONFIDENCE SCORE ---
        # compute_transition_scores gives us the log-probabilities of the chosen tokens
        transition_scores = self.model.compute_transition_scores(
            outputs.sequences, outputs.scores, normalize_logits=True
        )
        
        # Convert log-probs to probabilities and take the mean
        # log_prob to probability: exp(score)
        probs = torch.exp(transition_scores[0])
        mean_confidence = torch.mean(probs).item()
        # ------------------------------------------

        return InferenceResponse(
            model_name=self.model_id,
            generated_text=generated_text,
            confidence=ConfidenceMetrics(
                score=round(mean_confidence, 4),
                method="mean_token_probability",
                explanation="Arithmetic mean of softmax probabilities for all generated tokens."
            ),
            metadata={
                "device": str(self.model.device),
                "quantization": "bitsandbytes-4bit",
                "token_count": len(generated_tokens)
            }
        )

# Instantiate as a singleton
model_executor = ModelService("Qwen/Qwen3-4B")