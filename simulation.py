from cProfile import label
from curses.ascii import isprint
import math
import os
import time
from datetime import datetime
from turtle import color

import matplotlib.pyplot as plt
import numpy as np
import torch

from config import MPCConfig
from myenv import TrackingEnv
from network import Actor, Critic
from solver import Solver

def simulationMPC(MPCStep, simu_dir, curveType = 'sine'):

    env = TrackingEnv()
    env.seed(0)
    stateDim = env.stateDim
    actionDim = env.actionSpace.shape[0]
    solver = Solver()
    for mpcstep in MPCStep:
        print("----------------------Start Solving!----------------------")
        print("MPCStep: {}".format(mpcstep))
        # plt.ion()
        plt.figure(mpcstep)
        tempstate = env.initializeState(200)
        tempstate = tempstate[0].tolist() # 这里就取了一个，可以考虑从0开始取
        state = tempstate[-3:] + tempstate[:3]
        refState = tempstate[3:6]
        count = 0
        x = torch.linspace(0, 30*np.pi, 1000)
        y, _ = env.referenceCurve(x)
        plt.xlim(-5, 100)
        plt.ylim(-1.1, 1.1)
        plt.plot(x, y, color='gray')
        controlMPC = np.empty(0)
        stateMPC = np.empty(0)
        while(count < env.testStepReal[curveType]):
            _, control = solver.MPCSolver(state, refState, mpcstep, isReal = True)
            stateMPC = np.append(stateMPC, np.array(state))
            stateMPC = np.append(stateMPC, np.array(refState))
            action = control[0].tolist()
            state = env.vehicleDynamic(
                state[0], state[1], state[2], state[3], state[4], state[5], action[0], action[1], MPCflag=1)
            refState = env.refDynamicReal(refState[0], MPCflag = 1)[0:3]
            plt.scatter(state[0], state[1], color='red', s=2)
            plt.scatter(refState[0], refState[1], color='blue', s=2)
            controlMPC = np.append(controlMPC, control[0])
            # plt.pause(0.05)
            count += 1
            if count % 10 == 0:
                print('count/totalStep: {}/{}'.format(count, env.testStepReal[curveType]))
        plt.title('MPCStep:'+str(mpcstep))
        plt.savefig(simu_dir + '/OnlyMPCStep'+str(mpcstep)+'.png')
        # plt.ioff()
        plt.close()
        controlMPC = np.reshape(controlMPC, (-1, actionDim))
        stateMPC = np.reshape(stateMPC, (-1, stateDim))
        saveMPC = np.concatenate((stateMPC, controlMPC), axis = 1)
        with open(simu_dir + "/simulationMPC_" + str(mpcstep)+".csv", 'ab') as f:
            np.savetxt(f, saveMPC, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega,xr,yr,phir,a,delta")

def simulationOpen(MPCStep, simu_dir):
    # 虚拟时域中MPC表现（开环控制）
    env = TrackingEnv()
    solver = Solver()
    for mpcstep in MPCStep:
        print("----------------------Start Solving!----------------------")
        print("MPCStep: {}".format(mpcstep))
        plt.figure(mpcstep)
        tempstate = env.initializeState(200)
        tempstate = tempstate[0].tolist() # 这里就取了一个，可以考虑从0开始取
        state = tempstate[-3:] + tempstate[:3]
        refState = tempstate[3:6]
        x = torch.linspace(0, 30*np.pi, 1000)
        y, _ = env.referenceCurve(x)
        plt.xlim(-5, 100)
        plt.ylim(-1.1, 1.1)
        plt.plot(x, y, color='gray')
        count = 0
        _, control = solver.MPCSolver(state, refState, mpcstep, isReal=False)
        plt.scatter(state[0], state[1], color='red', s=5)
        plt.scatter(refState[0], refState[1], color='blue', s=5)
        stateList = np.empty(0)
        refList = np.empty(0)
        stateList = np.append(stateList, state)
        refList = np.append(refList, refState)
        while(count < mpcstep):
            action = control[count].tolist()
            state = env.vehicleDynamic(
                state[0], state[1], state[2], state[3], state[4], state[5], action[0], action[1], MPCflag=1)
            refState = env.refDynamicVirtual(refState, MPCflag=1)[:3]
            stateList = np.append(stateList, state)
            refList = np.append(refList, refState)
            plt.scatter(state[0], state[1], color='red', s=5)
            plt.scatter(refState[0], refState[1], color='blue', s=5)
            count += 1
        plt.title('MPCStep:'+str(mpcstep))
        plt.savefig(simu_dir + '/simulationOpen'+str(mpcstep)+'.png')
        plt.close()
        stateList = np.reshape(stateList, (-1, 6))
        refList = np.reshape(refList, (-1, env.refNum * 3))
        if mpcstep==MPCStep[-1]:
            animationPlot(stateList[:,:2], refList[:,:2],'x', 'y')
        
def simulationOneStep(MPCStep, ADP_dir, simu_dir, stateNum):
    # 单步ADP、MPC测试
    env = TrackingEnv()
    env.seed(0)
    relstateDim = env.relstateDim
    actionDim = env.actionSpace.shape[0]
    policy = Actor(relstateDim, actionDim)
    policy.loadParameters(ADP_dir)
    value = Critic(relstateDim, 1)
    value.loadParameters(ADP_dir)
    solver = Solver()
    initialState = env.initializeState(stateNum) # [u,v,omega,[xr,yr,phir],x,y,phi]
    timeStart = time.time()
    relState = env.relStateCal(initialState)
    controlADP = policy(relState).detach()
    timeADP = (time.time() - timeStart)
    controlADP = controlADP.numpy()
    print("ADP consumes {:.3f}s {} step".format(timeADP, stateNum))
    for mpcstep in MPCStep:
        timeMPC = 0
        controlMPC = np.empty(0)
        print("----------------------Start Solving MPC" +str(mpcstep)+"!----------------------")
        for i in range(stateNum):
            tempstate = initialState[i].tolist() # 这里就取了一个，可以考虑从0开始取
            state = tempstate[-3:] + tempstate[:3]
            refState = tempstate[3:6]
            timeStart = time.time()
            _, control = solver.MPCSolver(state, refState, mpcstep, isReal=False)
            timeMPC += time.time() - timeStart
            controlMPC = np.append(controlMPC, control[0])
        controlMPC = np.reshape(controlMPC, (-1, actionDim))
        print("MPC{} consumes {:.3f}s {} step".format(mpcstep, timeMPC, stateNum))
        # TODO: 这么做合适吗
        maxAction = np.array(env.actionHigh)
        minAction = np.array(env.actionLow)
        # maxAction = np.max(controlMPC, 0)
        # minAction = np.min(controlMPC, 0)
        relativeError = np.abs(
            (controlADP - controlMPC)/(maxAction - minAction))
        relativeErrorMax = np.max(relativeError, 0)
        relativeErrorMean = np.mean(relativeError, 0)
        for i in range(actionDim):
            print('Relative error for action{}'.format(i+1))
            print('Mean: {:.2f}%, Max: {:.2f}%'.format(relativeErrorMean[i]*100,relativeErrorMax[i]*100))
        saveMPC = np.concatenate((controlADP, controlMPC, relativeError), axis = 1)
        with open(simu_dir + "/simulationOneStepMPC_"+str(mpcstep)+".csv", 'ab') as f:
            np.savetxt(f, saveMPC, delimiter=',', fmt='%.4f', comments='', header="ADP_a,ADP_delta,MPC_a,MPC_delta,rel_a,rel_delta")
        plt.figure()
        data = relativeError[:, 0]
        plt.hist(data, bins=30, weights = np.zeros_like(data) + 1 / len(data))
        plt.xlabel('Relative Error')
        plt.ylabel('Frequency')
        plt.title('Relative Error of control a')
        plt.savefig(simu_dir + '/simulationOneStep'+str(mpcstep)+'_a.png')
        plt.close()
        plt.figure()
        data = relativeError[:, 1]
        plt.hist(data, bins=30, weights = np.zeros_like(data) + 1 / len(data))
        plt.xlabel('Relative Error')
        plt.ylabel('Frequency')
        plt.title('Relative Error of control delta')
        plt.savefig(simu_dir + '/simulationOneStep'+str(mpcstep)+'_delta.png')
        plt.close()

def simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'sine', seed = 0):
    print("----------------------Curve Type: {}----------------------".format(curveType))
    plotDelete = 0
    # 真实时域ADP、MPC应用
    env = TrackingEnv()
    env.seed(seed)
    relstateDim = env.relstateDim
    actionDim = env.actionSpace.shape[0]
    policy = Actor(relstateDim, actionDim)
    policy.loadParameters(ADP_dir)
    value = Critic(relstateDim, 1)
    value.loadParameters(ADP_dir)
    solver = Solver()
    initialState = env.resetSpecificCurve(1, curveType) # [u,v,omega,[xr,yr,phir],x,y,phi]

    # ADP
    stateAdp = initialState.clone()
    controlADPList = np.empty(0)
    stateADPList = np.empty(0)
    rewardADP = np.empty(0)
    timeADP = np.empty(0)
    count = 0
    while(count < env.testStepReal[curveType]):
        stateADPList = np.append(stateADPList, stateAdp[0, -3:].numpy()) # x, y, phi
        stateADPList = np.append(stateADPList, stateAdp[0, :-3].numpy()) # u, v, omega, [xr, yr, phir]
        relState = env.relStateCal(stateAdp)
        start = time.time()
        controlAdp = policy(relState)
        end = time.time()
        timeADP = np.append(timeADP, end - start)
        controlAdp = controlAdp.detach()
        stateAdp, reward, done = env.stepReal(stateAdp, controlAdp, curveType = curveType)
        controlADPList = np.append(controlADPList, controlAdp[0].numpy())
        rewardADP = np.append(rewardADP, reward.numpy())
        count += 1
    stateADPList = np.reshape(stateADPList, (-1, env.stateDim))
    controlADPList = np.reshape(controlADPList, (-1, actionDim))
    stateADPList = np.delete(stateADPList, range(plotDelete), 0)
    controlADPList = np.delete(controlADPList, range(plotDelete), 0)
    rewardADP = np.delete(rewardADP, range(plotDelete), 0)
    saveADP = np.concatenate((stateADPList, controlADPList), axis = 1)
    with open(simu_dir + "/simulationRealADP.csv", 'wb') as f:
        np.savetxt(f, saveADP, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*env.refNum + "a,delta")

    controlMPCAll = []
    stateMPCAll = []
    rewardMPCAll = []
    timeMPCAll = []
    for mpcstep in MPCStep:
        env.randomTestReset()
        print("Start Solving MPC-{}!".format(mpcstep))
        tempstate = initialState[0].tolist()
        stateMpc = tempstate[-3:] + tempstate[:3] # x, y, phi, u, v, omega
        refStateMpc = tempstate[3:-3]
        count = 0
        controlMPCList = np.empty(0)
        stateMPCList = np.empty(0)
        rewardMPC = np.empty(0)
        timeMPC = np.empty(0)
        while(count < env.testStepReal[curveType]):
            # MPC
            start = time.time()
            _, control = solver.MPCSolver(stateMpc, refStateMpc, mpcstep, isReal = False)
            end = time.time()
            timeMPC = np.append(timeMPC, end - start)
            stateMPCList = np.append(stateMPCList, np.array(stateMpc))
            stateMPCList = np.append(stateMPCList, np.array(refStateMpc))
            action = control[0].tolist()
            reward = env.calReward(stateMpc[-3:] + refStateMpc + stateMpc[:3],action,MPCflag=1)
            stateMpc = env.vehicleDynamic(
                stateMpc[0], stateMpc[1], stateMpc[2], stateMpc[3], stateMpc[4], stateMpc[5], action[0], action[1], MPCflag=1)
            refStateMpc = env.refDynamicReal(refStateMpc, MPCflag=1, curveType=curveType)
            rewardMPC = np.append(rewardMPC, reward)
            controlMPCList = np.append(controlMPCList, control[0])
            count += 1
        stateMPCList = np.reshape(stateMPCList, (-1, env.stateDim))
        controlMPCList = np.reshape(controlMPCList, (-1, actionDim))
        stateMPCList = np.delete(stateMPCList, range(plotDelete), 0)
        controlMPCList = np.delete(controlMPCList, range(plotDelete), 0)
        rewardMPC = np.delete(rewardMPC, range(plotDelete), 0)

        saveMPC = np.concatenate((stateMPCList, controlMPCList), axis = 1)
        with open(simu_dir + "/simulationRealMPC_"+str(mpcstep)+".csv", 'wb') as f:
            np.savetxt(f, saveMPC, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*env.refNum + "a,delta")
        rewardMPCAll.append(rewardMPC)
        stateMPCAll.append(stateMPCList)
        controlMPCAll.append(controlMPCList)
        timeMPCAll.append(timeMPC)
    
    print("Time consume ADP: {}ms".format(timeADP.mean() * 1000))
    for i in range(len(MPCStep)):
        print("Time consume MPC-{}: {}ms".format(MPCStep[i], timeMPCAll[i].mean() * 1000))

    colorList = ['darkorange', 'green', 'blue', 'red']
    plt.figure()
    pos = list(range(len(MPCStep) + 1))
    plt.bar([p for p in pos], [timeADP.mean() * 1000]+[timempc.mean() * 1000 for timempc in timeMPCAll], 
        width = 0.3,color = [colorList[-1]] + [colorList[i] for i in range(len(MPCStep))], 
        label=['ADP'] + ['MPC-'+str(mpcstep) for mpcstep in MPCStep])
    plt.xticks(range(len(MPCStep) + 1), ['ADP'] + ['MPC-'+str(mpcstep) for mpcstep in MPCStep])
    for x,y in enumerate([timeADP.mean() * 1000]+[timempc.mean() * 1000 for timempc in timeMPCAll]):
        plt.text(x, y,'%s ms' %round(y, 2), ha='center', va='bottom',fontsize=9)
    # plt.bar(['ADP'] + ['MPC-'+str(mpcstep) for mpcstep in MPCStep], 
    #     [timeADP.mean() * 1000]+[timempc.mean() * 1000 for timempc in timeMPCAll],
    #     color = [colorList[-1]] + [colorList[i] for i in range(len(MPCStep))],
    #     width=0.3)
    plt.ylabel("Average calculation time [ms]")
    plt.yscale('log')
    plt.savefig(simu_dir + '/average-calculation-time.png', bbox_inches='tight')
    # plt.title("Calculation time")
    plt.close()

    plt.figure()
    for i in range(len(MPCStep)):
        plt.plot(range(len(timeMPCAll[i])), timeMPCAll[i] * 1000, label = 'MPC-' + str(MPCStep[i]), color = colorList[i])
    plt.plot(range(len(timeADP)), timeADP * 1000, label = 'ADP', color = colorList[-1])
    plt.legend()
    plt.ylabel("Calculation time [ms]")
    plt.xlabel('Step')
    plt.yscale('log')
    # plt.title("Calculation time")
    plt.savefig(simu_dir + '/calculation-time-step.png', bbox_inches='tight')
    plt.close()

    # TODO: time
    plt.figure()
    plt.boxplot([time * 1000 for time in timeMPCAll] + [timeADP * 1000], patch_artist=True,widths=0.4,
                showmeans=True,
                meanprops={'marker':'+',
                        'markerfacecolor':'k',
                        'markeredgecolor':'k',
                        'markersize':5})
    plt.xticks(range(1, len(MPCStep)+2, 1), ['MPC-'+str(step) for step in MPCStep] + ['RL'])
    # plt.ylim(0,9)
    plt.yscale('log')
    plt.grid(axis='y',ls='--',alpha=0.5)
    plt.ylabel('Calculation time [ms]',fontsize=18)
    plt.savefig(simu_dir + '/boxplot-time.png', bbox_inches='tight')
    plt.close()

    # stateADPList: [x,y,phi,u,v,omega,[xr,yr,phir]]
    # controlMPCAll: [a, delta]
    # Cal relative error
    errorSaveList = []
    # Acceleration
    ADPData = controlADPList[:,0]
    MPCData = controlMPCAll[-1][:, 0]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Acceleration', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Steering Angle
    ADPData = controlADPList[:,1]
    MPCData = controlMPCAll[-1][:, 1]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Steering Angle', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Distance Error
    ADPData = np.sqrt(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2))
    MPCData = np.sqrt(np.power(stateMPCAll[-1][:, 0] - stateMPCAll[-1][:, 6], 2) + np.power(stateMPCAll[-1][:, 1] - stateMPCAll[-1][:, 7], 2))
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Distance Error', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Heading Angle
    ADPData = stateADPList[:,2] - stateADPList[:,8]
    MPCData = stateMPCAll[-1][:,2] - stateMPCAll[-1][:,8]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Heading Angle Error', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)
    
    # Utility  Function
    ADPData = rewardADP
    MPCData = rewardMPCAll[-1]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Utility  Function', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    if os.path.exists(simu_dir + "/RelError.csv")==False:
        with open(simu_dir + "/RelError.csv", 'ab') as f:
            np.savetxt(f, np.array([errorSaveList]), delimiter=',', fmt='%.4f', comments='', \
                header='Acceleration mean,max,Steering Angle mean,max,Distance Error mean,max,Heading Angle mean,max,Utility Function mean, max')
    else:
        with open(simu_dir + "/RelError.csv", 'ab') as f:
            np.savetxt(f, np.array([errorSaveList]), delimiter=',', fmt='%.4f', comments='')

    # Plot
    # stateAll: [x,y,phi,u,v,omega,[xr,yr,phir]]
    # controlAll: [a, delta]
    figSize = (20,5)
    # y v.s. x
    xADP = stateADPList[:,0]
    xMPC = [mpc[:,0] for mpc in stateMPCAll]
    xRef = stateADPList[:,6]
    yADP = stateADPList[:,1]
    yMPC = [mpc[:,1] for mpc in stateMPCAll]
    yRef = stateADPList[:,7]
    xName = 'X [m]'
    yName = 'Y [m]'
    title = 'y-x'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isRef = True, xRef = xRef, yRef = yRef, figSize='equal', lineWidth = 2)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isRef = True, xRef = xRef, yRef = yRef, lineWidth = 2)

    # distance error v.s. t
    yADP = np.sqrt(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2))*100
    yMPC = [np.sqrt(np.power(mpc[:, 0] - mpc[:, 6], 2) + np.power(mpc[:, 1] - mpc[:, 7], 2))*100 for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'Distance error [cm]'
    title = 'distance-error-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)
    Ip_ADP = np.sqrt(np.mean(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2)))
    Ip_MPC = [np.sqrt(np.mean(np.power(mpc[:, 0] - mpc[:, 6], 2) + np.power(mpc[:, 1] - mpc[:, 7], 2))) for mpc in stateMPCAll]
    print('Position error ADP: {}m'.format(Ip_ADP))
    for i in range(len(MPCStep)):
        print('Position error MPC-{}: {}m'.format(MPCStep[i], Ip_MPC[i]))

    # x error v.s. t
    yADP = stateADPList[:, 0] - stateADPList[:, 6]
    yMPC = [mpc[:, 0] - mpc[:, 6] for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'X error [m]'
    title = 'x-error-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)

    # y error v.s. t
    yADP = stateADPList[:, 1] - stateADPList[:, 7]
    yMPC = [mpc[:, 1] - mpc[:, 7] for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'Y error [m]'
    title = 'y-error-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)

    # phi v.s. t
    yADP = stateADPList[:,2] * 180/np.pi
    yMPC = [mpc[:,2] * 180/np.pi for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'Heading angle [°]'
    title = 'phi-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)

    # phi error v.s. t
    yADP = stateADPList[:,2] * 180/np.pi - stateADPList[:,8] * 180/np.pi
    yMPC = [mpc[:,2] * 180/np.pi - mpc[:,8] * 180/np.pi for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'Heading angle error [°]'
    title = 'phi-error-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)
    Iphi_ADP = np.sqrt(np.mean(np.power(stateADPList[:,2] * 180/np.pi - stateADPList[:,8] * 180/np.pi, 2)))
    Iphi_MPC = [np.sqrt(np.mean(np.power(mpc[:,2] * 180/np.pi - mpc[:,8] * 180/np.pi, 2))) for mpc in stateMPCAll]
    print('Phi error ADP: {}°'.format(Iphi_ADP))
    for i in range(len(MPCStep)):
        print('Phi error MPC-{}: {}°'.format(MPCStep[i], Iphi_MPC[i]))

    # utility v.s. t
    yADP = rewardADP
    yMPC = [mpc for mpc in rewardMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'Utility'
    title = 'utility-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)

    # accumulated utility v.s. t
    yADP = np.cumsum(rewardADP)
    yMPC = [np.cumsum(mpc) for mpc in rewardMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'Accumulated utility'
    title = 'accumulated-utility-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)
    print('Accumulated utility of ADP {:.4f}, {:.4f}% higher than MPC'.format(yADP[-1], (yADP[-1]-yMPC[-1][-1])/yMPC[-1][-1]*100))
    for i in range(len(yMPC)):
        print('Accumulated utility of MPC-{} {:.4f}, {:.4f}% higher than MPC-{}'.format(
            MPCStep[i], yMPC[i][-1], (yMPC[i][-1]-yMPC[-1][-1])/yMPC[-1][-1]*100, MPCStep[-1]))
    # a v.s. t
    yADP = controlADPList[:,0]
    yMPC = [mpc[:,0] for mpc in controlMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'a [m/s^2]'
    title = 'a-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)

    # delta v.s. t
    yADP = controlADPList[:,1] * 180/np.pi
    yMPC = [mpc[:,1] * 180/np.pi for mpc in controlMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'time [s]'
    yName = 'delta [°]'
    title = 'delta-t'
    if curveType == 'RandomTest':
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, figSize=figSize)
    else:
        comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title)
 
def simulationVirtual(MPCStep, ADP_dir, simu_dir, noise = 0, seed = 0):
    # 虚拟时域ADP、MPC应用
    print("----------------------Start Solving! seed: {}----------------------".format(seed))
    plotDelete = 0
    env = TrackingEnv()
    env.seed(seed)
    relstateDim = env.relstateDim
    actionDim = env.actionSpace.shape[0]
    policy = Actor(relstateDim, actionDim)
    policy.loadParameters(ADP_dir)
    value = Critic(relstateDim, 1)
    value.loadParameters(ADP_dir)
    solver = Solver()
    initialState = env.resetRandom(1, noise = noise) # [u,v,omega,[xr,yr,phir],x,y,phi]
    if noise == 0:
        # initialState[0, 0] += 0.01
        initialState[0, 2] = -0.05
        initialState[0, -2] = 0.8
        initialState[0, -1] = np.pi/30

    # ADP
    stateAdp = initialState.clone()
    controlADPList = np.empty(0)
    stateADPList = np.empty(0)
    rewardADP = np.empty(0)
    count = 0
    while(count < max(MPCStep)):
        stateADPList = np.append(stateADPList, stateAdp[0, -3:].numpy()) # x, y, phi
        stateADPList = np.append(stateADPList, stateAdp[0, :-3].numpy()) # u, v, omega, [xr, yr, phir]
        relState = env.relStateCal(stateAdp)
        controlAdp = policy(relState).detach()
        stateAdp, reward, done = env.stepVirtual(stateAdp, controlAdp)
        controlADPList = np.append(controlADPList, controlAdp[0].numpy())
        rewardADP = np.append(rewardADP, reward.numpy())
        count += 1
    stateADPList = np.reshape(stateADPList, (-1, env.stateDim))
    controlADPList = np.reshape(controlADPList, (-1, actionDim))
    stateADPList = np.delete(stateADPList, range(plotDelete), 0)
    controlADPList = np.delete(controlADPList, range(plotDelete), 0)
    rewardADP = np.delete(rewardADP, range(plotDelete), 0)
    saveADP = np.concatenate((stateADPList, controlADPList), axis = 1)
    with open(simu_dir + "/simulationRealADP.csv", 'wb') as f:
        np.savetxt(f, saveADP, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*env.refNum + "a,delta")

    # MPC
    controlMPCAll = []
    stateMPCAll = []
    rewardMPCAll = []
    for mpcstep in MPCStep:
        # print("MPCStep: {}".format(mpcstep))
        tempstate = initialState[0].tolist()
        stateMpc = tempstate[-3:] + tempstate[:3] # [x,y,phi,u,v,omega]
        refStateMpc = tempstate[3:-3]
        count = 0
        controlMPCList = np.empty(0) # [a, delta]
        stateMPCList = np.empty(0) # [x,y,phi,u,v,omega,[xr,yr,phir]]
        rewardMPC = np.empty(0)
        _, control = solver.MPCSolver(stateMpc, refStateMpc, mpcstep, isReal=False)
        while(count < mpcstep):
            stateMPCList = np.append(stateMPCList, np.array(stateMpc))
            stateMPCList = np.append(stateMPCList, np.array(refStateMpc))
            action = control[count].tolist()
            reward = env.calReward(stateMpc[-3:] + refStateMpc + stateMpc[:3],action,MPCflag=1)
            stateMpc = env.vehicleDynamic(
                stateMpc[0], stateMpc[1], stateMpc[2], stateMpc[3], stateMpc[4], stateMpc[5], action[0], action[1], MPCflag=1)
            refStateMpc = env.refDynamicVirtual(refStateMpc, MPCflag=1)
            rewardMPC = np.append(rewardMPC, reward)
            controlMPCList = np.append(controlMPCList, control[count])
            count += 1
        stateMPCList = np.reshape(stateMPCList, (-1, env.stateDim))
        controlMPCList = np.reshape(controlMPCList, (-1, actionDim))
        stateMPCList = np.delete(stateMPCList, range(plotDelete), 0)
        controlMPCList = np.delete(controlMPCList, range(plotDelete), 0)
        rewardMPC = np.delete(rewardMPC, range(plotDelete), 0)
        saveMPC = np.concatenate((stateMPCList, controlMPCList), axis = 1)
        with open(simu_dir + "/simulationVirtualMPC_"+str(mpcstep)+".csv", 'wb') as f:
            np.savetxt(f, saveMPC, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*env.refNum + "a,delta")
        rewardMPCAll.append(rewardMPC)
        stateMPCAll.append(stateMPCList)
        controlMPCAll.append(controlMPCList)

    # controlADPList: [x,y,phi,u,v,omega,[xr,yr,phir]]
    # controlADPList: [a, delta]
    # Cal relative error
    errorSaveList = []
    # Acceleration
    ADPData = controlADPList[:,0]
    MPCData = controlMPCAll[-1][:, 0]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Acceleration', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Steering Angle
    ADPData = controlADPList[:,1]
    MPCData = controlMPCAll[-1][:, 1]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Steering Angle', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Distance Error
    ADPData = np.sqrt(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2))
    MPCData = np.sqrt(np.power(stateMPCAll[-1][:, 0] - stateMPCAll[-1][:, 6], 2) + np.power(stateMPCAll[-1][:, 1] - stateMPCAll[-1][:, 7], 2))
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Distance Error', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    # Heading Angle
    ADPData = stateADPList[:,2] - stateADPList[:,8]
    MPCData = stateMPCAll[-1][:,2] - stateMPCAll[-1][:,8]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Heading Angle Error', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)
    
    # Utility  Function
    ADPData = rewardADP
    MPCData = rewardMPCAll[-1]
    relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Utility  Function', simu_dir = simu_dir)
    errorSaveList.append(relativeErrorMean)
    errorSaveList.append(relativeErrorMax)

    if os.path.exists(simu_dir + "/RelError.csv")==False:
        with open(simu_dir + "/RelError.csv", 'ab') as f:
            np.savetxt(f, np.array([errorSaveList]), delimiter=',', fmt='%.4f', comments='', \
                header='Acceleration mean,max,Steering Angle mean,max,Distance Error mean,max,Heading Angle mean,max,Utility Function mean, max')
    else:
        with open(simu_dir + "/RelError.csv", 'ab') as f:
            np.savetxt(f, np.array([errorSaveList]), delimiter=',', fmt='%.4f', comments='')
    
    # Plot [x,y,phi,u,v,omega,[xr,yr,phir]]
    # a v.s. t
    xADP = np.arange(0, len(controlADPList[:,0])) * env.T
    xMPC = [np.arange(0, len(mpc[:,0])) * env.T for mpc in controlMPCAll]
    yADP = controlADPList[:,0]
    yMPC = [mpc[:,0] for mpc in controlMPCAll]
    xName = 'Time [s]'
    yName = 'Acceleration [m/s^2]'
    title = 'a-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = True)

    # delta v.s. t
    xADP = np.arange(0, len(controlADPList[:,0])) * env.T
    xMPC = [np.arange(0, len(mpc[:,1])) * env.T for mpc in controlMPCAll]
    yADP = controlADPList[:,1] * 180 / np.pi
    yMPC = [mpc[:,1] * 180 / np.pi for mpc in controlMPCAll]
    xName = 'Time [s]'
    yName = 'Steering Angle [°]'
    title = 'delta-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = True)

    # distance error v.s. t
    yADP = np.sqrt(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2))
    yMPC = [np.sqrt(np.power(mpc[:, 0] - mpc[:, 6], 2) + np.power(mpc[:, 1] - mpc[:, 7], 2)) for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'Distance error [m]'
    title = 'distance-error-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = True)

    # phi error v.s. t
    yADP = (stateADPList[:,2] - stateADPList[:,8]) * 180 / np.pi
    yMPC = [(mpc[:,2] - mpc[:,8]) * 180 / np.pi for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'Heading angle error [°]'
    title = 'phi-error-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = True)

    # phi v.s. t
    yADP = stateADPList[:,2] * 180 / np.pi
    yMPC = [mpc[:,2] * 180 / np.pi for mpc in stateMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'Heading angle [°]'
    title = 'phi-t'
    xRef = np.arange(0, len(yADP)) * env.T
    yRef = stateADPList[:,8] * 180 / np.pi
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isRef = True, xRef = xRef, yRef = yRef)

    # phi error v.s. distance error
    xADP = np.sqrt(np.power(stateADPList[:, 0] - stateADPList[:, 6], 2) + np.power(stateADPList[:, 1] - stateADPList[:, 7], 2))
    xMPC = [np.sqrt(np.power(mpc[:, 0] - mpc[:, 6], 2) + np.power(mpc[:, 1] - mpc[:, 7], 2)) for mpc in stateMPCAll]
    yADP = (stateADPList[:,2] - stateADPList[:,8]) * 180 / np.pi
    yMPC = [(mpc[:,2] - mpc[:,8]) * 180 / np.pi for mpc in stateMPCAll]
    xName = 'Distance error [m]'
    yName = 'Heading angle error [°]'
    title = 'phi-error-Distance-error'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = False)

    # y v.s. x
    xADP = stateADPList[:, 0]
    xMPC = [mpc[:, 0] for mpc in stateMPCAll]
    yADP = stateADPList[:, 1]
    yMPC = [mpc[:, 1] for mpc in stateMPCAll]
    xName = 'X [m]'
    yName = 'Y [m]'
    title = 'y-x'
    xRef = stateADPList[:, 6]
    yRef = stateADPList[:, 7]
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isRef = True, xRef = xRef, yRef = yRef)

    # utility v.s. t
    yADP = rewardADP
    yMPC = [mpc for mpc in rewardMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'utility'
    title = 'utility-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = True)

    # accumulated utility v.s. t
    yADP = np.cumsum(rewardADP)
    yMPC = [np.cumsum(mpc) for mpc in rewardMPCAll]
    xADP = np.arange(0, len(yADP)) * env.T
    xMPC = [np.arange(0, len(mpc)) * env.T for mpc in yMPC]
    xName = 'Time [s]'
    yName = 'Accumulated cost'
    title = 'accumulated-cost-t'
    comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = True, isError = False)

def comparePlot(xADP, xMPC, yADP, yMPC, MPCStep, xName, yName, simu_dir, title, isMark = False, isError = False, isRef = False, xRef = None, yRef = None, figSize = None, lineWidth = 2):
    if figSize != None and figSize != 'equal':
        plt.figure(figsize=figSize, dpi=300)
    else:
        plt.figure()
    colorList = ['darkorange', 'limegreen', 'blue', 'red']
    if isMark == True:
        markerList = ['|', 'D', 'o', '*']
    else:
        markerList = ['None', 'None', 'None', 'None']
    for i in range(len(xMPC)):
        plt.plot(xMPC[i], yMPC[i], linewidth=lineWidth, color = colorList[3 - len(xMPC) + i], linestyle = '--', marker=markerList[3 - len(xMPC) + i], markersize=4)

    plt.plot(xADP, yADP , linewidth = lineWidth, color=colorList[-1],linestyle = '--', marker=markerList[-1], markersize=4)
    if isError == True:
        plt.plot([np.min(xADP), np.max(xADP)], [0,0], linewidth = lineWidth/2, color = 'grey', linestyle = '--')
        plt.legend(labels=['MPC'+str(mpcStep) for mpcStep in MPCStep] + ['ADP', 'Ref'])
    elif isRef == True:
        plt.plot(xRef, yRef, linewidth = lineWidth/2, color = 'gray', linestyle = '--')
        plt.legend(labels=['MPC'+str(mpcStep) for mpcStep in MPCStep] + ['ADP', 'Ref'])
        # plt.legend(labels=['MPC'+str(mpcStep) for mpcStep in MPCStep] + ['ADP', 'Ref'])
    else:
        plt.legend(labels=['MPC'+str(mpcStep) for mpcStep in MPCStep] + ['ADP'])
    plt.xlabel(xName)
    plt.ylabel(yName)
    # plt.savefig(simu_dir + '/' + title + '.png', bbox_inches='tight')
    plt.savefig(simu_dir + '/' + title + '.png')
    if figSize == 'equal':
        plt.axis('equal')
    else:
        plt.axis('scaled')
    plt.close()

def animationPlot(state, refstate, xName, yName):
    plt.figure()
    plt.ion()
    plt.xlabel(xName)
    plt.ylabel(yName)
    colorList = ['green', 'darkorange', 'blue', 'yellow']
    plt.xlim([min(np.min(state[:,0]), np.max(refstate[:,0])), max(np.max(state[:,0]), np.max(refstate[:,0]))])
    plt.ylim([min(np.min(state[:,1]), np.max(refstate[:,1])), max(np.max(state[:,1]), np.max(refstate[:,1]))])
    for step in range(state.shape[0]):
        plt.pause(1)
        plt.scatter(state[step][0], state[step][1], color='red', s=5)
        plt.scatter(refstate[step][0], refstate[step][1], color='blue', s=5)
    plt.pause(20)
    plt.ioff()
    plt.close()

def calRelError(ADP, MPC, title, simu_dir, isPlot = False, isPrint = True):
    maxMPC = np.max(MPC, 0)
    minMPC = np.min(MPC, 0)
    relativeError = np.abs((ADP - MPC)/(maxMPC - minMPC + 1e-3))
    relativeErrorMax = np.max(relativeError, 0)
    relativeErrorMean = np.mean(relativeError, 0)
    if isPrint == True:
        print(title +' Error | Mean: {:.4f}%, Max: {:.4f}%'.format(relativeErrorMean*100,relativeErrorMax*100))
    if isPlot == True:
        plt.figure()
        data = relativeError
        plt.hist(data, bins=30, weights = np.zeros_like(data) + 1 / len(data))
        plt.xlabel('Relative Error of '+title)
        plt.ylabel('Frequency')
        plt.title('Relative Error of '+title)
        plt.savefig(simu_dir + '/relative-error-'+title+'.png')
        plt.close()
    return relativeErrorMean, relativeErrorMax

def simuVirtualTraning(env, ADP_dir, noise = 1):
    config = MPCConfig()
    mpcstep = max(config.MPCStep)
    if env.MPCState == None:
        solver = Solver()
        env.MPCState = env.resetRandom(env.testSampleNum, noise = noise)
        env.MPCAction = []
        for testNum in range(env.testSampleNum):
            tempstate = env.MPCState[testNum].tolist()
            stateMpc = tempstate[-3:] + tempstate[:3]
            refStateMpc = tempstate[3:-3]
            _, control = solver.MPCSolver(stateMpc, refStateMpc, mpcstep, isReal=False)
            env.MPCAction.append(control)
    relstateDim = env.relstateDim
    actionDim = env.actionSpace.shape[0]
    policy = Actor(relstateDim, actionDim)
    policy.loadParameters(ADP_dir)
    count = 0
    stateAdp = env.MPCState.clone()
    controlADPList = np.empty(0)
    rewardList = np.empty(0)
    while(count < mpcstep):
        relState = env.relStateCal(stateAdp)
        controlAdp = policy(relState).detach()
        stateAdp, reward, done = env.stepVirtual(stateAdp, controlAdp)
        controlADPList = np.append(controlADPList, controlAdp.numpy())
        rewardList = np.append(rewardList, reward.numpy().mean())
        count += 1
    controlADPList =np.reshape(controlADPList, (mpcstep, env.testSampleNum, actionDim))
    ADPAction = np.array(np.transpose(controlADPList, (1, 0, 2)))
    errorAccMaxList = np.empty(0)
    errorDeltaMaxList = np.empty(0)
    for testNum in range(env.testSampleNum):
        # Acceleration
        ADPData = ADPAction[testNum][:, 0]
        MPCData = env.MPCAction[testNum][:, 0]
        relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Acceleration', simu_dir = None, isPlot = False, isPrint = False)
        errorAccMaxList = np.append(errorAccMaxList, relativeErrorMax)
        # Steering Angle
        ADPData = ADPAction[testNum][:, 1]
        MPCData = env.MPCAction[testNum][:, 1]
        relativeErrorMean, relativeErrorMax = calRelError(ADPData, MPCData, title = 'Steering Angle', simu_dir = None, isPlot = False, isPrint = False)
        errorDeltaMaxList = np.append(errorDeltaMaxList, relativeErrorMax)
    return rewardList.mean(), errorAccMaxList.mean(), errorDeltaMaxList.mean()

def main(ADP_dir):
    config = MPCConfig()
    MPCStep = config.MPCStep

    parameters = {'axes.labelsize': 20,
        'axes.titlesize': 18,
    #   'figure.figsize': (9.0, 6.5),
        'xtick.labelsize': 18,
        'ytick.labelsize': 18,
        'axes.unicode_minus': False}
    plt.rcParams.update(parameters)

    # 检查一下reward是否一样
    
    # 1. 真实时域中MPC表现
    # MPC参考点更新按照真实参考轨迹
    # 测试MPC跟踪性能
    # simu_dir = "./Simulation_dir/simulationMPC" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # os.makedirs(simu_dir, exist_ok=True)
    # simulationMPC(MPCStep, simu_dir)

    # 2. 虚拟时域中MPC表现（开环控制）
    # simu_dir = "./Simulation_dir/simulationOpen" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # os.makedirs(simu_dir, exist_ok=True)
    # simulationOpen(MPCStep, simu_dir)

    # 3. 单步ADP、MPC测试
    # simu_dir = ADP_dir + '/simulationOneStep' + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    # os.makedirs(simu_dir, exist_ok=True)
    # simulationOneStep(MPCStep, ADP_dir, simu_dir, stateNum=200)

    # 4. 真实时域ADP、MPC应用
    seed = 3
    plt.rcParams['font.size'] = 12.5
    plt.rcParams['figure.figsize'] = (8, 6.4)
    simu_dir = ADP_dir + '/simulationReal/sine'
    os.makedirs(simu_dir, exist_ok=True)
    simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'sine', seed = seed)

    simu_dir = ADP_dir + '/simulationReal/DLC'
    os.makedirs(simu_dir, exist_ok=True)
    simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'DLC', seed = seed)

    simu_dir = ADP_dir + '/simulationReal/TurnLeft'
    os.makedirs(simu_dir, exist_ok=True)
    simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'TurnLeft', seed = seed)

    simu_dir = ADP_dir + '/simulationReal/TurnRight'
    os.makedirs(simu_dir, exist_ok=True)
    simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'TurnRight', seed = seed)

    simu_dir = ADP_dir + '/simulationReal/RandomTest'
    os.makedirs(simu_dir, exist_ok=True)
    simulationReal(MPCStep, ADP_dir, simu_dir, curveType = 'RandomTest', seed = seed)
    
    # 5. 虚拟时域ADP、MPC应用
    plt.rcParams['figure.figsize'] = (9.2, 6.4)
    plt.rcParams['font.size'] = 18
    simu_dir = ADP_dir + '/simulationVirtual'
    os.makedirs(simu_dir, exist_ok=True)
    for seed in range(100):
    # for seed in [96]:
        simulationVirtual(MPCStep, ADP_dir, simu_dir, noise = 0.8, seed = seed)
    print("-"*100)
    errorList = np.loadtxt(simu_dir + "/RelError.csv", delimiter=',', skiprows=1)
    print('Mean Acceleration Error | Mean: {:.4f}%, Max: {:.4f}%'.format(np.mean(errorList[:,0])*100,np.mean(errorList[:,1])*100))
    print('Mean Steering Angle Error | Mean: {:.4f}%, Max: {:.4f}%'.format(np.mean(errorList[:,2])*100,np.mean(errorList[:,3])*100))
    print('Mean Distance Error Error | Mean: {:.4f}%, Max: {:.4f}%'.format(np.mean(errorList[:,4])*100,np.mean(errorList[:,5])*100))
    print('Mean Heading Angle Error Error | Mean: {:.4f}%, Max: {:.4f}%'.format(np.mean(errorList[:,6])*100,np.mean(errorList[:,7])*100))
    print('Mean Utility  Function Error | Mean: {:.4f}%, Max: {:.4f}%'.format(np.mean(errorList[:,8])*100,np.mean(errorList[:,9])*100))
    plt.figure()
    plt.boxplot([errorList[:, 1]*100, errorList[:, 3]*100, errorList[:, 5]*100, errorList[:, 7]*100],patch_artist=True,widths=0.4,
                showmeans=True,
                meanprops={'marker':'+',
                        'markerfacecolor':'k',
                        'markeredgecolor':'k',
                        'markersize':5})
    plt.xticks([1,2,3,4],['Acceleration','Steering Angle','Distance Error','Heading Error'])
    # plt.ylim(0,9)
    plt.grid(axis='y',ls='--',alpha=0.5)
    plt.ylabel('Maximum relative error [%]',fontsize=18)
    plt.tight_layout()
    plt.savefig(simu_dir + '/relative-error.png')
    plt.close()

