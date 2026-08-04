# backend/scripts/train_whisper_lora.py
import os
import re
import sys
import logging
import torch
import pandas as pd
from typing import Any, Dict, List, Union
from dataclasses import dataclass
from datasets import Dataset, Audio
from transformers import (
    WhisperFeatureExtractor,
    WhisperTokenizer,
    WhisperProcessor,
    WhisperForConditionalGeneration,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer
)
from peft import LoraConfig, get_peft_model

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # 1. Setup paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    training_dir = os.path.join(base_dir, "data", "training")
    meta_csv = os.path.join(training_dir, "metadata.csv")
    audio_dir = os.path.join(training_dir, "audio")
    
    if not os.path.exists(meta_csv):
        logging.error(f"Metadata file not found at: {meta_csv}")
        sys.exit(1)
        
    logging.info("Loading metadata and preparing datasets...")
    df = pd.read_csv(meta_csv)
    df['audio'] = audio_dir + "/" + df['file_name']
    df['sentence'] = df['verified_transcript']
    
    # Drop rows missing audio files
    df = df[df['audio'].apply(os.path.exists)]
    if len(df) == 0:
        logging.error(f"No audio files found in: {audio_dir}")
        sys.exit(1)
        
    from datasets import Features, Value
    logging.info(f"Loaded {len(df)} training samples.")
    features = Features({
        'audio': Value('string'),
        'sentence': Value('string')
    })
    dataset_dict = {
        'audio': df['audio'].tolist(),
        'sentence': df['sentence'].tolist()
    }
    dataset = Dataset.from_dict(dataset_dict, features=features)
    
    # 2. Initialize Whisper Components
    model_id = 'openai/whisper-base'
    feature_extractor = WhisperFeatureExtractor.from_pretrained(model_id)
    tokenizer = WhisperTokenizer.from_pretrained(model_id, language='English', task='transcribe')
    processor = WhisperProcessor.from_pretrained(model_id, language='English', task='transcribe')
    
    import librosa
    def prepare_dataset(batch):
        # Load audio path dynamically using librosa at 16kHz
        speech, sr = librosa.load(batch['audio'], sr=16000)
        batch['input_features'] = feature_extractor(speech, sampling_rate=16000).input_features[0]
        batch['labels'] = tokenizer(batch['sentence']).input_ids
        return batch
        
    logging.info("Preprocessing audio features (this might take a minute)...")
    dataset = dataset.map(prepare_dataset, remove_columns=dataset.column_names)
    
    @dataclass
    class DataCollatorSpeechSeq2SeqWithPadding:
        processor: Any
        def __call__(self, features: List[Dict[str, Union[List[int], torch.Tensor]]]) -> Dict[str, torch.Tensor]:
            input_features = [{'input_features': feature['input_features']} for feature in features]
            batch = self.processor.feature_extractor.pad(input_features, return_tensors='pt')
            label_features = [{'input_ids': feature['labels']} for feature in features]
            labels_batch = self.processor.tokenizer.pad(label_features, return_tensors='pt')
            labels = labels_batch['input_ids'].masked_fill(labels_batch.attention_mask.ne(1), -100)
            if (labels[:, 0] == self.processor.tokenizer.bos_token_id).all().cpu().item():
                labels = labels[:, 1:]
            batch['labels'] = labels
            return batch
            
    data_collator = DataCollatorSpeechSeq2SeqWithPadding(processor=processor)
    
    # 3. Apply LoRA Config
    logging.info("Loading base Whisper model and attaching LoRA adapters...")
    model = WhisperForConditionalGeneration.from_pretrained(model_id)
    model.config.forced_decoder_ids = None
    model.config.suppress_tokens = []
    
    config = LoraConfig(
        r=32,
        lora_alpha=64,
        target_modules=['q_proj', 'v_proj'],
        lora_dropout=0.05,
        bias='none'
    )
    model = get_peft_model(model, config)
    model.print_trainable_parameters()
    
    # 4. Training Arguments (Configured for local CPU execution)
    output_dir = os.path.join(training_dir, "output")
    training_args = Seq2SeqTrainingArguments(
        output_dir=output_dir,
        per_device_train_batch_size=4,          # Lower batch size to prevent CPU memory thrashing
        gradient_accumulation_steps=2,
        learning_rate=1e-3,
        warmup_steps=5,
        num_train_epochs=5,
        eval_strategy='no',
        fp16=False,                             # Must be False on CPU (no half-precision support)
        save_strategy='epoch',
        logging_steps=2,
        report_to='none',
        use_cpu=True                            # Explicitly force CPU training
    )
    
    trainer = Seq2SeqTrainer(
        args=training_args,
        model=model,
        train_dataset=dataset,
        data_collator=data_collator,
        processing_class=processor,
    )
    
    logging.info("🔥 Starting local CPU fine-tuning (should take 30-40 minutes)...")
    trainer.train()
    logging.info("🎉 Fine-tuning finished! Saving model checkpoint...")
    
    # 5. Merge LoRA adapter weights and export
    merged_dir = os.path.join(training_dir, "merged_base")
    merged_model = model.merge_and_unload()
    merged_model.save_pretrained(merged_dir)
    processor.save_pretrained(merged_dir)
    logging.info(f"Merged model saved to: {merged_dir}")
    
    # Convert model to CTranslate2 int8 for faster-whisper local loading
    ct2_output = os.path.join(base_dir, "models", "whisper-base-cfr-ct2")
    logging.info(f"Converting merged model to ctranslate2 int8 format at: {ct2_output}...")
    
    # Run conversion tool via shell command
    import subprocess
    cmd = [
        sys.executable,
        "-m",
        "ctranslate2.converters.transformers",
        "--model", merged_dir,
        "--output_dir", ct2_output,
        "--quantization", "int8",
        "--force"
    ]
    subprocess.run(cmd, check=True)
    logging.info("🚀 SUCCESSFULLY fine-tuned and converted local Whisper model! Ready to use.")

if __name__ == '__main__':
    main()
