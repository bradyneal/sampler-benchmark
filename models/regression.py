"""
This module provides functions for sampling from the posteriors of various
regression models. The supported models are specified in the
REGRESSION_MODEL_NAMES constant.
"""

import pymc3 as pm

import theano.tensor as tt

from data.preprocessing.format import numpy_to_dataframe
from .utils import format_trace, get_pairwise_formula, get_quadratic_formula, \
                   get_linear_formula, join_nonempty
from .nn import sample_shallow_nn
from . import NUM_SAMPLES
from .utils import reduce_data_dimension

REGRESSION_MODEL_NAMES = [
    'ls_linear', 'ls_pairwise_linear', 'ls_quadratic_linear',
    # 'robust_linear', 'robust_pairwise_linear', 'robust_quadratic_linear',
    'shallow_nn', 'gp']


def sample_regression_model(model_name, X, y, num_samples=NUM_SAMPLES,
                            num_non_categorical=None):
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
    d = X.shape[1]
    X = reduce_data_dimension(X, model_name)
    reduced_d = X.shape[1]
    if reduced_d < d:
        num_non_categorical = reduced_d
        
    if 'ls_linear' == model_name:
        sample_ls_linear(X, y, num_samples)
    elif 'ls_pairwise_linear' == model_name:
        sample_ls_pairwise(X, y, num_non_categorical, num_samples)
    elif 'ls_quadratic_linear' == model_name:
        sample_ls_quadratic(X, y, num_non_categorical, num_samples)
    elif 'robust_linear' == model_name:
        sample_robust_linear(X, y, num_samples)
    elif 'robust_pairwise_linear' == model_name:
        sample_robust_pairwise(X, y, num_non_categorical, num_samples)
    elif 'robust_quadratic_linear' == model_name:
        sample_robust_quadratic(X, y, num_non_categorical, num_samples)
    elif 'shallow_nn' == model_name:
        sample_shallow_nn_regres(X, y, num_samples)
    elif 'gp' == model_name:
        sample_gp(X, y, num_samples)
    else:
        raise ValueError('Unsupported model: {}\nSupported models: {}'
                         .format(model_name, REGRESSION_MODEL_NAMES))


# GLM Defaults
# intercept:  flat prior
# weights:    N(0, 10^6) prior
# likelihood: Normal

def sample_linear(X, y, num_samples=NUM_SAMPLES, robust=False):
    """
    Sample from Bayesian linear model (abstraction of least squares and robust
    linear models that correspond to Normal and Student's T likelihoods
    respectively).
    """
    with pm.Model():
        if robust:
            pm.GLM(X, y, family=pm.glm.families.StudentT())
        else:
            pm.GLM(X, y)
        trace = pm.sample(num_samples)
    return format_trace(trace)


