import torch
import numpy as np
import utils

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
