"""
RL Training Script - Multi-Program Training Loop
Train DQN agent across diverse benchmark programs
"""

import argparse
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from tqdm import tqdm
import tempfile
import random

from rl_agent import RLPassSelector, EpsilonScheduler, moving_average
from llvm_wrapper import LLVMWrapper, read_ir_file
from security_oracle import SecurityOracle
from rl_environment import LLVMOptimizationEnv
from config import RL_EPISODES, RL_LEARNING_RATE, APPROVED_PASSES


def train_rl_agent(benchmark_dir: str, 
                   model_output: str,
                   episodes: int = RL_EPISODES,
                   learning_rate: float = RL_LEARNING_RATE,
                   batch_size: int = 64,
                   target_update_freq: int = 10,
                   save_freq: int = 100,
                   device: str = 'cpu',
                   verbose: bool = True):
    """
    Train RL agent on multiple benchmark programs
    
    This is the CORE training loop that learns across diverse programs
    
    Args:
        benchmark_dir: Directory containing C source files
        model_output: Path to save trained model
        episodes: Total training episodes
        learning_rate: Learning rate for optimizer
        batch_size: Mini-batch size for training
        target_update_freq: Episodes between target network updates
        save_freq: Episodes between checkpoints
        device: 'cpu' or 'cuda'
        verbose: Print progress
    """
    llvm = LLVMWrapper()
    oracle = SecurityOracle()
    
    # Get benchmark files
    c_files = list(Path(benchmark_dir).glob("*.c"))
    if not c_files:
        raise ValueError(f"No C files found in {benchmark_dir}")
    
    # Split into train/val (80/20)
    random.shuffle(c_files)
    split_idx = int(0.8 * len(c_files))
    train_files = c_files[:split_idx]
    val_files = c_files[split_idx:]
    
    if verbose:
        print(f"Found {len(c_files)} benchmark programs")
        print(f"Train: {len(train_files)}, Val: {len(val_files)}")
        print(f"Training for {episodes} episodes...")
        print(f"Using {len(APPROVED_PASSES)} approved passes")
    
    # Pre-compile all programs to IR (faster training)
    if verbose:
        print("\nPre-compiling programs to IR...")
    
    train_irs = []
    for c_file in tqdm(train_files, desc="Compiling train set", disable=not verbose):
        try:
            fd, ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            llvm.compile_to_ir_stripped(str(c_file), ir_file, opt_level="0")
            
            # Get baseline score
            ir_content = read_ir_file(ir_file)
            baseline_score, _ = oracle.analyze(ir_content)
            
            train_irs.append((ir_file, baseline_score, c_file.name))
        except Exception as e:
            if verbose:
                print(f"  Failed to compile {c_file.name}: {e}")
    
    if len(train_irs) == 0:
        raise ValueError("No programs successfully compiled!")
    
    if verbose:
        print(f"Successfully compiled {len(train_irs)} programs")
    
    # Get state/action dimensions from first environment
    sample_env = LLVMOptimizationEnv(train_irs[0][0], train_irs[0][1])
    state_dim = sample_env.observation_space.shape[0]
    action_dim = sample_env.action_space.n
    sample_env.close()
    
    if verbose:
        print(f"\nRL Agent Configuration:")
        print(f"  State dimension: {state_dim}")
        print(f"  Action dimension: {action_dim}")
        print(f"  Learning rate: {learning_rate}")
        print(f"  Batch size: {batch_size}")
    
    # Initialize RL agent
    agent = RLPassSelector(
        state_dim=state_dim,
        action_dim=action_dim,
        learning_rate=learning_rate,
        device=device
    )
    
    # Epsilon scheduler
    epsilon_scheduler = EpsilonScheduler(
        epsilon_start=1.0,
        epsilon_end=0.01,
        epsilon_decay=episodes // 2  # Decay over first half of training
    )
    
    # Training statistics
    episode_rewards = []
    episode_lengths = []
    episode_size_reductions = []
    episode_security_ratios = []
    losses = []
    
    # Create output directory
    os.makedirs(os.path.dirname(model_output) if os.path.dirname(model_output) else ".", 
                exist_ok=True)
    
    # Training loop
    print("\n" + "=" * 60)
    print("TRAINING STARTED")
    print("=" * 60)
    
    for episode in tqdm(range(episodes), desc="Training"):
        # Sample random program
        ir_file, baseline_score, program_name = random.choice(train_irs)
        
        # Create environment
        env = LLVMOptimizationEnv(ir_file, baseline_score)
        state, _ = env.reset()
        
        # Episode variables
        episode_reward = 0
        step_count = 0
        done = False
        
        # Get epsilon for this episode
        epsilon = epsilon_scheduler.get_epsilon(episode)
        
        # Episode loop
        while not done and step_count < 50:  # Max 50 steps per episode
            # Select action
            action = agent.select_action(state, epsilon)
            
            # Take step
            next_state, reward, terminated, truncated, info = env.step(action)
            done = terminated or truncated
            
            # Store transition
            agent.store_transition(state, action, reward, next_state, done)
            
            # Train if enough samples
            if len(agent.replay_buffer) >= batch_size:
                loss = agent.train_step(batch_size)
                if loss > 0:
                    losses.append(loss)
            
            state = next_state
            episode_reward += reward
            step_count += 1
        
        # Get final metrics
        metrics = env.get_metrics()
        episode_rewards.append(episode_reward)
        episode_lengths.append(step_count)
        episode_size_reductions.append(metrics['size_reduction'])
        episode_security_ratios.append(metrics['security_preservation'])
        
        # Clean up environment
        env.close()
        
        # Update target network periodically
        if episode % target_update_freq == 0:
            agent.update_target_network()
        
        # Save checkpoint
        if episode % save_freq == 0 and episode > 0:
            checkpoint_path = model_output.replace('.pt', f'_ep{episode}.pt')
            agent.save(checkpoint_path)
            if verbose and episode % (save_freq * 2) == 0:
                print(f"\nEpisode {episode}/{episodes}")
                print(f"  Avg Reward (last 100): {np.mean(episode_rewards[-100:]):.3f}")
                print(f"  Avg Size Reduction: {np.mean(episode_size_reductions[-100:]):.1f}%")
                print(f"  Avg Security: {np.mean(episode_security_ratios[-100:]):.1f}%")
                print(f"  Epsilon: {epsilon:.3f}")
                if len(losses) > 0:
                    print(f"  Avg Loss: {np.mean(losses[-100:]):.4f}")
    
    # Save final model
    agent.save(model_output)
    
    if verbose:
        print("\n" + "=" * 60)
        print("TRAINING COMPLETE")
        print("=" * 60)
        print(f"Model saved to: {model_output}")
    
    # Generate training curves
    plot_training_curves(
        episode_rewards,
        episode_size_reductions,
        episode_security_ratios,
        losses,
        output_dir=os.path.dirname(model_output) or "."
    )
    
    # Evaluate on validation set
    if len(val_files) > 0 and verbose:
        print("\nEvaluating on validation set...")
        eval_agent(agent, val_files[:5], llvm, oracle, verbose=True)
    
    # Cleanup
    for ir_file, _, _ in train_irs:
        if os.path.exists(ir_file):
            os.remove(ir_file)
    
    return agent


