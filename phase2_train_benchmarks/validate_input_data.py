# Ryan Turner (turnerry@iro.umontreal.ca)
import os
import sys
import numpy as np
import scipy.stats as ss
import ConfigParser
import fileio as io

EPSILON = 1e-12


def moments_report(X):
    N, D = X.shape

    finite = np.all(np.isfinite(X))

    acc = np.abs(np.diff(X, axis=0)) > EPSILON
    acc_valid = np.all(np.any(acc, 1) == np.all(acc, 1))
    acc_rate = np.mean(acc[:, 0])

    print 'N = %d, D = %d' % (N, D)
    print 'finite %d, accept %d' % (finite, acc_valid)
    print 'acc rate %f' % acc_rate

    V = np.std(X, axis=0)
    std_ratio = np.log10(np.max(V) / np.min(V))

    C = np.cov(X, rowvar=0)
    cond_number = np.log10(np.linalg.cond(C))

    corr = np.corrcoef(X, rowvar=0) - np.eye(X.shape[1])

    max_skew = np.max(np.abs(ss.skew(X, axis=0)))
    max_kurt = np.max(ss.kurtosis(X, axis=0))

    print 'log10 std ratio %f, cond number %f' % (std_ratio, cond_number)
    print 'min corr %f, max corr %f' % (np.min(corr), np.max(corr))
    print 'max skew %f, max kurt %f' % (max_skew, max_kurt)


def moments_report_w_burn(X, burn_frac=0.05):
    print 'full data'
    moments_report(X)

    print 'post burn-in'
    moments_report(X[int(burn_frac * X.shape[0]):, :])


def main():
    assert(len(sys.argv) == 2)  # Print usage error instead to be user friendly
    config_file = io.abspath2(sys.argv[1])

    config = ConfigParser.RawConfigParser()
    config.read(config_file)
    input_path = io.abspath2(config.get('phase1', 'output_path'))
    data_ext = config.get('common', 'csv_ext')

    print 'searching for input data in'
    print input_path
    chain_files = sorted(f for f in os.listdir(input_path)
                         if f.endswith(data_ext))
    np.random.shuffle(chain_files)
    print 'found %d files' % len(chain_files)

    for chain in chain_files:
        print '-' * 20
        print chain
        X = io.load_np(input_path, chain, '')
        assert(X.ndim == 2)
        moments_report_w_burn(X)
    print 'done'

if __name__ == '__main__':
    main()
