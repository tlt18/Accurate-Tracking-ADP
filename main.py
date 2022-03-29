import os
import shutil
import time
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import torch

from config import trainConfig
from myenv import TrackingEnv
from network import Actor, Critic
from train import Train

# mode setting
isTrain = True

# parameters setting
config = trainConfig()

env = TrackingEnv()
env.seed(0)
relstateDim = env.relstateDim
actionDim = env.actionSpace.shape[0]
policy = Actor(relstateDim, actionDim, lr=config.lrPolicy)
value = Critic(relstateDim, 1, lr=config.lrValue)
# ADP_dir = './Results_dir/2022-03-29-10-19-28'
# policy.loadParameters(ADP_dir)
# value.loadParameters(ADP_dir)
log_dir = "./Results_dir/" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
os.makedirs(log_dir, exist_ok=True)
os.makedirs(log_dir + '/train', exist_ok=True)
os.makedirs(log_dir + '/code', exist_ok=True)

shutil.copy('./config.py', log_dir + '/code/config.py')
shutil.copy('./main.py', log_dir + '/code/main.py')
shutil.copy('./myenv.py', log_dir + '/code/myenv.py')
shutil.copy('./network.py', log_dir + '/code/network.py')
shutil.copy('./train.py', log_dir + '/code/train.py')

rewardList = []

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
            print("iteration: {}, LossValue: {:.4f}, LossPolicy: {:.4f}, value lr: {:8f}, policy lr: {:8f}".format(
                iterarion, train.lossValue[-1], train.lossPolicy[-1], value.opt.param_groups[0]['lr'], policy.opt.param_groups[0]['lr']))
        if iterarion % config.iterationSave == 0 or iterarion == config.iterationMax - 1:
            rewardSum = env.policyTestReal(policy, iterarion, log_dir+'/train')
            print("Accumulated Reward in real time is {:.4f}".format(rewardSum))
            rewardSum = env.policyTestVirtual(policy, iterarion, log_dir+'/train')
            print("Accumulated Reward in virtual time is {:.4f}".format(rewardSum))
            if np.isnan(rewardSum)==0:
                rewardList.append(rewardSum)
            env.plotReward(rewardList, log_dir+'/train', config.iterationSave)
            value.saveParameters(log_dir)
            policy.saveParameters(log_dir)
            # train.saveDate(log_dir+'/train')
            # env.policyRender(policy)
        iterarion += 1
