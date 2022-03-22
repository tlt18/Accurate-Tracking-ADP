from matplotlib import pyplot as plt
import torch
import numpy as np
from myenv import TrackingEnv

env = TrackingEnv()
plt.figure()
x = torch.linspace(0, 30*np.pi, 1000)
y = env.referenceCurve(x)
plt.xlim(-5, 100)
plt.ylim(-1.1, 1.1)
plt.plot(x, y, color='gray')        
plt.savefig('./background.png')
plt.close()