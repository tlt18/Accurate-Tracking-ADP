from config import trainConfig
from myenv import TrackingEnv
from network import Actor, Critic
from train import Train
import numpy as np
import torch
import matplotlib.pyplot as plt
from datetime import datetime
import os
import time

# mode setting
isTrain = 1

# parameters setting
config = trainConfig()

# random seed
np.random.seed(0)
torch.manual_seed(0)

env = TrackingEnv()
env.seed(0)
stateDim = env.stateDim - 2
actionDim = env.actionSpace.shape[0]
actionSpace = env.actionSpace
policy = Actor(stateDim, actionDim, config.lrPolicy)
value = Critic(stateDim, 1, config.lrValue)
log_dir = "./Results_dir/" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
os.makedirs(log_dir, exist_ok=True)

if isTrain:
    print("----------------------Start Training!----------------------")
    train = Train(env)
    iterarion = 0
    lossListValue = 0
    while iterarion < config.iterationMax:
        # PEV
        train.policyEvaluate(policy, value)
        # PIM
        train.policyImprove(policy, value)
        train.calLoss()
        # update
        train.update(policy)
        if iterarion % config.iterationPrint == 0:
            print("iteration: {}, LossValue: {}, LossPolicy: {}".format(
                iterarion, train.lossValue[-1], train.lossPolicy[-1]))
        if iterarion % config.iterationSave == 0:
            env.policyTest(policy, iterarion, log_dir)
            # env.policyRender(policy)
        iterarion += 1
    env.policyTest(policy, iterarion, log_dir)
    plt.figure()
    plt.plot(range(len(train.lossValue)), train.lossValue)
    plt.xlabel('iteration')
    plt.ylabel('Value Loss')
    plt.savefig(log_dir + '/value_loss.png')
    plt.close()
    plt.figure()
    plt.plot(range(len(train.lossPolicy)), train.lossPolicy)
    plt.xlabel('iteration')
    plt.ylabel('Policy Loss')
    plt.savefig(log_dir + '/policy_loss.png')
    plt.close()
