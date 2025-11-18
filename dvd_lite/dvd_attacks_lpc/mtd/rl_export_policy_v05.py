# 파일 경로: dvd_lite/dvd_attacks_lpc/mtd/rl_export_policy_v05.py
import torch
import json
import os
import argparse
import logging
from datetime import datetime
from .rl_config_v05 import FEATURE_KEYS, ACTION_PARAM_KEYS, FEATURE_NORM_METADATA
from .rl_model_v05 import ActorCritic # Import the network definition

logger = logging.getLogger(__name__)

def export_policy(model_path, export_dir, state_dim, action_dim, hidden_size):
    """
    Exports the trained policy model and associated metadata for deployment.
    """
    logger.info(f"Loading model from: {model_path}")
    
    # --- 1. Load the Model ---
    # Determine the device (CPU is standard for deployment/export)
    device = torch.device("cpu")
    
    # Initialize the model structure
    model = ActorCritic(state_dim, action_dim, hidden_size).to(device)
    
    # Load the trained weights
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.eval() # Set to evaluation mode
        logger.info("Model weights loaded successfully.")
    except Exception as e:
        logger.error(f"Error loading model state dict: {e}")
        return

    # --- 2. Save Policy Network (Only the necessary part for inference) ---
    policy_output_path = os.path.join(export_dir, "mtd_policy.pth")
    torch.save(model.state_dict(), policy_output_path)
    logger.info(f"Policy model (.pth) saved to: {policy_output_path}")

    # --- 3. Save Metadata (JSON) ---
    metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "model_architecture": "PPO_ActorCritic_Continuous",
        "input_features": FEATURE_KEYS,
        "output_actions": ACTION_PARAM_KEYS,
        "input_dim": state_dim,
        "output_dim": action_dim,
        "hidden_size": hidden_size,
        "normalization_metadata": FEATURE_NORM_METADATA, # Includes assumed normalization
        "notes": "Policy output is continuous [-1, 1] and must be rescaled to [0, 1] before applying MTD functions (e.g. blacklist_aggression)."
    }
    
    metadata_output_path = os.path.join(export_dir, "mtd_policy_metadata.json")
    with open(metadata_output_path, 'w') as f:
        json.dump(metadata, f, indent=4)
        
    logger.info(f"Policy metadata (.json) saved to: {metadata_output_path}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    parser = argparse.ArgumentParser(description="MTD PPO Policy Export Utility")
    parser.add_argument("model_path", type=str, help="Path to the trained PyTorch model file (.pth)")
    parser.add_argument("--export-dir", type=str, default="exported_policy", help="Directory to save the exported files")
    parser.add_argument("--state-dim", type=int, default=len(FEATURE_KEYS), help="State dimension")
    parser.add_argument("--action-dim", type=int, default=len(ACTION_PARAM_KEYS), help="Action dimension")
    parser.add_argument("--hidden-size", type=int, default=128, help="Hidden layer size (must match training)")
    
    args = parser.parse_args()

    os.makedirs(args.export_dir, exist_ok=True)
    
    export_policy(args.model_path, args.export_dir, args.state_dim, args.action_dim, args.hidden_size)