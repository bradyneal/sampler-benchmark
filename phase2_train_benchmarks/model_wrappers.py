# Ryan Turner (turnerry@iro.umontreal.ca)
import os
import warnings
import numpy as np
from numpy.linalg.linalg import LinAlgError
import scipy.stats as ss
from scipy.misc import logsumexp
from sklearn.mixture import BayesianGaussianMixture, GaussianMixture

# IGN stuff
import bench_models.ign.ign as ign
import bench_models.ign.t_util as t_util

# RNADE stuff
from bench_models.nade.Data import Dataset, BigDataset
import bench_models.nade.NADE as NADE
import bench_models.nade.Instrumentation as Instrumentation
import bench_models.nade.Backends as Backends
import bench_models.nade.Optimization as Optimization
import bench_models.nade.TrainingController as TrainingController
from bench_models.nade.Utils.DropoutMask import create_dropout_masks
from bench_models.nade.Utils.theano_helpers import floatX


class Gaussian():
    def __init__(self, diag=False):
        self.diag = diag
        self.mu = None
        self.cov = None

    def fit(self, X):
        self.mu = np.mean(X, axis=0)
        if self.diag:
            self.cov = np.diag(np.var(X, axis=0))
        else:
            self.cov = np.cov(X, rowvar=False, bias=True)

    def score_samples(self, X):
        return self.loglik_chk(X, self.get_params_())

    def get_params_(self):
        D = {'mean': self.mu, 'covariance': self.cov}
        return D

    @staticmethod
    def loglik_chk(X, params):
        # Could be more efficient in diag case later
        logpdf = ss.multivariate_normal.logpdf(X, params['mean'],
                                               params['covariance'])
        return logpdf


def mvn_logpdf_from_chol(X, mu, inv_chol_U_cov):
    '''inv_chol_U_cov = inv(chol(covariance).T) where chol return tril mat.'''
    assert(X.ndim == 2)
    D = X.shape[1]
    assert(mu.shape == (D,) and inv_chol_U_cov.shape == (D, D))
    # This has overhead, but there is too much potential for confusion to skip
    assert(np.allclose(inv_chol_U_cov, np.triu(inv_chol_U_cov)))

    log_det_cov = -2.0 * np.sum(np.log(np.diag(inv_chol_U_cov)))
    dev = X - mu[None, :]
    maha = np.sum(np.square(np.dot(dev, inv_chol_U_cov)), axis=1)
    return -0.5 * (D * np.log(2 * np.pi) + log_det_cov + maha)


def get_params_mixture(mixture):
    '''Add get_params object to BayesianGaussianMixture.'''
    D = {'weights': mixture.weights_, 'means': mixture.means_,
         'covariances': mixture.covariances_, 'type': mixture.covariance_type,
         'precisions_cholesky': mixture.precisions_cholesky_}

    # Verify sklearn is coherent and consistent with precisions_cholesky
    for cc in xrange(D['precisions_cholesky'].shape[0]):
        chol_U = np.linalg.inv(D['precisions_cholesky'][cc, :, :])
        cov = np.dot(chol_U.T, chol_U)
        assert(np.allclose(cov, D['covariances'][cc, :, :]))
    return D


def loglik_mixture(X, params):
    '''Indep check of loglik instead of just using self reported in
    original class. This could be made into some sort of static method
    since we never use self.'''
    # other types not yet supported
    assert(params['type'] == 'full')

    N = X.shape[0]

    w = params['weights']
    w = w / np.sum(w)  # Just to be sure normalized

    loglik = np.zeros((N, len(w)))
    for ii in xrange(len(w)):
        mu = params['means'][ii, :]
        prec_U = params['precisions_cholesky'][ii, :, :]
        # More efficient and stable than normal mvn log pdf
        gauss_part = mvn_logpdf_from_chol(X, mu, prec_U)

        # Now check against traditional mvn in scipy
        S = params['covariances'][ii, :, :]
        try:
            gauss_part_chk = ss.multivariate_normal.logpdf(X, mu, S)
            # TODO eventually move to numerical logger
            if not np.allclose(gauss_part, gauss_part_chk):
                err = np.max(np.abs(gauss_part_chk - gauss_part))
                print 'gauss chk log10 err: %f' % np.log10(err)
        except LinAlgError:
            pass  # Sometimes it is just hard to do cholesky

        loglik[:, ii] = np.log(w[ii]) + gauss_part
    loglik = logsumexp(loglik, axis=1)
    return loglik