def sample_ls_linear(X, y, num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Least Squares Linear Regression. Uses Normal
    likelihood, which is equivalent to minimizing the mean squared error
    in the frequentist version of Least Squares.
    """
    return sample_linear(X, y, num_samples=NUM_SAMPLES)


def sample_robust_linear(X, y, num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Robust Regression. Uses Student's T likelihood as it
    has heavier tails than the Normal likelihood, allowing it to place less
    emphasis on outliers.
    """
    return sample_linear(X, y, num_samples=NUM_SAMPLES, robust=True)


def sample_interaction_linear(X, y, num_non_categorical=None,
                              num_samples=NUM_SAMPLES,
                              robust=False, interaction='pairwise'):
    """
    Sample from Bayesian linear models with interaction and higher order terms
    (abstraction of all linear regressions that have nonlinear data terms).

    Assumptions:
    1. all non-categorial variables come first in the ordering
    2. all variables are non-categorical if num_non_categorical isn't given
    """
    d = X.shape[1]
    if num_non_categorical is None:
        num_non_categorical = d
    data_df = numpy_to_dataframe(X, y)
    with pm.Model():
        if 'pairwise' == interaction:
            interaction_formula = get_pairwise_formula(num_non_categorical)
        elif 'quadratic' == interaction:
            interaction_formula = get_quadratic_formula(num_non_categorical)
        x_formula = join_nonempty(
            (interaction_formula,
             get_linear_formula(num_non_categorical + 1, d))
        )
        if robust:
            pm.GLM.from_formula('y ~ ' + x_formula, data_df,
                                family=pm.glm.families.StudentT())
        else:
            pm.GLM.from_formula('y ~ ' + x_formula, data_df)
        trace = pm.sample(num_samples)
    return format_trace(trace)


def sample_ls_pairwise(X, y, num_non_categorical=None,
                       num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Least Squares Linear Regression that has pairwise
    interaction terms between all non-categorial variables. Uses Normal
    likelihood, which is equivalent to minimizing the mean squared error
    in the frequentist version of Least Squares.

    Assumptions:
    1. all non-categorial variables come first in the ordering
    2. all variables are non-categorical if num_non_categorical isn't given
    """
    return sample_interaction_linear(
        X, y, num_non_categorical=num_non_categorical,
        num_samples=num_samples, interaction='pairwise')


def sample_ls_quadratic(X, y, num_non_categorical=None,
                        num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Least Squares Linear Regression that has all first and
    second order non-categorical data terms. Uses Normal likelihood, which is
    equivalent to minimizing the mean squared error in the frequentist version
    of Least Squares.

    Assumptions:
    1. all non-categorial variables come first in the ordering
    2. all variables are non-categorical if num_non_categorical isn't given
    """
    return sample_interaction_linear(
        X, y, num_non_categorical=num_non_categorical,
        num_samples=num_samples, interaction='quadratic')


def sample_robust_pairwise(X, y, num_non_categorical=None,
                           num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Robust Linear Regression that has pairwise
    interaction terms between all non-categorial variables. Uses Student's T
    likelihood as it has heavier tails than the Normal likelihood, allowing it
    to place less emphasis on outliers.

    Assumptions:
    1. all non-categorial variables come first in the ordering
    2. all variables are non-categorical if num_non_categorical isn't given
    """
    return sample_interaction_linear(
        X, y, num_non_categorical=num_non_categorical, robust=True,
        num_samples=num_samples, interaction='pairwise')


def sample_robust_quadratic(X, y, num_non_categorical=None,
                            num_samples=NUM_SAMPLES):
    """
    Sample from Bayesian Robust Linear Regression that has all first and
    second order non-categorical data terms. Uses Student's T likelihood as it
    has heavier tails than the Normal likelihood, allowing it to place less
    emphasis on outliers.

    Assumptions:
    1. all non-categorial variables come first in the ordering
    2. all variables are non-categorical if num_non_categorical isn't given
    """
    return sample_interaction_linear(
        X, y, num_non_categorical=num_non_categorical, robust=True,
        num_samples=num_samples, interaction='quadratic')


def sample_shallow_nn_regres(X, y, num_samples=NUM_SAMPLES):
    """
    Sample from shallow Bayesian neural network, using variational inference.
    Uses Normal likelihood.
    """
    return sample_shallow_nn(X, y, 'regression')


def build_pm_gp_cov(D, cov_f='ExpQuad'):
    cov_dict = {'ExpQuad': pm.gp.cov.ExpQuad,
                'Exponential': pm.gp.cov.Exponential,
                'Matern32': pm.gp.cov.Matern32,
                'Matern52': pm.gp.cov.Matern52}

    log_ls = pm.Uniform('log_ls', lower=-2.0, upper=3.0)
    ls = pm.Deterministic('ls', tt.exp(log_ls))

    if cov_f == 'RatQuad':
        log_alpha = pm.Uniform('log_alpha', lower=-2.0, upper=5.0)
        alpha = pm.Deterministic('alpha', tt.exp(log_alpha))
        K = pm.gp.cov.RatQuad(D, ls=ls, alpha=alpha)
    else:
        assert(cov_f in cov_dict)  # TODO change to some type of better error
        cov_class = cov_dict[cov_f]
        K = cov_class(D, ls)
    return K


def sample_gp(X, y, cov_f='ExpQuad', num_samples=NUM_SAMPLES):
    """Sample from Gaussian Process"""
    # TODO also implement version that uses Elliptical slice sampling
    N, D = X.shape

    with pm.Model():
        # uninformative prior on the function variance
        log_s2_f = pm.Uniform('log_s2_f', lower=-10.0, upper=5.0)
        s2_f = pm.Deterministic('s2_f', tt.exp(log_s2_f))

        # covariance functions for the function f and the noise
        f_cov = s2_f * build_pm_gp_cov(D, cov_f)

        # uninformative prior on the noise variance
        log_s2_n = pm.Uniform('log_s2_n', lower=-10.0, upper=5.0)
        s2_n = pm.Deterministic('s2_n', tt.exp(log_s2_n))

        pm.gp.GP('y_obs', cov_func=f_cov, sigma=s2_n,
                 observed={'X': X, 'Y': y})

        trace = pm.sample(num_samples)
    return format_trace(trace)