def compareHorizon(ADP_list, refNum_list, seed = 0):
    simu_dir = "./Simulation_dir/compareHorizon" + datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    os.makedirs(simu_dir, exist_ok=True)
    env = TrackingEnv()
    env.seed(seed)
    env.changeRefNum(refNum_list[-1])
    config = MPCConfig()
    mpcstep = config.MPCStep[-1]
    curveType = 'RandomTest'
    envInitialState = env.resetSpecificCurve(1, curveType) # [u, v, omega, [xr, yr, phir], x, y, phi]
    rewardMPCAll = []
    stateMPCAll = []
    controlMPCAll = []
    rewardADPAll = []
    stateADPAll = []
    controlADPAll = []
    for index in range(len(refNum_list)):
        refNum = refNum_list[index]
        print("Number of reference states: {}".format(refNum))
        env.changeRefNum(refNum)
        solver = Solver(env)
        relstateDim = env.relstateDim
        actionDim = env.actionSpace.shape[0]
        initialRef = torch.zeros((1, refNum * 3))
        for i in range(refNum):
            initialRef[0, 3 * i] = env.refV * env.T * i
        initialState = torch.cat((envInitialState[:, :3], initialRef, envInitialState[:, -3:]), 1)

        # MPC
        env.randomTestReset()
        tempstate = initialState[0].tolist()
        stateMpc = tempstate[-3:] + tempstate[:3] # x, y, phi, u, v, omega
        refStateMpc = tempstate[3:-3]
        count = 0
        controlMPCList = np.empty(0)
        stateMPCList = np.empty(0)
        rewardMPC = np.empty(0)
        while(count < env.testStepReal[curveType]):
            _, control = solver.MPCSolver(stateMpc, refStateMpc, mpcstep, isReal = False)
            stateMPCList = np.append(stateMPCList, np.array(stateMpc))
            stateMPCList = np.append(stateMPCList, np.array(refStateMpc))
            action = control[0].tolist()
            reward = env.calReward(stateMpc[-3:] + refStateMpc + stateMpc[:3],action,MPCflag=1)
            stateMpc = env.vehicleDynamic(
                stateMpc[0], stateMpc[1], stateMpc[2], stateMpc[3], stateMpc[4], stateMpc[5], action[0], action[1], MPCflag=1)
            refStateMpc = env.refDynamicReal(refStateMpc, MPCflag=1, curveType=curveType)
            rewardMPC = np.append(rewardMPC, reward)
            controlMPCList = np.append(controlMPCList, control[0])
            count += 1
        stateMPCList = np.reshape(stateMPCList, (-1, env.stateDim))
        controlMPCList = np.reshape(controlMPCList, (-1, actionDim))

        saveMPC = np.concatenate((stateMPCList, controlMPCList), axis = 1)
        with open(simu_dir + "/MPCRefNum_"+str(refNum)+".csv", 'wb') as f:
            np.savetxt(f, saveMPC, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*refNum + "a,delta")
        rewardMPCAll.append(rewardMPC)
        stateMPCAll.append(stateMPCList)
        controlMPCAll.append(controlMPCList)

        # ADP
        policy = Actor(relstateDim, actionDim)
        policy.loadParameters(ADP_list[index])
        env.randomTestReset()
        stateAdp = initialState.clone()
        count = 0
        controlADPList = np.empty(0)
        stateADPList = np.empty(0)
        rewardADP = np.empty(0)
        while(count < env.testStepReal[curveType]):
            stateADPList = np.append(stateADPList, stateAdp[0, -3:].numpy()) # x, y, phi
            stateADPList = np.append(stateADPList, stateAdp[0, :-3].numpy()) # u, v, omega, [xr, yr, phir]
            relState = env.relStateCal(stateAdp)
            controlAdp = policy(relState)
            controlAdp = controlAdp.detach()
            stateAdp, reward, done = env.stepReal(stateAdp, controlAdp, curveType = curveType)
            controlADPList = np.append(controlADPList, controlAdp[0].numpy())
            rewardADP = np.append(rewardADP, reward.numpy())
            count += 1
        stateADPList = np.reshape(stateADPList, (-1, env.stateDim))
        controlADPList = np.reshape(controlADPList, (-1, actionDim))
        saveADP = np.concatenate((stateADPList, controlADPList), axis = 1)
        with open(simu_dir + "/ADPRefNum_"+str(refNum)+".csv", 'wb') as f:
            np.savetxt(f, saveADP, delimiter=',', fmt='%.4f', comments='', header="x,y,phi,u,v,omega," + "xr,yr,phir,"*refNum + "a,delta")
        rewardADPAll.append(rewardADP)
        stateADPAll.append(stateADPList)
        controlADPAll.append(controlADPList)

    # Plot
    # stateAll: [x,y,phi,u,v,omega,[xr,yr,phir]]
    # controlAll: [a, delta]
    # reward-t
    MPCsaveReward = np.empty(0)
    ADPsaveReward = np.empty(0)
    for index in range(len(refNum_list)):
        plt.figure(1)
        accRewardMPC = np.cumsum(rewardMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1)])
        MPCsaveReward = np.append(MPCsaveReward, np.array([refNum_list[index], accRewardMPC[-1]]))
        plt.plot(np.arange(0, len(accRewardMPC)) * env.T, accRewardMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(2)
        accRewardADP = np.cumsum(rewardADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1)])
        ADPsaveReward = np.append(ADPsaveReward, np.array([refNum_list[index], accRewardADP[-1]]))
        plt.plot(np.arange(0, len(accRewardADP)) * env.T, accRewardADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(1)
    plt.legend()
    plt.xlabel('Time [s]')
    plt.ylabel('Accumulated cost')
    plt.savefig(simu_dir + '/mpc_accumulate_cost.png')
    plt.figure(2)
    plt.legend()
    plt.xlabel('Time [s]')
    plt.ylabel('Accumulated cost')
    plt.savefig(simu_dir + '/adp_accumulate_cost.png')
    plt.figure(13)
    MPCsaveReward = np.reshape(MPCsaveReward, (-1, 2))
    ADPsaveReward = np.reshape(ADPsaveReward, (-1, 2))
    plt.plot(MPCsaveReward[:, 0], MPCsaveReward[:, 1], label='MPC')
    plt.plot(ADPsaveReward[:, 0], ADPsaveReward[:, 1], label='ADP')
    plt.legend()
    plt.xlabel('Number of reference states')
    plt.ylabel('Accumulated cost')
    plt.savefig(simu_dir + '/accumulate_cost.png')

    # y-x
    for index in range(len(refNum_list)):
        plt.figure(3)
        # xMPC = stateMPCAll[index][(refNum_list[index]-1):-(refNum_list[-1]-refNum_list[index]), 0] - refNum_list[index] * env.refV * env.T
        xMPC = stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0] - refNum_list[index] * env.refV * env.T
        yMPC = stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1]
        plt.plot(xMPC, yMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(4)
        xADP = stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0] - refNum_list[index] * env.refV * env.T
        yADP = stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1]
        plt.plot(xADP, yADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(3)
    plt.legend()
    plt.xlabel('X [m]')
    plt.ylabel('Y [m]')
    plt.savefig(simu_dir + '/mpc_x-y.png')
    plt.figure(4)
    plt.legend()
    plt.xlabel('X [m]')
    plt.ylabel('Y [m]')
    plt.savefig(simu_dir + '/adp_x-y.png')

    # u-t
    for index in range(len(refNum_list)):
        plt.figure(5)
        control_aMPC = controlMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0]
        plt.plot(np.arange(0, len(control_aMPC)) * env.T, control_aMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(6)
        control_aADP = controlADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0]
        plt.plot(np.arange(0, len(control_aADP)) * env.T, control_aADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(5)
    plt.legend()
    plt.ylabel('a [m/s^2]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/mpc_control_a.png')
    plt.figure(6)
    plt.legend()
    plt.ylabel('a [m/s^2]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/adp_control_a.png')
    for index in range(len(refNum_list)):
        plt.figure(7)
        control_deltaMPC = controlMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1] * 180/np.pi
        plt.plot(np.arange(0, len(control_deltaMPC)) * env.T, control_deltaMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(8)
        control_deltaADP = controlADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1] * 180/np.pi
        plt.plot(np.arange(0, len(control_deltaADP)) * env.T, control_deltaADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(7)
    plt.legend()
    plt.ylabel('delta [°]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/mpc_control_delta.png')
    plt.figure(8)
    plt.legend()
    plt.ylabel('delta [°]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/adp_control_delta.png')

    # distance error-t
    # [x,y,phi,u,v,omega,[xr,yr,phir]]
    for index in range(len(refNum_list)):
        plt.figure(9)
        distanceErrorMPC = \
            np.cumsum(np.sqrt(np.power(stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0]\
            -stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 6],2)\
            +np.power(stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1]
            -stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 7],2)))
        plt.plot(np.arange(0, len(distanceErrorMPC)) * env.T , distanceErrorMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(10)
        distanceErrorADP = np.cumsum(np.sqrt(np.power(stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 0]\
            -stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 6],2)\
            +np.power(stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 1]
            -stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 7],2)))
        plt.plot(np.arange(0, len(distanceErrorADP)) * env.T , distanceErrorADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(9)
    plt.legend()
    plt.ylabel('Accumulated Distance Error [m]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/mpc_cumdistance_error-t.png')
    plt.figure(10)
    plt.legend()
    plt.ylabel('Accumulated Distance Error [m]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/adp_cumdistance_error-t.png')

    # heading error-t
    # [x,y,phi,u,v,omega,[xr,yr,phir]]
    for index in range(len(refNum_list)):
        plt.figure(11)
        headingErrorMPC = np.cumsum(np.abs(stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 2]\
            -stateMPCAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 8]))*180/np.pi
        plt.plot(np.arange(0, len(headingErrorMPC)) * env.T , headingErrorMPC, label = 'RefNum='+str(refNum_list[index]))
        plt.figure(12)
        headingErrorADP = np.cumsum(np.abs(stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 2]\
            -stateADPAll[index][refNum_list[index]-1:-(refNum_list[-1]-refNum_list[index]+1), 8]))*180/np.pi
        plt.plot(np.arange(0, len(headingErrorADP)) * env.T , headingErrorADP, label = 'RefNum='+str(refNum_list[index]))
    plt.figure(11)
    plt.legend()
    plt.ylabel('Accumulated Heading Error [°]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/mpc_cumheading_error-t.png')
    plt.figure(12)
    plt.legend()
    plt.ylabel('Accumulated Heading Error [°]')
    plt.xlabel('Time [s]')
    plt.savefig(simu_dir + '/adp_cumheading_error-t.png')