def eval_agent(agent: RLPassSelector, 
               c_files: list,
               llvm: LLVMWrapper,
               oracle: SecurityOracle,
               verbose: bool = True):
    """
    Evaluate trained agent on test programs
    """
    results = []
    
    for c_file in c_files:
        try:
            # Compile
            fd, ir_file = tempfile.mkstemp(suffix=".ll")
            os.close(fd)
            llvm.compile_to_ir_stripped(str(c_file), ir_file, opt_level="0")
            
            ir_content = read_ir_file(ir_file)
            baseline_score, _ = oracle.analyze(ir_content)
            
            # Create environment
            env = LLVMOptimizationEnv(ir_file, baseline_score)
            state, _ = env.reset()
            
            # Run episode with greedy policy (no exploration)
            done = False
            steps = 0
            while not done and steps < 50:
                action = agent.select_action(state, epsilon=0.0)  # Greedy
                state, reward, terminated, truncated, info = env.step(action)
                done = terminated or truncated
                steps += 1
            
            metrics = env.get_metrics()
            results.append(metrics)
            
            if verbose:
                print(f"  {Path(c_file).name}: "
                      f"Size {metrics['size_reduction']:.1f}%, "
                      f"Security {metrics['security_preservation']:.1f}%")
            
            env.close()
            os.remove(ir_file)
            
        except Exception as e:
            if verbose:
                print(f"  {Path(c_file).name}: Error - {e}")
    
    if results and verbose:
        avg_size = np.mean([r['size_reduction'] for r in results])
        avg_sec = np.mean([r['security_preservation'] for r in results])
        print(f"\nValidation Averages:")
        print(f"  Size Reduction: {avg_size:.1f}%")
        print(f"  Security Preservation: {avg_sec:.1f}%")


