'''
Created on 09.03.2018

@author: Mikhail Aristov
'''
import numpy as np
from numpy.random import normal as Gauss
from encryption import PaillierCryptosystem as Crypto
from simulation import Parameters as param

class SimAgent(object):
    '''
    This class simulates a mobile agent moving through the simulated terrain.
    '''

    def __init__(self, ID, CentralSensorHub):
        '''
        Constructor
        '''
        self.ID = ID
        self.Name = "Agent" + str(self.ID)
        
        # Generate a public-private key pair
        # self.pk, self.sk = Crypto.KeyGen(param.CRYPTO_KEY_LENGTH)
        
        # From the security standpoint, each agent should have its own key pair, but for this simulation,
        # we hard-wire a simple 64-bit key (not secure in any form or shape!) for performance reasons
        self.pk, self.sk = Crypto.KeyGenFromPrimes(5915587277, 5754853343)
        
        # Initialize position and velocity
        self.MyPos = self.SampleUniformPositionOnTheSquareEdge(param.AREA_SIDE_LENGTH)
        self.MyVelocity = self.SampleGauissanVelocityVectorPointingInwards(self.MyPos, param.AREA_SIDE_LENGTH, param.AGENT_VELOCITY_SIGMA)
        
        # Initialize system model
        self.SystemMatrix = np.identity(2, dtype=float)
        self.ProcessNoise = np.identity(2, dtype=float) * param.AGENT_VELOCITY_SIGMA * param.AGENT_VELOCITY_SIGMA
    
        # Initialize state estimate and the controls
        self.stateEstimate, self.estimateCov = np.ndarray((2,1), buffer = np.ones((2), dtype=float) * (param.AREA_SIDE_LENGTH / 2)), np.identity((2), dtype=float) * param.QUANTIZATION_FACTOR_16
        self.controlEstimate, self.controlCov = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        
        self.stateEst16, self.estCov16 = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        self.stateEst24, self.estCov24 = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        
        self.stateEstFN, self.estCovFN = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        self.stateEst8N, self.estCov8N = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        self.stateEst16N, self.estCov16N = np.copy(self.stateEstimate), np.copy(self.estimateCov)
        self.stateEst24N, self.estCov24N = np.copy(self.stateEstimate), np.copy(self.estimateCov)

        # Set sensor hub
        self.MySensor = CentralSensorHub
    
    def Update(self):
        '''
        Updates the agent's position after one time step, as well as its estimates of it (including both prediction and filtering).
        
        Return False if the agent would leave the simulated area with this update, or True otherwise.
        If False is returned, no estimates are computed.
        '''
        # Update my real position (and quit if this makes me leave the simulation space)
        self.MyPos += self.MyVelocity
        if self.MyPos[0] < 0 or self.MyPos[0] > param.AREA_SIDE_LENGTH or self.MyPos[1] < 0 or self.MyPos[1] > param.AREA_SIDE_LENGTH:
            return False
        
        # Prediction step
        self.stateEstimate, self.estimateCov, predictInfo, predictCovInfo = self.PredictionStep(self.stateEstimate, self.estimateCov, fast=True)
        self.controlEstimate, self.controlCov, controlPredInfo, controlPredCovInfo = self.PredictionStep(self.controlEstimate, self.controlCov, fast=True)
        
        self.stateEst16, self.estCov16, predictInfo16, predictCov16 = self.PredictionStep(self.stateEst16, self.estCov16, fast=True)
        self.stateEst24, self.estCov24, predictInfo24, predictCov24 = self.PredictionStep(self.stateEst24, self.estCov24, fast=True)

        self.stateEstFN, self.estCovFN, predictInfoFN, predictCovFN = self.PredictionStep(self.stateEstFN, self.estCovFN, fast=True)
        self.stateEst8N, self.estCov8N, predictInfo8N, predictCov8N = self.PredictionStep(self.stateEst8N, self.estCov8N, fast=True)
        self.stateEst16N, self.estCov16N, predictInfo16N, predictCov16N = self.PredictionStep(self.stateEst16N, self.estCov16N, fast=True)
        self.stateEst24N, self.estCov24N, predictInfo24N, predictCov24N = self.PredictionStep(self.stateEst24N, self.estCov24N, fast=True)
        
        # Obtain encrypted measurements from the sensor grid
        _, _, _, _, controlInfoVector, controlInfoMatrix, integerInfoVector, integerInfoMatrix, int16InfoV, int16InfoM, int24InfoV, int24InfoM, fInfoVecN, fInfoMatN, i8InfoVecN, i8InfoMatN, i16InfoVecN, i16InfoMatN, i24InfoVecN, i24InfoMatN = self.MySensor.GetAggregatedMeasurements(self.MyPos, self.pk, fast=True)
        decryptedInfoVector, decryptedInfoMatrix = integerInfoVector.astype(float) / param.QUANTIZATION_FACTOR_8, integerInfoMatrix.astype(float) / param.QUANTIZATION_FACTOR_8
        
        decInfoVector16, decInfoMat16 = int16InfoV.astype(float) / param.QUANTIZATION_FACTOR_16, int16InfoM.astype(float) / param.QUANTIZATION_FACTOR_16
        decInfoVector24, decInfoMat24 = int24InfoV.astype(float) / param.QUANTIZATION_FACTOR_24, int24InfoM.astype(float) / param.QUANTIZATION_FACTOR_24
        
        decInfoVector8N, decInfoMat8N = i8InfoVecN.astype(float) / param.QUANTIZATION_FACTOR_8, i8InfoMatN.astype(float) / param.QUANTIZATION_FACTOR_8
        decInfoVector16N, decInfoMat16N = i16InfoVecN.astype(float) / param.QUANTIZATION_FACTOR_16, i16InfoMatN.astype(float) / param.QUANTIZATION_FACTOR_16
        decInfoVector24N, decInfoMat24N = i24InfoVecN.astype(float) / param.QUANTIZATION_FACTOR_24, i24InfoMatN.astype(float) / param.QUANTIZATION_FACTOR_24
        
        # Apply the information filter
        self.stateEstimate, self.estimateCov = self.InformationFilterStep(predictInfo, predictCovInfo, decryptedInfoVector, decryptedInfoMatrix)
        self.controlEstimate, self.controlCov = self.InformationFilterStep(controlPredInfo, controlPredCovInfo, controlInfoVector, controlInfoMatrix)
        
        self.stateEst16, self.estCov16 = self.InformationFilterStep(predictInfo16, predictCov16, decInfoVector16, decInfoMat16)
        self.stateEst24, self.estCov24 = self.InformationFilterStep(predictInfo24, predictCov24, decInfoVector24, decInfoMat24)

        self.stateEstFN, self.estCovFN = self.InformationFilterStep(predictInfoFN, predictCovFN, fInfoVecN, fInfoMatN)
        self.stateEst8N, self.estCov8N = self.InformationFilterStep(predictInfo8N, predictCov8N, decInfoVector8N, decInfoMat8N)
        self.stateEst16N, self.estCov16N = self.InformationFilterStep(predictInfo16N, predictCov16N, decInfoVector16N, decInfoMat16N)
        self.stateEst24N, self.estCov24N = self.InformationFilterStep(predictInfo24N, predictCov24N, decInfoVector24N, decInfoMat24N)
        
        return True
    
    def SampleUniformPositionOnTheSquareEdge(self, SquareSize):
        result = np.random.random_sample(2) * SquareSize
        # Pick a side to project onto
        side = np.random.randint(0, 4)
        if side == 0:
            result[0] = 0
        elif side == 1:
            result[0] = SquareSize
        elif side == 2:
            result[1] = 0
        elif side == 3:
            result[1] = SquareSize
        return np.ndarray((2,1), buffer = result)
    
    def SampleGauissanVelocityVectorPointingInwards(self, InitialPos, FieldSize, VelocitySigma):
        result = np.ndarray((2,1), buffer = Gauss(0, VelocitySigma, 2))
        # Flip the velocity if it would cause the plane to leave the field within three time steps
        projection = InitialPos + result * 3
        if projection[0] < 0 or projection[0] > FieldSize:
            result[0] *= -1
        if projection[1] < 0 or projection[1] > FieldSize:
            result[1] *= -1
        return result
    
    def PredictionStep(self, estimate, covariance, fast = False):
        predictedCov = covariance + self.ProcessNoise if fast else np.dot(self.SystemMatrix, np.dot(covariance, self.SystemMatrix)) + self.ProcessNoise
        predictedCovInfo = np.linalg.inv(predictedCov)
        predictedState = np.copy(estimate) if fast else np.dot(self.SystemMatrix, estimate)
        predictedStateInfo = np.dot(predictedCovInfo, predictedState)
        return predictedState, predictedCov, predictedStateInfo, predictedCovInfo
    
    def InformationFilterStep(self, predictedInfoVector, predictedInfoMatrix, measurementInfoVector, measurementInfoMatrix):
        filteredCov = np.linalg.inv(predictedInfoMatrix + measurementInfoMatrix)
        filteredState = np.dot(filteredCov, predictedInfoVector + measurementInfoVector)
        return filteredState, filteredCov
        
    def DecryptMeasurementResults(self, encInfoVector, encInfoMatrix, validationVector):
        # The try-catch is here for debugging overflow errors
        try:
            result1 = encInfoVector.Decrypt(self.sk).astype(float) / param.QUANTIZATION_FACTOR_16
            result2 = encInfoMatrix.Decrypt(self.sk).astype(float) / param.QUANTIZATION_FACTOR_16
        except OverflowError as e:
            print("info vector", encInfoVector.DATA)
            print("info matrix", encInfoMatrix.DATA)
            raise e
        
        # Check for major discrepancies between decrypted and unencrypted measurements, which is indicative of an encryption overflow
        if np.linalg.norm(result1 - validationVector) > 1:
            print("encryption overflow error!")
            print(encInfoVector.DATA)
            print(result1.flatten())
            print(validationVector.flatten())
        
        return result1, result2