if __name__ == '__main__':
    ADP_dir = './Results_dir/2023-01-06-11-43-31'
    main(ADP_dir)

    # parameters = {'axes.labelsize': 14,
    #     'axes.titlesize': 14,
    # #   'figure.figsize': (9.0, 6.5),
    #     'xtick.labelsize': 14,
    #     'ytick.labelsize': 14,
    #     'axes.unicode_minus': False}
    # plt.rcParams.update(parameters)
    # # file_list = ['2022-11-16-15-41-50', \
    # #     '2022-10-10-10-37-05',\
    # #     '2022-10-10-19-49-19',\
    # #     '2022-10-11-13-27-08',\
    # #     '2022-10-13-00-46-36',\
    # #     '2022-10-13-12-03-24',\
    # #     '2022-10-14-23-12-25',\
    # #     '2022-10-15-16-56-55',\
    # #     '2022-11-18-11-06-35']
    # file_list = ['2023-01-06-11-43-17',\
    #     '2023-01-06-11-43-31',\
    #     '2023-01-06-11-43-42',\
    # ]
    # ADP_list = ['./Results_dir/' + file for file in file_list]
    # # refNum_list = [2, 3, 4, 5, 6, 7, 8, 9, 10]
    # refNum_list = [6, 6, 6]
    # compareHorizon(ADP_list, refNum_list)