def plot_training_curves(rewards, size_reductions, security_ratios, losses, output_dir):
    """Generate training progress plots"""
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Episode rewards
    ax = axes[0, 0]
    ax.plot(rewards, alpha=0.3, label='Raw')
    if len(rewards) > 100:
        ax.plot(moving_average(rewards, 100), label='MA(100)', linewidth=2)
    ax.set_xlabel('Episode')
    ax.set_ylabel('Total Reward')
    ax.set_title('Training Reward Over Time')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 2: Size reduction
    ax = axes[0, 1]
    ax.plot(size_reductions, alpha=0.3, label='Raw')
    if len(size_reductions) > 100:
        ax.plot(moving_average(size_reductions, 100), label='MA(100)', linewidth=2)
    ax.set_xlabel('Episode')
    ax.set_ylabel('Code Size Reduction (%)')
    ax.set_title('Optimization Performance')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 3: Security preservation
    ax = axes[1, 0]
    ax.plot(security_ratios, alpha=0.3, label='Raw')
    if len(security_ratios) > 100:
        ax.plot(moving_average(security_ratios, 100), label='MA(100)', linewidth=2)
    ax.axhline(y=90, color='r', linestyle='--', label='Threshold (90%)')
    ax.set_xlabel('Episode')
    ax.set_ylabel('Security Preservation (%)')
    ax.set_title('Security Constraint Satisfaction')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Plot 4: Training loss
    ax = axes[1, 1]
    if len(losses) > 0:
        ax.plot(losses, alpha=0.3, label='Raw')
        if len(losses) > 100:
            ax.plot(moving_average(losses, 100), label='MA(100)', linewidth=2)
    ax.set_xlabel('Training Step')
    ax.set_ylabel('TD Loss')
    ax.set_title('Learning Progress')
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plot_path = os.path.join(output_dir, 'training_curves.png')
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Training curves saved to: {plot_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Train RL agent for security-preserving pass selection"
    )
    parser.add_argument("--benchmark-dir", required=True, 
                       help="Directory with benchmark C files")
    parser.add_argument("--model-output", required=True,
                       help="Output path for trained model (.pt)")
    parser.add_argument("--episodes", type=int, default=RL_EPISODES,
                       help=f"Total training episodes (default: {RL_EPISODES})")
    parser.add_argument("--learning-rate", type=float, default=RL_LEARNING_RATE,
                       help=f"Learning rate (default: {RL_LEARNING_RATE})")
    parser.add_argument("--batch-size", type=int, default=64,
                       help="Training batch size (default: 64)")
    parser.add_argument("--device", default="cpu", choices=["cpu", "cuda"],
                       help="Device for training")
    parser.add_argument("--no-verbose", action="store_false", dest="verbose",
                       help="Disable verbose output")
    parser.set_defaults(verbose=True)
    
    args = parser.parse_args()
    
    train_rl_agent(
        benchmark_dir=args.benchmark_dir,
        model_output=args.model_output,
        episodes=args.episodes,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        device=args.device,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
