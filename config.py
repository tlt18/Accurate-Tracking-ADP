import math
import numpy as np

class trainConfig():
    def __init__(self):
        self.iterationMax = 50000
        self.iterationPrint = 100
        self.iterationSave = 1000
        self.lrPolicy = 1e-3
        self.lrValue = 1e-2
        # self.lrPolicy = 1e-5
        # self.lrValue = 1e-4
        # need to match
        self.stepForwardPEV = 20
        self.gammar = 0.95

        self.lifeMax = 20
        self.batchSize = 256


class vehicleDynamic():
    def __init__(self):
        self.refV = 5
        # y_r = curveA * sin(curveK * x_r)
        self.curveK = 1/6
        self.curveA = 1
        # Double lane chang
        self.DLCh = 2
        self.DLCa = 25
        self.DLCb = 30
        self.curvePhi = np.pi/60

        # 车辆参数
        # TODO: 参数是否合理？
        self.T = 0.1  # 时间间隔
        self.m = 1520  # 自车质量
        self.a = 1.19  # 质心到前轴的距离
        self.b = 1.46  # 质心到后轴的距离
        self.kf = -155495  # 前轮总侧偏刚度
        self.kr = -155495  # 后轮总侧偏刚度
        self.Iz = 2642  # 转动惯量

        # 初始状态
        self.initState = [0, 0, math.atan(self.curveA * self.curveK), self.refV, 0, 0]
        self.testStepReal = {'sine': 200, 'DLC': 300, 'TurnLeft': 30, 'TurnRight': 30}
        self.testStepVirtual = 40
        self.testSampleNum = 100
        self.renderStep = 100
        self.refNum = 3

class MPCConfig():
    def __init__(self):
        self.MPCStep = [10, 30, 60]
        config = trainConfig()
        self.gammar = config.gammar
        # self.MPCStep = [205, 210, 220, 240]
        # self.MPCStep = [100]

