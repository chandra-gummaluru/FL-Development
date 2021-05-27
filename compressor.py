import torch
import numpy as np
import utils
from math import prod

# NOTE: this compressor class only serves as a proof of concept. In particular,
# it mimics compression by setting a fixed percentage of the model weights to 
# zero. Nonetheless, our Clients and Server are sending the entire model now with
# just some weights set to zero, and thus no actual compression is acheived. To
# achieve actual compression of data, one needs to convert the model to a list of
# floats (weights), drop the zero terms and thus send the smaller (compressed) list
# as well as a seed that allows us to recover the indices where weights were dropped.
# NOTE: An actual compression scheme based on Federated Dropout should follow or
# should be documented in a README or Github Wiki.
class Compressor:
    # NOTE: dropout = 1 - sqrt(1 - net dropout) --> net dropout = 2*dropout - dropout^2
    # This is because dropout occurs on the client and then server (twice) before the next round of weights is received
    def dropout_weights(model, seed, dropout=0.01, use_cuda=True):
        # Use the specified seed (to recover the relevant indices)
        # np.random.seed(seed)
        rng = np.random.default_rng(seed)
        
        model = model.cpu()
        state_dict = {}

        # Iterate through the state dictionary of the model
        for name, params in model.state_dict().items():
            # Compress the weights only
            if 'bias' not in name:
                weights = np.array(params.cpu()).flatten()

                # Select indices to "randomly" zero-out
                indices = rng.choice(np.arange(weights.size), replace=False, size=int(weights.size * dropout))
                weights[indices] = 0
                state_dict[name] = torch.tensor(weights.reshape(params.shape))
            else:
                state_dict[name] = params
        
        model.load_state_dict(state_dict)
        
        # Restore cuda
        if torch.cuda.is_available() and use_cuda:
          model = model.cuda()


class CompressedModel:

    def __init__(self, model, seed, dropout=0.01):
        self.values = []
        self.layers = []
        self.metadata = {}  # (start, end) indices in compressed list
        self.shape = {}     # shape of tensor
        self.seed = seed
        self.dropout = dropout

        # Compress
        model = model.cpu()

        # Use the specified seed (to recover the relevant indices)
        rng = np.random.default_rng(seed)
        
        # Iterate through the state dictionary of the model
        for name, params in model.state_dict().items():
            self.layers.append(name)
            self.metadata[name] = {}
            
            weights = np.array(params.cpu())
            self.metadata[name]['shape'] = weights.shape

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
            self.metadata[name]['indices'] = (start_idx, end_idx)
        
    def reconstruct(self):
        state_dict = {}

        # Use the specified seed (to recover the relevant indices)
        rng = np.random.default_rng(self.seed)

        for name in self.layers:
            # Retrieve compressed weights
            start, end = self.metadata[name]['indices']
            shape = self.metadata[name]['shape']
            numel = prod(shape)

            comp_weights = self.values[start:end]

            if 'bias' not in name:
                # Generate indices list
                indices = rng.choice(np.arange(numel), replace=False, size=int(numel * (1.0 - self.dropout)))
            
                # Populate non-zero weights
                weights = np.zeros(numel, dtype=np.float64)
                weights[indices] = comp_weights
            else:
                weights = np.array(comp_weights)
            
            # Reshape
            weights = weights.reshape(shape)

            state_dict[name] = torch.from_numpy(weights)
        
        return state_dict