class GaussianMixture_(GaussianMixture):
    '''We could use multiple inheritence to enforce that all these classes have
    a get_params() method, but that might be more trouble than it is worth.'''

    def get_params_(self):
        # Way to do these functions with =??
        return get_params_mixture(self)

    @staticmethod
    def loglik_chk(X, params):
        return loglik_mixture(X, params)


class BayesianGaussianMixture_(BayesianGaussianMixture):
    def get_params_(self):
        # Way to do these functions with =??
        return get_params_mixture(self)

    @staticmethod
    def loglik_chk(X, params):
        return loglik_mixture(X, params)


class IGN:
    def __init__(self, n_layers=1, WL_init=1e-2, reg_dict={}, valid_frac=0.2,
                 gauss_basepdf=True, n_epochs=100, batch_size=32, lr=1e-3):
        self.n_layers = n_layers
        self.WL_init = WL_init
        self.reg_dict = reg_dict
        self.n_epochs = n_epochs
        self.batch_size = batch_size
        self.valid_frac = valid_frac
        self.lr = lr

        # Only parts that need to be saved in param extraction
        self.gauss_basepdf = gauss_basepdf
        self.fit_layers = None

        self.base_logpdf = t_util.norm_logpdf_T if self.gauss_basepdf \
            else t_util.t_logpdf_T

    def fit(self, X):
        N, D = X.shape
        n_train = int(np.ceil((1.0 - self.valid_frac) * N))

        # Could also have setting in there for trying LU vs full training
        layers = ign.init_ign(self.n_layers, D, aL_val=0.95, rnd_W=True)
        layers = ign.fit_base_layer(X, layers)
        # Chunk some in validation
        R = ign.train_ign(X[:n_train, :], X[n_train:, :], layers,
                          self.reg_dict, base_logpdf=self.base_logpdf,
                          lr=self.lr, n_epochs=self.n_epochs,
                          batch_size=self.batch_size)
        _, _, _, self.fit_layers = R

    def score_samples(self, X):
        assert(self.fit_layers is not None)
        logpdf, _ = ign.ign_log_pdf(X, self.fit_layers, self.base_logpdf)
        return logpdf

    def get_params_(self):
        assert(self.fit_layers is not None)
        # Make a copy, maybe we should even make a deep copy
        D = dict(self.fit_layers)
        D['gauss_basepdf'] = self.gauss_basepdf
        return D

    @staticmethod
    def loglik_chk(X, params):
        base_logpdf = t_util.norm_logpdf_T if params['gauss_basepdf'] \
            else t_util.t_logpdf_T

        layers = dict(params)
        # ign_log_pdf() checks if there are any extra elements in param dict
        del layers['gauss_basepdf']
        logpdf, _ = ign.ign_log_pdf(X, layers, base_logpdf)
        return logpdf


