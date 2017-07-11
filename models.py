"""
This module provides functions for sampling from the posteriors of various
different models. The supported models are specified in the MODEL_NAMES
constant.
"""

import pymc3 as pm

MODEL_NAMES = ['glm', 'gp']
NUM_SAMPLES = 5000


def sample_model(model_name, X, y, num_samples=NUM_SAMPLES):
    """
    Sample from the posteriors of any of the supported models
    
    Args:
        model_name: to specify which model to sample from
        X: data matrix
        y: targets
        num_samples: number points to sample from the model posterior
    
    Returns:
        samples (in currently undecided format)
        
    Raises:
        ValueError: if the specified model name is not supported
    """
    return {
        'glm': sample_glm(X, y, num_samples),
        'gp' : sample_gp(X, y, num_samples)
    }.get(model_name, unsupported_model(model_name))

    def unsupported_model(model_name):
        raise ValueError('Unsupported model: {}\nSupported models: {}'
                         .format(model_name, MODEL_NAMES))
    
    
def sample_glm(X, y, num_samples=NUM_SAMPLES):
    """Sample from Generalized Linear Model"""
    pm.GLM(X, y)
    trace = pm.sample(num_samples)
    return trace
    

def sample_gp(X, y, num_samples=NUM_SAMPLES):
    """Sample from Gaussian Process"""
    raise NotImplementedError(
        'The Gaussian Process model is not yet implemented.')