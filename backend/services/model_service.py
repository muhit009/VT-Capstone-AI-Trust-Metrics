import torch
import numpy as np
from transformers import pipeline, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from models import db_models
from models.schemas import InferenceRequest, InferenceResponse, ConfidenceMetrics
from models.db_models import Query, Answer, ConfidenceSignal

class ModelService:
    def __init__(self, model_id: str):
        self.model_id = model_id
        
        # Load tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_id, trust_remote_code=True)

        # Create quantization config
        quant_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True
        )
        
        # Load model with bitsandbytes 4-bit quantization
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            device_map="auto",
            quantization_config=quant_config, 
            torch_dtype=torch.float16,
            trust_remote_code=True
        )

        # Initialize pipeline
        self.pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer
        )

    def generate(self, payload: InferenceRequest, db_session) -> InferenceResponse:
        # We use generate_kwargs to extract probabilities for confidence
        generate_kwargs = {
            "max_new_tokens": payload.max_new_tokens,
            "temperature": payload.temperature,
            "top_p": payload.top_p,
            "repetition_penalty": payload.repetition_penalty, 
            "no_repeat_ngram_size": payload.no_repeat_ngram_size,
            "return_dict_in_generate": True,
            "output_scores": True,
            "do_sample": True if payload.temperature > 0 else False,
            "pad_token_id": self.tokenizer.eos_token_id
        }

        # Run inference
        outputs = self.model.generate(
            **self.tokenizer(payload.prompt, return_tensors="pt").to(self.model.device),
            **generate_kwargs
        )

        # Log the query
        db_query = db_models.Query(
            prompt=payload.prompt,
            model_name=self.model_id,
            params={
                "max_new_tokens": payload.max_new_tokens,
                "temperature": payload.temperature,
                "top_p": payload.top_p
            }
        )
        db_session.add(db_query)
        db_session.flush() # Get query ID


        # Extract generated tokens (excluding the prompt)
        prompt_length = self.tokenizer(payload.prompt, return_tensors="pt").input_ids.shape[1]
        generated_tokens = outputs.sequences[0][prompt_length:]
        generated_text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

        # Log the generated text
        db_answer = db_models.Answer(
            query_id=db_query.id,
            generated_text=generated_text,
            metadata_json={
                "device": str(self.model.device),
                "token_count": len(generated_tokens)
            }
        )
        db_session.add(db_answer)
        db_session.flush()

        # Compute the log-probabilities of the chosen tokens
        transition_scores = self.model.compute_transition_scores(
            outputs.sequences, outputs.scores, normalize_logits=True
        )
        
        # Convert log-probs to probabilities and take the mean
        probs = torch.exp(transition_scores[0])
        mean_confidence = torch.mean(probs).item()

        # Log the confidence signal
        db_signal = db_models.ConfidenceSignal(
            answer_id=db_answer.id,
            score=round(mean_confidence, 4),
            method="mean_token_probability",
            explanation="Arithmetic mean of softmax probabilities for all generated tokens."
        )
        db_session.add(db_signal)

        db_session.commit() # Save everything to the DB
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