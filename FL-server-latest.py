#!/usr/bin/env python
# coding: utf-8

# In[1]:


import torch
import torchvision
import torchvision.transforms as transforms
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
from torch.utils.data import DataLoader,TensorDataset
import numpy as np
import time
from torchvision import datasets
from collections import OrderedDict


# In[2]:


class Net(nn.Module):
    def __init__(self):
        super(Net, self).__init__()
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=20,
                               kernel_size=5, stride=1)
        self.conv2 = nn.Conv2d(in_channels=20, out_channels=50,
                               kernel_size=5, stride=1)
        self.fc1 = nn.Linear(in_features=50*4*4, out_features=500)
        self.fc2 = nn.Linear(in_features=500, out_features=10)
    def forward(self, x):
        x = F.relu(self.conv1(x.float()))
        x = F.max_pool2d(x, 2, 2)
        x = F.relu(self.conv2(x)) #do we need to convert to float here as well?
        x = F.max_pool2d(x, 2, 2)
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = self.fc2(x)
        return x


# In[24]:


class ML_Server:
    def __init__(self):
        self.model = Net()

    def get_model(self):
        return self.model

    def aggregate(self, updates):
        # updates is a list of OrderedDict/state_dict
        num_updates = len(updates)
        if (num_updates == 0):
            raise Exception("No updates to aggregate")
        if (num_updates == 1):
            return updates[0]

        combined_update = Net().state_dict()
        for i in range(num_updates):
            for key in updates[i]:
                combined_update[key] += updates[i][key]
        
        for key in combined_update:
            combined_update[key] /= float(num_updates)

        return combined_update

    def update(self, combined_update):
        self.model.load_state_dict(combined_update)


# In[25]:


# test
server = ML_Server()

# test get_model
model = server.get_model()
print(model.state_dict())


# In[26]:


# test aggregate
PATH1 = './models/model' #123
PATH2 = './models/model2' #456
PATH3 = './models/model3' #7890

net1_sd = torch.load(PATH1)
net2_sd = torch.load(PATH2)
net3_sd = torch.load(PATH3)

updates = [net1_sd, net2_sd, net3_sd]
combined_update = server.aggregate(updates)
for key, value in combined_update.items():
    print(key, value) 


# In[27]:


# test update
print(combined_update)
server.update(combined_update)
model = server.get_model()
for param in model.parameters():
    print(param)


# In[ ]:




