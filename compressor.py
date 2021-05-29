import torch
import numpy as np

import utils
from utils import NetworkModel

from math import prod

"""
NOTE: This compressor class uses Federated Dropout, one possible
implementation of compression. See the GitHub Wiki for instructions
on implementing a custom compressor.
"""
class CompressedModel(NetworkModel):

    def __init__(self, seed=0):
        super(CompressedModel, self).__init__(seed)
        
    def compress(self, state_dict, dropout=0.01):
        self.metadata['dropout'] = dropout

        # Use the specified seed (to recover the relevant indices)
        rng = np.random.default_rng(self.seed)
        
        # Iterate through the state dictionary of the model
        for name, params in state_dict.items():
            self.layers.append(name)
            self.metadata['layer'][name] = {}
            
            weights = np.array(params.cpu())
            self.metadata['layer'][name]['shape'] = weights.shape

            weights = weights.flatten()

            start_idx = len(self.values)

            # Compress the weights only
            if 'bias' not in name:
                # Select indices to "randomly" keep
                indices = rng.choice(np.arange(weights.size), replace=False, size=int(weights.size * (1.0 - dropout)))
                # Keep those indices
                self.values.extend(weights[indices].tolist())
            else:
                self.values.extend(weights.tolist())

            end_idx = len(self.values)
            self.metadata['layer'][name]['indices'] = (start_idx, end_idx)
        
        return self

    def reconstruct(self):
        state_dict = {}

        # Use the specified seed (to recover the relevant indices)
        rng = np.random.default_rng(self.seed)

        for name in self.layers:
            # Retrieve compressed weights
            start, end = self.metadata['layer'][name]['indices']
            shape = self.metadata['layer'][name]['shape']
            numel = prod(shape)

            comp_weights = self.values[start:end]

            if 'bias' not in name:
                # Generate indices list
                indices = rng.choice(np.arange(numel), replace=False, size=int(numel * (1.0 - self.metadata['dropout'])))
            
                # Populate non-zero weights
                weights = np.zeros(numel, dtype=np.float64)
                weights[indices] = comp_weights
            else:
                weights = np.array(comp_weights)
            
            # Reshape
            weights = weights.reshape(shape)

            state_dict[name] = torch.from_numpy(weights)
        
        return state_dict
