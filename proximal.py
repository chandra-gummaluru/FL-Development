import torch

# Squared difference of all layers
def proximal_term(local_model, global_model, mu=1.0):
    diff = None

    for lparam, gparam in zip(local_model.parameters(), global_model.parameters()):
        if diff == None:
            # Initialize diff so it can propagate gradients
            diff = torch.dist(lparam, gparam, p=2).pow(2)
        else:
            # Cumulate L2 distance
            diff = diff + torch.dist(lparam, gparam, p=2).pow(2)
    
    return diff * mu / 2.0
