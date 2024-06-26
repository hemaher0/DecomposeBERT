# in[] Library
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    AutoModelForSequenceClassification,
)
import torch
import os
import pathlib


# In[] Load/Save ModelConfig
def save_model(model_config):
    model_name = model_config.model_name
    model_dir = model_config.config_dir
    model = AutoModelForSequenceClassification.from_pretrained(model_name)

    # Save model and tokenizer
    model.save_pretrained(model_dir)
    return model


def save_tokenizer(model_config):
    model_name = model_config.model_name
    model_dir = model_config.config_dir
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.save_pretrained(model_dir)

    return tokenizer


def load_tokenizer(model_config):
    config_path = model_config.config_dir
    if not model_config.is_downloaded:
        tokenizer = save_tokenizer(model_config)
    else:
        tokenizer = AutoTokenizer.from_pretrained(config_path)
    return tokenizer


def load_model(model_config):
    """
    Load the specific model.
    Args:
        model_config (ModelConfig): The configuration for the model.
    Returns:
         model
         tokenizer
         checkpoint
    """

    load_path = model_config.module_dir

    config_path = model_config.config_dir
    # Check if the model exists, and Load model and tokenizer
    if not model_config.is_downloaded:
        print(f"Directory {config_path} does not exist.")
        print("Saving a new model here.")
        model = save_model(model_config)
        tokenizer = load_tokenizer(model_config)
    else:
        print(f"Directory {config_path} exists.")
        print("Loading the model.")
        if model_config.task_type == "classification":
            model = AutoModelForSequenceClassification.from_pretrained(config_path)
        elif model_config.task_type == "seq2seq":
            model = AutoModelForSeq2SeqLM.from_pretrained(config_path)
        else:
            raise ValueError(f"Unsupported task type: {model_config.task_type}")

        # Load a tokenizer.
        tokenizer = load_tokenizer(model_config)
    model_config.is_downloaded = True

    # load check point
    checkpoint = None
    if model_config.checkpoint is not None:
        checkpoint_path = os.path.join(load_path, model_config.checkpoint)
        if os.path.isfile(checkpoint_path):
            checkpoint = torch.load(checkpoint_path, map_location=model_config.device)
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"], strict=True)
            else:
                print(
                    "Checkpoint structure is unrecognized. Check the keys or save format."
                )
        else:
            print(f"Checkpoint path {checkpoint_path} does not exist.")
            checkpoint = None
    model.to(model_config.device)

    return model, tokenizer, checkpoint
