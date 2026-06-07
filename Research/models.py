import pandas as pd
import numpy as np
import re
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold, cross_val_score

class FullGDLinearRegression(BaseEstimator, RegressorMixin):
    def __init__(self, learning_rate=0.01, n_iterations=1000, random_state=None):
        self.learning_rate = learning_rate
        self.n_iterations = n_iterations
        self.random_state = random_state
        self.weights_ = None
        self.bias_ = None
        
    def fit(self, X, y):
        X_arr = np.array(X)
        y_arr = np.array(y)
        
        n_samples, n_features = X_arr.shape
        
        rng = np.random.default_rng(self.random_state)
        self.weights_ = rng.normal(0, 0.01, n_features)
        self.bias_ = 0.0
        
        for _ in range(self.n_iterations):
            y_pred = np.dot(X_arr, self.weights_) + self.bias_
            error = y_pred - y_arr
            
            dw = (2 / n_samples) * np.dot(X_arr.T, error)
            db = (2 / n_samples) * np.sum(error)
            
            self.weights_ -= self.learning_rate * dw
            self.bias_ -= self.learning_rate * db
            
        return self
        
    def predict(self, X):
        return np.dot(np.array(X), self.weights_) + self.bias_