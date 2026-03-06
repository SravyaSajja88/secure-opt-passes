"""
Deep Q-Network Agent for Security-Preserving Pass Selection
Core RL component - learns optimal pass sequences
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import numpy as np
import random
from collections import deque, namedtuple
from typing import List, Tuple

# Transition tuple for replay buffer
Transition = namedtuple('Transition', 
                       ('state', 'action', 'reward', 'next_state', 'done'))


class DQN(nn.Module):
    """
    Deep Q-Network for pass selection
    
    Architecture:
        state (dim ~100) -> FC(256) -> FC(256) -> FC(128) -> Q-values (dim 20-30)
    """
    
    def __init__(self, state_dim: int, action_dim: int, 
                 hidden_dims: List[int] = [256, 256, 128]):
        super(DQN, self).__init__()
        
        self.state_dim = state_dim
        self.action_dim = action_dim
        
        # Build network layers
        layers = []
        prev_dim = state_dim
        
        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.1))  # Prevent overfitting
            prev_dim = hidden_dim
        
        # Output layer (Q-values for each action)
        layers.append(nn.Linear(prev_dim, action_dim))
        
        self.network = nn.Sequential(*layers)
        
        # Initialize weights
        self.apply(self._init_weights)
    
    def _init_weights(self, module):
        """Xavier initialization for better learning"""
        if isinstance(module, nn.Linear):
            torch.nn.init.xavier_uniform_(module.weight)
            module.bias.data.fill_(0.01)
    
    def forward(self, state):
        """Forward pass: state -> Q-values"""
        return self.network(state)


class ReplayBuffer:
    """
    Experience Replay Buffer
    Stores transitions and samples mini-batches for training
    """
    
    def __init__(self, capacity: int = 100000):
        self.buffer = deque(maxlen=capacity)
    
    def add(self, state, action, reward, next_state, done):
        """Add transition to buffer"""
        self.buffer.append(Transition(state, action, reward, next_state, done))
    
    def sample(self, batch_size: int) -> List[Transition]:
        """Sample random mini-batch"""
        return random.sample(self.buffer, batch_size)
    
    def __len__(self):
        return len(self.buffer)


class RLPassSelector:
    """
    RL Agent for selecting optimization passes
    Uses DQN with experience replay and target network
    """
    
    def __init__(self, state_dim: int, action_dim: int,
                 learning_rate: float = 0.0003,
                 gamma: float = 0.99,
                 buffer_capacity: int = 100000,
                 device: str = 'cpu'):
        """
        Args:
            state_dim: Dimension of state vector
            action_dim: Number of possible actions (passes)
            learning_rate: Adam optimizer learning rate
            gamma: Discount factor for future rewards
            buffer_capacity: Replay buffer size
            device: 'cpu' or 'cuda'
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.gamma = gamma
        self.device = torch.device(device)
        
        # Policy network (updated every step)
        self.policy_net = DQN(state_dim, action_dim).to(self.device)
        
        # Target network (updated periodically)
        self.target_net = DQN(state_dim, action_dim).to(self.device)
        self.target_net.load_state_dict(self.policy_net.state_dict())
        self.target_net.eval()  # Always in eval mode
        
        # Optimizer
        self.optimizer = optim.Adam(self.policy_net.parameters(), 
                                    lr=learning_rate)
        
        # Replay buffer
        self.replay_buffer = ReplayBuffer(capacity=buffer_capacity)
        
        # Training statistics
        self.loss_history = []
        self.reward_history = []
    
    def select_action(self, state: np.ndarray, epsilon: float = 0.1) -> int:
        """
        Epsilon-greedy action selection
        
        Args:
            state: Current state vector
            epsilon: Exploration rate (0 = greedy, 1 = random)
        
        Returns:
            action: Index of selected pass
        """
        if random.random() < epsilon:
            # Explore: random action
            return random.randint(0, self.action_dim - 1)
        else:
            # Exploit: best action according to policy
            with torch.no_grad():
                state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
                q_values = self.policy_net(state_tensor)
                return q_values.argmax().item()
    
    def store_transition(self, state, action, reward, next_state, done):
        """Store experience in replay buffer"""
        self.replay_buffer.add(state, action, reward, next_state, done)
    
    def train_step(self, batch_size: int = 64) -> float:
        """
        Perform one training step using sampled batch
        
        Returns:
            loss: TD error loss value
        """
        if len(self.replay_buffer) < batch_size:
            return 0.0
        
        # Sample mini-batch
        transitions = self.replay_buffer.sample(batch_size)
        batch = Transition(*zip(*transitions))
        
        # Convert to tensors
        state_batch = torch.FloatTensor(np.array(batch.state)).to(self.device)
        action_batch = torch.LongTensor(batch.action).unsqueeze(1).to(self.device)
        reward_batch = torch.FloatTensor(batch.reward).to(self.device)
        next_state_batch = torch.FloatTensor(np.array(batch.next_state)).to(self.device)
        done_batch = torch.FloatTensor(batch.done).to(self.device)
        
        # Compute Q(s, a) for taken actions
        q_values = self.policy_net(state_batch).gather(1, action_batch)
        
        # Compute target Q-values using target network
        with torch.no_grad():
            # Double DQN: use policy net to select action, target net to evaluate
            next_actions = self.policy_net(next_state_batch).argmax(1, keepdim=True)
            next_q_values = self.target_net(next_state_batch).gather(1, next_actions)
            target_q = reward_batch + self.gamma * next_q_values.squeeze() * (1 - done_batch)
        
        # Compute Huber loss (more stable than MSE)
        loss = F.smooth_l1_loss(q_values.squeeze(), target_q)
        
        # Optimize
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping for stability
        torch.nn.utils.clip_grad_norm_(self.policy_net.parameters(), max_norm=1.0)
        self.optimizer.step()
        
        # Record loss
        self.loss_history.append(loss.item())
        
        return loss.item()
    
    def update_target_network(self):
        """Copy weights from policy network to target network"""
        self.target_net.load_state_dict(self.policy_net.state_dict())
    
    def save(self, filepath: str):
        """Save model weights and training history"""
        torch.save({
            'policy_net': self.policy_net.state_dict(),
            'target_net': self.target_net.state_dict(),
            'optimizer': self.optimizer.state_dict(),
            'loss_history': self.loss_history,
            'reward_history': self.reward_history,
        }, filepath)
    
    def load(self, filepath: str):
        """Load model weights and training history"""
        checkpoint = torch.load(filepath, map_location=self.device)
        self.policy_net.load_state_dict(checkpoint['policy_net'])
        self.target_net.load_state_dict(checkpoint['target_net'])
        self.optimizer.load_state_dict(checkpoint['optimizer'])
        self.loss_history = checkpoint.get('loss_history', [])
        self.reward_history = checkpoint.get('reward_history', [])
    
    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for all actions (for debugging)"""
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.policy_net(state_tensor)
            return q_values.cpu().numpy()[0]


class EpsilonScheduler:
    """
    Epsilon decay scheduler for exploration vs exploitation
    """
    
    def __init__(self, epsilon_start: float = 1.0, 
                 epsilon_end: float = 0.01,
                 epsilon_decay: int = 500):
        """
        Args:
            epsilon_start: Initial exploration rate
            epsilon_end: Minimum exploration rate
            epsilon_decay: Episodes over which to decay
        """
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
    
    def get_epsilon(self, episode: int) -> float:
        """Get epsilon for current episode (exponential decay)"""
        epsilon = self.epsilon_end + (self.epsilon_start - self.epsilon_end) * \
                  np.exp(-episode / self.epsilon_decay)
        return epsilon


# Utility functions for training

def compute_returns(rewards: List[float], gamma: float = 0.99) -> List[float]:
    """
    Compute discounted returns for episode
    Useful for monitoring training progress
    """
    returns = []
    G = 0
    for r in reversed(rewards):
        G = r + gamma * G
        returns.insert(0, G)
    return returns


def moving_average(data: List[float], window: int = 100) -> List[float]:
    """Compute moving average for smoothing plots"""
    if len(data) < window:
        return data
    
    smoothed = []
    for i in range(len(data)):
        start = max(0, i - window + 1)
        smoothed.append(np.mean(data[start:i+1]))
    return smoothed