class RNADE:
    def __init__(self, n_hidden=100, h_layers=2, n_components=10, epochs=20,
                 pretraining_epochs=5, validation_loops=20, valid_frac=0.2,
                 lr=0.02, epoch_size=100, batch_size=100, momentum=0.9,
                 dataset_name='RNADE_test_run', scratch_dir='.'):
        self.dataset_name = dataset_name
        self.scratch_dir = scratch_dir

        self.n_hidden = n_hidden
        self.h_layers = h_layers
        self.n_components = n_components
        self.nonlinearity = 'RLU'  # Might just want to hard code this one

        self.epochs = epochs
        self.pretraining_epochs = pretraining_epochs
        self.validation_loops = validation_loops

        self.lr = lr
        self.epoch_size = epoch_size
        self.batch_size = batch_size
        self.momentum = momentum
        self.valid_frac = valid_frac

        self.nade_class = NADE.OrderlessMoGNADE
        self.nade_obj = None

    def fit(self, X):
        # This function is a mess, it comes from original RNADE code, I won't
        # even bother to fully clean this up.

        N, n_visible = X.shape
        n_train = int(np.ceil((1.0 - self.valid_frac) * N))

        training_dataset = Dataset(X[:n_train, :])
        validation_dataset = Dataset(X[n_train:, :])

        masks_filename = self.dataset_name + "." + floatX + ".masks"
        masks_route = os.path.join(self.scratch_dir, masks_filename)
        create_dropout_masks(self.scratch_dir, masks_filename, n_visible, ks=1000)
        masks_dataset = BigDataset(masks_route + ".hdf5", "masks/.*", "masks")

        nade = self.nade_class(n_visible, self.n_hidden, 1, self.n_components, nonlinearity=self.nonlinearity)
        loss_function = 'sym_masked_neg_loglikelihood_gradient'
        validation_loss = lambda ins: -ins.model.estimate_average_loglikelihood_for_dataset_using_masks(validation_dataset, masks_dataset, loops=self.validation_loops)
        validation_loss_measurement = Instrumentation.Function('validation_loss', validation_loss)

        console = Backends.Console()
        textfile_log = Backends.TextFile(os.path.join(self.scratch_dir, "NADE_training.log"))
        hdf5_backend = Backends.HDF5(self.scratch_dir, "NADE")

        # Pretrain layerwise
        for l in xrange(1, self.h_layers + 1):
            if l == 1:
                nade.initialize_parameters_from_dataset(training_dataset)
            else:
                nade = self.nade_class.create_from_smaller_NADE(nade, add_n_hiddens=1)

            # Configure training
            trainer = Optimization.MomentumSGD(nade, nade.__getattribute__(loss_function))
            trainer.set_datasets([training_dataset, masks_dataset])
            trainer.set_learning_rate(self.lr)
            trainer.set_datapoints_as_columns(True)
            trainer.add_controller(TrainingController.AdaptiveLearningRate(self.lr, 0, epochs=self.pretraining_epochs))
            trainer.add_controller(TrainingController.MaxIterations(self.pretraining_epochs))
            trainer.add_controller(TrainingController.ConfigurationSchedule("momentum", [(2, 0), (float('inf'), self.momentum)]))
            trainer.set_updates_per_epoch(self.epoch_size)
            trainer.set_minibatch_size(self.batch_size)
            trainer.add_controller(TrainingController.NaNBreaker())

            # Instrument the training
            trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend],
                                                                        Instrumentation.Function("training_loss", lambda ins: ins.get_training_loss())))
            trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend], Instrumentation.Configuration()))
            trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend], Instrumentation.Timestamp()))

            # Train
            trainer.set_context("pretraining_%d" % l)
            trainer.train()

        # Configure training
        ordering = range(n_visible)
        np.random.shuffle(ordering)
        trainer = Optimization.MomentumSGD(nade, nade.__getattribute__(loss_function))
        trainer.set_datasets([training_dataset, masks_dataset])
        trainer.set_learning_rate(self.lr)
        trainer.set_datapoints_as_columns(True)
        trainer.add_controller(TrainingController.AdaptiveLearningRate(self.lr, 0, epochs=self.epochs))
        trainer.add_controller(TrainingController.MaxIterations(self.epochs))
        trainer.add_controller(TrainingController.ConfigurationSchedule("momentum", [(2, 0), (float('inf'), self.momentum)]))
        trainer.set_updates_per_epoch(self.epoch_size)
        trainer.set_minibatch_size(self.batch_size)

        trainer.add_controller(TrainingController.NaNBreaker())

        # Instrument the training
        trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend],
                                                                    Instrumentation.Function("training_loss", lambda ins: ins.get_training_loss())))

        trainer.add_instrumentation(Instrumentation.Instrumentation([console], validation_loss_measurement))
        trainer.add_instrumentation(Instrumentation.Instrumentation([hdf5_backend], validation_loss_measurement, at_lowest=[Instrumentation.Parameters()]))
        trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend], Instrumentation.Configuration()))
        trainer.add_instrumentation(Instrumentation.Instrumentation([console, textfile_log, hdf5_backend], Instrumentation.Timestamp()))

        # Train
        trainer.train()

        if trainer.was_successful():
            self.nade_obj = nade
        else:
            warnings.warn('RNADE training failed')

    def score_samples(self, X):
        assert(self.nade_obj is not None)
        logpdf = self.nade_obj.logdensity(X.T)
        assert(logpdf.shape == (X.shape[0],))
        return logpdf

    def get_params_(self):
        assert(self.nade_obj is not None)
        # This could later be truncated down to the params we actually need in
        # loglik_chk()
        D = self.nade_obj.get_parameters()
        # This could be a deep copy or cast to np array if we wanted to be safe
        D['orderings'] = self.nade_obj.orderings
        return D

    @staticmethod
    def loglik_chk(X, params):
        N, n_visible = X.shape

        # TODO infer these from parameters
        n_hidden, n_layers = params['n_hidden'], params['n_layers']

        Wflags, W1, b1 = params['Wflags'], params['W1'], params['b1']
        Ws, bs = params['Ws'], params['bs']
        V_alpha, b_alpha = params['V_alpha'], params['b_alpha']
        V_mu, b_mu = params['V_mu'], params['b_mu']
        V_sigma, b_sigma = params['V_sigma'], params['b_sigma']
        orderings = params['orderings']

        assert(params['nonlinearity'] == 'RLU')  # Only one supported yet
        act_fun = lambda x_: x_ * (x_ > 0.0)

        def softmax(X):
            '''Calculates softmax row-wise'''
            # TODO implement logsoftmax
            # TODO move to util
            X = X - np.max(X, axis=1, keepdims=True)
            e = np.exp(X)
            R = e / np.sum(e, axis=1, keepdims=True)
            return R

        lp = np.zeros((N, len(orderings)))
        for o_index, curr_order in enumerate(orderings):
            a = np.zeros((N, n_hidden)) + b1[None, :]  # N x H
            for i in curr_order:
                h = act_fun(a)  # N x H
                for l in xrange(n_layers - 1):
                    h = act_fun(np.dot(h, Ws[l, :, :]) + bs[l, None])  # N x H

                # All N x C
                z_alpha = np.dot(h, V_alpha[i, :, :]) + b_alpha[i, None]
                z_mu = np.dot(h, V_mu[i, :, :]) + b_mu[i, None]
                z_sigma = np.dot(h, V_sigma[i, :, :]) + b_sigma[i, None]

                # Any final warping. All N x C.
                Alpha = softmax(z_alpha)
                Mu = z_mu
                Sigma_std = np.exp(z_sigma)

                lp_components = np.zeros(Alpha.shape)
                for cc in xrange(lp_components.shape[1]):
                    lp_components[:, cc] = ss.norm.logpdf(X[:, i], Mu[:, cc], Sigma_std[:, cc])
                # The += is needed to aggregate over the different visible vars
                lp[:, o_index] += logsumexp(lp_components + np.log(Alpha), axis=1)

                a += np.outer(X[:, i], W1[i, :]) + Wflags[i, None]  # N x H
        logpdf = logsumexp(lp + np.log(1.0 / len(orderings)), axis=1)

        assert(logpdf.shape == (X.shape[0],))
        return logpdf

# Dict with sklearn like interfaces for each of the models
STD_BENCH_MODELS = {'MoG': GaussianMixture_, 'VBMoG': BayesianGaussianMixture_,
                    'IGN': IGN, 'RNADE': RNADE, 'Gaussian': Gaussian}
